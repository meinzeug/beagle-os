#!/usr/bin/env python3
"""Reproducible streaming quality baseline smoke for Plan 11.

This script runs guest commands via libvirt qemu-agent on a remote host and
reports a JSON summary for:
- vkms module state
- X11 session/xrandr visibility
- 4K mode apply result
- Sunshine service/API reachability

Usage:
  python3 scripts/test-streaming-quality-smoke.py \
    --host srv1.beagle-os.com --domain beagle-100
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class GuestExecResult:
    exitcode: int
    out: str
    err: str


def _decode_field(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "")
    if not value:
        return ""
    try:
        return base64.b64decode(value).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _run_cmd(argv: list[str]) -> str:
    proc = subprocess.run(argv, check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def _run_ssh(host: str, remote_argv: list[str]) -> str:
    remote_command = " ".join(shlex.quote(arg) for arg in remote_argv)
    argv = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        host,
        remote_command,
    ]
    return _run_cmd(argv)


def _guest_exec(host: str, domain: str, command: str) -> GuestExecResult:
    request = {
        "execute": "guest-exec",
        "arguments": {
            "path": "/bin/bash",
            "arg": ["-lc", command],
            "capture-output": True,
        },
    }
    launch_raw = _run_ssh(host, ["virsh", "qemu-agent-command", domain, json.dumps(request)])
    launch_doc = json.loads(launch_raw)
    pid = int(((launch_doc.get("return") or {}).get("pid") or 0))
    if pid <= 0:
        raise RuntimeError(f"guest-exec did not return a valid pid: {launch_raw}")

    status_req = {
        "execute": "guest-exec-status",
        "arguments": {"pid": pid},
    }
    status_raw = _run_ssh(host, ["virsh", "qemu-agent-command", domain, json.dumps(status_req)])
    status_doc = json.loads(status_raw)
    ret = status_doc.get("return") or {}
    return GuestExecResult(
        exitcode=int(ret.get("exitcode") or 0),
        out=_decode_field(ret, "out-data"),
        err=_decode_field(ret, "err-data"),
    )


def _xrandr_current_mode(xrandr_out: str) -> str:
    # Example line: "   1280x800      74.99*+"
    for line in xrandr_out.splitlines():
        if "*" in line and re.search(r"\d+x\d+", line):
            return line.strip().split()[0]
    return ""


def _xrandr_has_virtual_output(xrandr_out: str) -> bool:
    for line in xrandr_out.splitlines():
        if " connected" not in line:
            continue
        output = line.strip().split()[0]
        if output.startswith("Virtual-"):
            return True
    return False


def _extract_kv(out: str, key: str) -> str:
    prefix = f"{key}="
    for line in out.splitlines():
        line = line.strip()
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="srv1.beagle-os.com")
    parser.add_argument("--domain", default="beagle-100")
    args = parser.parse_args()

    summary: dict[str, Any] = {
        "host": args.host,
        "domain": args.domain,
        "checks": {},
        "result": "unknown",
    }

    prereq = _guest_exec(
        args.host,
        args.domain,
        (
            "set -e; "
            "guest_user=''; "
            "if [[ -r /etc/beagle/sunshine-healthcheck.env ]]; then "
            "  source /etc/beagle/sunshine-healthcheck.env >/dev/null 2>&1 || true; "
            "fi; "
            "for c in \"${SUNSHINE_GUEST_USER:-}\" beagle ubuntu; do "
            "  [[ -n \"$c\" ]] || continue; "
            "  if id \"$c\" >/dev/null 2>&1; then guest_user=\"$c\"; break; fi; "
            "done; "
            "if [[ -z \"$guest_user\" ]]; then "
            "  guest_user=$(awk -F: '($3>=1000 && $3<65534){print $1; exit}' /etc/passwd); "
            "fi; "
            "[[ -n \"$guest_user\" ]] || { echo 'guest_user='; exit 1; }; "
            "xauth=\"/home/$guest_user/.Xauthority\"; "
            "if [[ ! -f \"$xauth\" ]]; then "
            "  xauth=$(find \"/home/$guest_user\" -maxdepth 3 -name .Xauthority 2>/dev/null | head -n1 || true); "
            "fi; "
            "echo \"guest_user=$guest_user\"; "
            "echo \"xauth=$xauth\"; "
            "id \"$guest_user\"; "
            "ls -l /tmp/.X11-unix/X0; "
            "[[ -n \"$xauth\" ]] && ls -l \"$xauth\" || true"
        ),
    )
    guest_user = _extract_kv(prereq.out, "guest_user")
    xauth = _extract_kv(prereq.out, "xauth")
    summary["checks"]["x11_prereq"] = {
        "ok": prereq.exitcode == 0 and bool(guest_user),
        "exitcode": prereq.exitcode,
        "guest_user": guest_user,
        "xauthority": xauth,
        "out": prereq.out,
        "err": prereq.err,
    }

    xauth_ref = xauth or f"/home/{guest_user}/.Xauthority"
    xrandr = _guest_exec(
        args.host,
        args.domain,
        f"DISPLAY=:0 XAUTHORITY={shlex.quote(xauth_ref)} xrandr --query",
    )
    xrandr_out = xrandr.out
    output_name = ""
    for line in xrandr_out.splitlines():
        if " connected" in line:
            output_name = line.split()[0]
            break
    summary["checks"]["xrandr_query"] = {
        "ok": xrandr.exitcode == 0,
        "exitcode": xrandr.exitcode,
        "output": output_name,
        "current_mode": _xrandr_current_mode(xrandr_out),
        "has_4k_mode": "3840x2160_60.00" in xrandr_out,
        "err": xrandr.err,
    }

    set_4k = _guest_exec(
        args.host,
        args.domain,
        (
            f"DISPLAY=:0 XAUTHORITY={shlex.quote(xauth_ref)} "
            "xrandr --output Virtual-1 --mode 3840x2160_60.00; "
            f"DISPLAY=:0 XAUTHORITY={shlex.quote(xauth_ref)} xrandr --query"
        ),
    )
    summary["checks"]["xrandr_set_4k"] = {
        "ok": set_4k.exitcode == 0 and "3840x2160_60.00" in _xrandr_current_mode(set_4k.out),
        "exitcode": set_4k.exitcode,
        "current_mode_after": _xrandr_current_mode(set_4k.out),
        "err": set_4k.err,
    }

    vkms = _guest_exec(
        args.host,
        args.domain,
        "lsmod | grep vkms || true; ls -l /dev/dri; systemctl is-active beagle-sunshine.service",
    )
    vkms_loaded = "vkms" in vkms.out
    virtual_output_present = _xrandr_has_virtual_output(xrandr_out)
    sunshine_active = "active" in vkms.out
    summary["checks"]["vkms_sunshine"] = {
        "ok": vkms.exitcode == 0 and sunshine_active and (vkms_loaded or virtual_output_present),
        "exitcode": vkms.exitcode,
        "vkms_loaded": vkms_loaded,
        "virtual_output_present": virtual_output_present,
        "out": vkms.out,
        "err": vkms.err,
    }

    api = _guest_exec(
        args.host,
        args.domain,
        (
            "source /etc/beagle/sunshine-healthcheck.env >/dev/null 2>&1; "
            "api_port=$((SUNSHINE_PORT+1)); "
            # tls-bypass-allowlist: guest-exec loopback to Sunshine API; self-signed cert on 127.0.0.1
            "curl --insecure -fsS --connect-timeout 3 --max-time 5 "  # tls-bypass-allowlist: guest-exec loopback to Sunshine API
            "--user \"${SUNSHINE_USER}:${SUNSHINE_PASSWORD}\" "
            "\"https://127.0.0.1:${api_port}/api/apps\" >/dev/null && echo APPS_OK || echo APPS_FAIL"
        ),
    )
    summary["checks"]["sunshine_api_apps"] = {
        "ok": "APPS_OK" in api.out,
        "exitcode": api.exitcode,
        "out": api.out,
        "err": api.err,
    }

    hard_requirements = [
        summary["checks"]["x11_prereq"]["ok"],
        summary["checks"]["xrandr_query"]["ok"],
        summary["checks"]["vkms_sunshine"]["ok"],
        summary["checks"]["sunshine_api_apps"]["ok"],
    ]

    if all(hard_requirements):
        if summary["checks"]["xrandr_set_4k"]["ok"]:
            summary["result"] = "pass_4k"
        else:
            summary["result"] = "pass_with_4k_limit"
    else:
        summary["result"] = "fail"

    print(json.dumps(summary, indent=2))

    if summary["result"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(
            json.dumps(
                {
                    "result": "error",
                    "returncode": exc.returncode,
                    "cmd": exc.cmd,
                    "stdout": exc.stdout,
                    "stderr": exc.stderr,
                },
                indent=2,
            )
        )
        raise SystemExit(2)
