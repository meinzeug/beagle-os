#!/usr/bin/env python3
"""R1 VM lifecycle smoke for Beagle OS API.

Flow (API-only, reproducible):
1) login
2) pick online node
3) create VM via /api/v1/vms (mapped to provisioning)
4) start VM via /api/v1/virtualization/vms/{vmid}/power
5) snapshot VM via /api/v1/vms/{vmid}/snapshot
6) reboot VM via /api/v1/virtualization/vms/{vmid}/power
7) delete VM via /api/v1/provisioning/vms/{vmid}

The script always attempts cleanup (delete) before exit.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass

import requests


@dataclass
class StepResult:
    step: str
    status: int
    ok: bool
    detail: str


def _json(resp: requests.Response) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"raw": data}
    except Exception:
        return {"raw": (resp.text or "")[:500]}


def login(base_url: str, username: str, password: str, timeout: float) -> str:
    resp = requests.post(
        f"{base_url}/api/v1/auth/login",
        json={"username": username, "password": password},
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = _json(resp)
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError(f"login failed: {payload}")
    return token


def pick_online_node(base_url: str, headers: dict[str, str], timeout: float) -> str:
    resp = requests.get(f"{base_url}/api/v1/virtualization/nodes", headers=headers, timeout=timeout)
    resp.raise_for_status()
    payload = _json(resp)
    nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else []
    for node in nodes:
        if str(node.get("status", "")).lower() == "online" and str(node.get("name", "")).strip():
            return str(node["name"]).strip()
    if nodes and str(nodes[0].get("name", "")).strip():
        return str(nodes[0]["name"]).strip()
    raise RuntimeError(f"no virtualization node available: {payload}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--memory", type=int, default=2048)
    parser.add_argument("--cores", type=int, default=2)
    parser.add_argument("--disk-gb", type=int, default=32)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    timeout = float(args.timeout)

    results: list[StepResult] = []
    token: str | None = None
    created_vmid: int | None = None
    created_name: str = ""

    try:
        token = login(base_url, args.username, args.password, timeout)
        headers = {"Authorization": f"Bearer {token}"}
        results.append(StepResult("login", 200, True, "ok"))

        node = pick_online_node(base_url, headers, timeout)
        results.append(StepResult("pick_node", 200, True, f"node={node}"))

        suffix = int(time.time()) % 100000
        created_name = f"r1-lifecycle-{suffix}"
        create_payload = {
            "node": node,
            "name": created_name,
            "start": 0,
            "memory": int(args.memory),
            "cores": int(args.cores),
            "disk_gb": int(args.disk_gb),
        }
        create_resp = requests.post(f"{base_url}/api/v1/vms", headers=headers, json=create_payload, timeout=timeout)
        create_data = _json(create_resp)
        created_vmid = int(
            ((create_data.get("provisioned_vm") or {}).get("vmid"))
            or (create_data.get("ubuntu_beagle_vm") or {}).get("vmid")
            or 0
        )
        create_ok = create_resp.status_code in {200, 201} and created_vmid > 0
        results.append(
            StepResult(
                "create",
                create_resp.status_code,
                create_ok,
                f"vmid={created_vmid} payload={json.dumps(create_data)[:220]}",
            )
        )
        if not create_ok:
            raise RuntimeError("create failed")

        start_resp = requests.post(
            f"{base_url}/api/v1/virtualization/vms/{created_vmid}/power",
            headers=headers,
            json={"action": "start"},
            timeout=timeout,
        )
        start_ok = start_resp.status_code in {200, 202}
        results.append(StepResult("start", start_resp.status_code, start_ok, json.dumps(_json(start_resp))[:220]))
        if not start_ok:
            raise RuntimeError("start failed")

        snap_name = f"r1snap-{random.randint(1000, 9999)}"
        snap_resp = requests.post(
            f"{base_url}/api/v1/vms/{created_vmid}/snapshot",
            headers=headers,
            json={"name": snap_name},
            timeout=timeout,
        )
        snap_ok = snap_resp.status_code in {200, 202}
        results.append(StepResult("snapshot", snap_resp.status_code, snap_ok, json.dumps(_json(snap_resp))[:220]))
        if not snap_ok:
            raise RuntimeError("snapshot failed")

        reboot_resp = requests.post(
            f"{base_url}/api/v1/virtualization/vms/{created_vmid}/power",
            headers=headers,
            json={"action": "reboot"},
            timeout=timeout,
        )
        reboot_ok = reboot_resp.status_code in {200, 202}
        results.append(StepResult("reboot", reboot_resp.status_code, reboot_ok, json.dumps(_json(reboot_resp))[:220]))
        if not reboot_ok:
            raise RuntimeError("reboot failed")

    except Exception as exc:
        results.append(StepResult("runtime_exception", 0, False, str(exc)))

    finally:
        if created_vmid and token:
            try:
                delete_resp = requests.delete(
                    f"{base_url}/api/v1/provisioning/vms/{created_vmid}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=timeout,
                )
                delete_ok = delete_resp.status_code in {200, 202, 404}
                results.append(StepResult("delete", delete_resp.status_code, delete_ok, json.dumps(_json(delete_resp))[:220]))
            except Exception as exc:
                results.append(StepResult("delete", 0, False, str(exc)))

    failed = [r for r in results if not r.ok]
    output = {
        "ok": len(failed) == 0,
        "created_name": created_name,
        "created_vmid": created_vmid,
        "checked": len(results),
        "failed": len(failed),
        "results": [r.__dict__ for r in results],
    }
    print(json.dumps(output, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
