#!/usr/bin/env python3
"""Smoke: Subprocess sandbox prevents shell injection; run_cmd rejects string commands.

Validates that:
1. run_cmd() raises ValueError when passed a string (not a list)
2. run_cmd() raises ValueError when passed an empty list
3. run_cmd() works correctly with a safe list command
4. The CI guard file exists at .github/workflows/security-subprocess-check.yml
5. run_shell_unsafe() is clearly named to make it visible in code review

Run locally or on srv1:
    python3 /opt/beagle/scripts/test-subprocess-sandbox-smoke.py

Expected output: SUBPROCESS_SANDBOX_SMOKE=PASS
"""
from __future__ import annotations

import sys
from pathlib import Path

_OPT = Path("/opt/beagle")
_REPO_ROOT = Path(__file__).resolve().parents[1]

for search_root in (_OPT, _REPO_ROOT):
    p = str(search_root)
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> int:
    try:
        from core.exec.safe_subprocess import run_cmd, run_shell_unsafe
    except ImportError as exc:
        print("SUBPROCESS_SANDBOX_SMOKE=FAIL")
        print(f"error=import error: {exc}")
        return 2

    findings: list[str] = []

    # 1. String command must be rejected
    try:
        run_cmd("echo hello")
        findings.append("FAIL: run_cmd('echo hello') did not raise ValueError")
    except ValueError:
        pass  # Expected
    except Exception as exc:
        findings.append(f"FAIL: run_cmd(str) raised unexpected {type(exc).__name__}: {exc}")

    # 2. Empty list must be rejected
    try:
        run_cmd([])
        findings.append("FAIL: run_cmd([]) did not raise ValueError")
    except ValueError:
        pass  # Expected
    except Exception as exc:
        findings.append(f"FAIL: run_cmd([]) raised unexpected {type(exc).__name__}: {exc}")

    # 3. Safe list command must work (true always exits 0)
    try:
        result = run_cmd(["true"])
        if result.returncode != 0:
            findings.append(f"FAIL: run_cmd(['true']) returned {result.returncode}")
    except Exception as exc:
        findings.append(f"FAIL: run_cmd(['true']) raised {type(exc).__name__}: {exc}")

    # 4. run_shell_unsafe must exist and be callable
    if not callable(run_shell_unsafe):
        findings.append("FAIL: run_shell_unsafe is not callable")

    # 5. CI guard file must exist in the repo
    ci_guard = _REPO_ROOT / ".github" / "workflows" / "security-subprocess-check.yml"
    if not ci_guard.exists():
        findings.append(f"FAIL: CI guard not found at {ci_guard.relative_to(_REPO_ROOT)}")

    if findings:
        print("SUBPROCESS_SANDBOX_SMOKE=FAIL")
        for f in findings:
            print(f"  {f}")
        return 1

    print("SUBPROCESS_SANDBOX_SMOKE=PASS")
    print("checks=string_rejected empty_rejected list_works ci_guard_present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
