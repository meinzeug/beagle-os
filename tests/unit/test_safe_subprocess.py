"""Unit tests for core.exec.safe_subprocess."""
from __future__ import annotations

import subprocess

import pytest

from core.exec.safe_subprocess import run_cmd, run_shell_unsafe


# ---------------------------------------------------------------------------
# Basic execution
# ---------------------------------------------------------------------------

def test_run_cmd_basic() -> None:
    result = run_cmd(["echo", "hello"])
    assert "hello" in result.stdout


def test_run_cmd_returns_stdout() -> None:
    result = run_cmd(["printf", "abc"])
    assert result.stdout == "abc"


def test_run_cmd_nonzero_check_raises() -> None:
    with pytest.raises(subprocess.CalledProcessError):
        run_cmd(["false"])


def test_run_cmd_nonzero_check_false_no_raise() -> None:
    result = run_cmd(["false"], check=False)
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# Safety guards
# ---------------------------------------------------------------------------

def test_run_cmd_string_raises() -> None:
    with pytest.raises(ValueError, match="requires a list"):
        run_cmd("echo hello")  # type: ignore[arg-type]


def test_run_cmd_empty_list_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        run_cmd([])


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

def test_run_cmd_timeout_raises() -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        run_cmd(["sleep", "10"], timeout=0.05)


# ---------------------------------------------------------------------------
# Output truncation
# ---------------------------------------------------------------------------

def test_run_cmd_truncates_large_output() -> None:
    # Generate ~5 KiB output, limit to 1 KiB
    result = run_cmd(
        ["python3", "-c", "print('x' * 5000)"],
        max_output=1024,
    )
    assert len(result.stdout) <= 1024


# ---------------------------------------------------------------------------
# run_shell_unsafe
# ---------------------------------------------------------------------------

def test_run_shell_unsafe_works() -> None:
    result = run_shell_unsafe("echo piped | cat")
    assert "piped" in result.stdout
