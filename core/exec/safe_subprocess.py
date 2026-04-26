"""Safe subprocess execution helper.

Replaces ad-hoc ``subprocess.run`` calls with a single entry point that:

* Rejects shell execution (must use ``run_shell_unsafe`` for documented exceptions)
* Enforces list-style commands (no string commands)
* Has a mandatory timeout (default 30 s)
* Caps captured output size to prevent memory exhaustion
* Logs oversize output as a warning

Usage::

    from core.exec.safe_subprocess import run_cmd

    output = run_cmd(["virsh", "list", "--all"])
    run_cmd(["systemctl", "restart", "beagle-manager"], capture=False)
"""
from __future__ import annotations

import logging
import subprocess
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30       # seconds
_DEFAULT_MAX_OUTPUT = 10 * 1024 * 1024  # 10 MiB


def run_cmd(
    cmd: list[str],
    *,
    timeout: int | float = _DEFAULT_TIMEOUT,
    check: bool = True,
    capture: bool = True,
    max_output: int = _DEFAULT_MAX_OUTPUT,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command safely.

    Parameters
    ----------
    cmd:
        Command as a *list* of strings.  Passing a plain ``str`` raises
        ``ValueError`` to prevent accidental shell injection.
    timeout:
        Seconds before the process is killed.  Mandatory — no ``None`` allowed.
    check:
        If True (default), raise ``subprocess.CalledProcessError`` on non-zero exit.
    capture:
        If True (default), capture stdout/stderr.
    max_output:
        If the combined output exceeds this many bytes, it is truncated and a
        warning is logged.
    env:
        Optional explicit environment dict.  ``None`` inherits the current env.
    cwd:
        Optional working directory.

    Returns
    -------
    subprocess.CompletedProcess
    """
    if not isinstance(cmd, list):
        raise ValueError(
            f"run_cmd() requires a list, got {type(cmd).__name__!r}. "
            "Never pass a shell string — use a list to prevent injection."
        )
    if not cmd:
        raise ValueError("run_cmd() requires a non-empty command list.")

    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False,          # we handle check ourselves so we can truncate output first
        timeout=timeout,
        shell=False,          # Keep shell execution disabled in this helper.
        env=env,
        cwd=cwd,
    )

    if capture:
        if result.stdout and len(result.stdout.encode()) > max_output:
            log.warning(
                "run_cmd stdout truncated: command=%r output_bytes=%d max=%d",
                cmd[0], len(result.stdout.encode()), max_output,
            )
            result = subprocess.CompletedProcess(
                args=result.args,
                returncode=result.returncode,
                stdout=result.stdout[:max_output],
                stderr=result.stderr,
            )

    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )

    return result


def run_shell_unsafe(
    cmd: str,
    *,
    timeout: int | float = _DEFAULT_TIMEOUT,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command string.

    This function is intentionally named ``_unsafe`` to make it visible in
    code review.  It MUST only be used in the following documented scenarios:

    - Pipe chains that cannot be expressed as a list (e.g. ``cmd1 | cmd2``)
    - The call site must have a ``# noqa: shell-allowed: <reason>`` comment

    Never use for user-supplied input.
    """
    log.warning("run_shell_unsafe called: cmd=%r", cmd[:200])
    return subprocess.run(
        cmd,
        shell=True,  # noqa: shell-allowed: explicit escape hatch — see docstring
        capture_output=capture,
        text=True,
        check=check,
        timeout=timeout,
    )
