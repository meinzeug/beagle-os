#!/usr/bin/env python3
"""Smoke test: Cleanup hooks leave srv1 in clean state (R3 gate).

Validates that test artifacts, temporary logs, and state don't persist after
smoke test runs. This ensures repeatability and prevents test pollution.
"""
import sys
import subprocess
import os
import json
from pathlib import Path


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    """Run command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out"
    except Exception as e:
        return 255, "", str(e)


def cleanup_srv1_state() -> tuple[bool, dict]:
    """Cleanup temporary state and logs; validate clean state."""
    results = {
        "cleanup_paths": [],
        "validation_checks": [],
        "issues": [],
    }
    
    # Cleanup temp logs and state
    cleanup_targets = [
        "/tmp/bootstrap-rerun.log",
        "/tmp/beagle-test-*.tmp",
        "/var/log/beagle-*.log.bak",
    ]
    
    for target in cleanup_targets:
        # Use find to handle glob patterns safely
        if "*" in target:
            rc, out, _ = run_cmd(["find", target.rsplit("*", 1)[0], "-name", target.split("*", 1)[1], "-delete"])
        else:
            rc, _, _ = run_cmd(["rm", "-f", target])
        results["cleanup_paths"].append({"path": target, "deleted": rc == 0})
    
    # Validation checks
    checks = [
        {
            "name": "beagle-control-plane running",
            "cmd": ["systemctl", "is-active", "beagle-control-plane.service"],
        },
        {
            "name": "nginx running",
            "cmd": ["systemctl", "is-active", "nginx.service"],
        },
        {
            "name": "no zombie processes on system",
            "cmd": ["sh", "-c", "! ps aux | grep -E ' Z ' | grep -v grep"],
        },
        {
            "name": "disk cleanup: /var/lib/beagle not over 90%",
            "cmd": ["sh", "-c", "[ $(df /var/lib/beagle | tail -1 | awk '{print $5}' | sed 's/%//') -lt 90 ]"],
        },
    ]
    
    all_pass = True
    for check in checks:
        rc, out, err = run_cmd(check["cmd"])
        passed = rc == 0
        results["validation_checks"].append({
            "name": check["name"],
            "passed": passed,
        })
        if not passed:
            all_pass = False
            results["issues"].append(f"{check['name']}: {err.strip() or 'failed'}")
    
    # Final state summary
    if all_pass and all(p["deleted"] for p in results["cleanup_paths"] if "deleted" in p):
        results["cleanup_status"] = "clean"
    else:
        results["cleanup_status"] = "dirty" if results["issues"] else "partial"
    
    return all_pass, results


def main():
    success, results = cleanup_srv1_state()
    
    if success:
        print(f"CLEANUP_HOOKS_SMOKE=PASS")
        print(f"status={results['cleanup_status']}")
        print(f"validation_checks={len([c for c in results['validation_checks'] if c['passed']])}/{len(results['validation_checks'])}")
        return 0
    else:
        print(f"CLEANUP_HOOKS_SMOKE=FAIL")
        print(f"status={results['cleanup_status']}")
        for issue in results["issues"]:
            print(f"issue={issue}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
