#!/usr/bin/env python3
"""Plan 17 SDN smoke test: IPAM mapping and firewall rollback semantics.

This script is intended to run on the Beagle control-plane host.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def _load_token_from_env_file() -> str:
    env_file = Path("/etc/beagle/beagle-manager.env")
    if not env_file.exists():
        return ""
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "BEAGLE_MANAGER_API_TOKEN":
            return value.strip().strip('"').strip("'")
    return ""


def _api_call(base_url: str, token: str, method: str, path: str, payload: dict | None = None) -> dict:
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base_url.rstrip("/") + path, data=body, method=method)
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {"ok": True}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {text}")


def run_ipam_mapping_check(base_url: str, token: str) -> dict:
    suffix = str(int(time.time()))
    zone_id = f"smoke-zone-{suffix}"
    vm_id = f"smoke-vm-{suffix}"
    mac = "52:54:00:aa:bb:cc"
    hostname = f"smoke-{suffix}"
    subnet = "10.254.17.0/24"
    dhcp_start = "10.254.17.10"
    dhcp_end = "10.254.17.250"

    _api_call(
        base_url,
        token,
        "POST",
        "/api/v1/network/ipam/zones",
        {
            "zone_id": zone_id,
            "subnet": subnet,
            "dhcp_start": dhcp_start,
            "dhcp_end": dhcp_end,
        },
    )
    alloc = _api_call(
        base_url,
        token,
        "POST",
        f"/api/v1/network/ipam/zones/{zone_id}/allocate",
        {
            "vm_id": vm_id,
            "mac_address": mac,
            "hostname": hostname,
        },
    )
    ip_address = str(alloc.get("ip_address") or "")
    leases = _api_call(base_url, token, "GET", f"/api/v1/network/ipam/zones/{zone_id}/leases")
    lease_items = leases.get("leases") or []
    match = None
    for lease in lease_items:
        if str(lease.get("vm_id") or "") == vm_id:
            match = lease
            break
    if not match:
        raise RuntimeError("ipam lease not found for vm_id")
    if str(match.get("mac_address") or "").lower() != mac.lower():
        raise RuntimeError("ipam lease MAC mismatch")
    if ip_address and str(match.get("ip_address") or "") != ip_address:
        raise RuntimeError("ipam lease IP mismatch")

    _api_call(
        base_url,
        token,
        "POST",
        f"/api/v1/network/ipam/zones/{zone_id}/release",
        {"vm_id": vm_id},
    )
    return {
        "zone_id": zone_id,
        "vm_id": vm_id,
        "ip_address": ip_address,
        "mac_address": mac,
        "result": "ok",
    }


def run_firewall_rollback_check(repo_root: Path) -> dict:
    sys.path.insert(0, str(repo_root / "beagle-host" / "services"))
    from firewall_service import FirewallProfile, FirewallRule, FirewallService  # pylint: disable=import-error

    with tempfile.TemporaryDirectory(prefix="beagle-fw-smoke-") as tmp:
        tmp_path = Path(tmp)
        state_file = tmp_path / "firewall-rules.json"
        backup_file = tmp_path / "firewall-rules.backup.json"

        fw = FirewallService(state_file=state_file, backup_file=backup_file)
        fw._run_nft_cmd = lambda _cmd, test_only=False: True  # type: ignore[attr-defined]

        good_profile = FirewallProfile(
            profile_id="smoke-allow-22",
            name="Smoke Allow SSH",
            rules=[FirewallRule(direction="inbound", protocol="tcp", port=22, action="allow")],
        )
        second_profile = FirewallProfile(
            profile_id="smoke-allow-443",
            name="Smoke Allow HTTPS",
            rules=[FirewallRule(direction="inbound", protocol="tcp", port=443, action="allow")],
        )
        fw.create_profile(good_profile)
        fw.create_profile(second_profile)
        vm_id = "vm-smoke-rollback"
        fw.apply_profile_to_vm("smoke-allow-22", vm_id)
        fw.apply_profile_to_vm("smoke-allow-443", vm_id)

        fw.rollback()
        restored = fw.get_vm_profile(vm_id)
        if restored is None or restored.profile_id != "smoke-allow-22":
            raise RuntimeError("firewall rollback did not restore previous mapping")

        bad_profile = FirewallProfile(
            profile_id="smoke-bad",
            name="Smoke Bad",
            rules=[FirewallRule(direction="inbound", protocol="tcp", port=22, action="block")],
        )
        fw.create_profile(bad_profile)

        def _run_with_failure(_cmd: list[str], test_only: bool = False) -> bool:
            if test_only:
                return False
            return True

        fw._run_nft_cmd = _run_with_failure  # type: ignore[attr-defined]
        try:
            fw.apply_profile_to_vm("smoke-bad", vm_id)
            raise RuntimeError("expected apply_profile_to_vm to fail for invalid rule")
        except RuntimeError:
            pass

        unchanged = fw.get_vm_profile(vm_id)
        if unchanged is None or unchanged.profile_id != "smoke-allow-22":
            raise RuntimeError("vm profile changed after failed firewall apply")

    return {
        "vm_id": vm_id,
        "result": "ok",
    }


def main() -> int:
    base_url = os.environ.get("BEAGLE_API_BASE", "http://127.0.0.1:9088").strip()
    token = os.environ.get("BEAGLE_API_TOKEN", "").strip() or _load_token_from_env_file()
    if not token:
        print("ERROR: BEAGLE_API_TOKEN missing and not found in /etc/beagle/beagle-manager.env")
        return 2

    repo_root = Path(os.environ.get("BEAGLE_REPO_ROOT", "/opt/beagle")).resolve()

    report = {
        "ipam_mapping": run_ipam_mapping_check(base_url, token),
        "firewall_rollback": run_firewall_rollback_check(repo_root),
    }
    print(json.dumps(report, indent=2))
    print("PLAN17_SDN_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
