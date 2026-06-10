#!/usr/bin/env python3
"""Run a shell command inside a libvirt guest via the QEMU guest agent.

Usage: vm-exec.py <domain> "<shell command>"
Prints stdout, then stderr (if any) to stderr, and exits with the guest's code.
"""
import base64
import json
import subprocess
import sys
import time


def virsh_agent(domain: str, payload: dict) -> dict:
    cmd = ["virsh", "qemu-agent-command", domain, json.dumps(payload)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        sys.stderr.write(out.stderr)
        sys.exit(1)
    return json.loads(out.stdout)


def main() -> int:
    if len(sys.argv) < 3:
        sys.stderr.write("usage: vm-exec.py <domain> <command>\n")
        return 2
    domain = sys.argv[1]
    command = sys.argv[2]
    started = virsh_agent(domain, {
        "execute": "guest-exec",
        "arguments": {
            "path": "/bin/sh",
            "arg": ["-c", command],
            "capture-output": True,
        },
    })
    pid = started["return"]["pid"]
    for _ in range(600):
        status = virsh_agent(domain, {
            "execute": "guest-exec-status",
            "arguments": {"pid": pid},
        })["return"]
        if status.get("exited"):
            break
        time.sleep(0.2)
    out = status.get("out-data", "")
    err = status.get("err-data", "")
    if out:
        sys.stdout.write(base64.b64decode(out).decode("utf-8", "replace"))
    if err:
        sys.stderr.write(base64.b64decode(err).decode("utf-8", "replace"))
    return int(status.get("exitcode", 0))


if __name__ == "__main__":
    raise SystemExit(main())
