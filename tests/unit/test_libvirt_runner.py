"""Unit tests for providers/beagle/libvirt_runner.py."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
PROVIDERS_DIR = ROOT_DIR / "providers" / "beagle"
for _p in [str(ROOT_DIR), str(PROVIDERS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libvirt_runner import LibvirtError, LibvirtRunner


def make_fake_run(stdout: str = "", returncode: int = 0, stderr: str = ""):
    """Return a run_cmd mock that returns a fixed CompletedProcess."""
    def fake_run(cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )
    return fake_run


# ---------------------------------------------------------------------------
# virsh() — basic dispatch
# ---------------------------------------------------------------------------

def test_virsh_returns_stdout():
    runner = LibvirtRunner(run_cmd=make_fake_run(stdout="running\n"))
    assert runner.virsh("domstate", "beagle-100") == "running"


def test_virsh_raises_on_nonzero():
    runner = LibvirtRunner(run_cmd=make_fake_run(returncode=1, stderr="Domain not found"))
    with pytest.raises(LibvirtError) as exc_info:
        runner.virsh("domstate", "beagle-100")
    assert exc_info.value.returncode == 1
    assert "Domain not found" in exc_info.value.stderr


def test_virsh_connect_flag_injected():
    captured = []
    def fake(cmd):
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")
    runner = LibvirtRunner(connect="qemu:///system", run_cmd=fake)
    runner.virsh("list", "--all")
    assert "--connect" in captured[0]
    assert "qemu:///system" in captured[0]


# ---------------------------------------------------------------------------
# _safe_arg — injection prevention
# ---------------------------------------------------------------------------

def test_safe_arg_rejects_shell_meta():
    runner = LibvirtRunner(run_cmd=make_fake_run())
    for bad in ["; rm -rf /", "$(evil)", "`cmd`", "| cat /etc/passwd"]:
        with pytest.raises(ValueError):
            runner.virsh("domstate", bad)


def test_safe_arg_rejects_empty():
    runner = LibvirtRunner(run_cmd=make_fake_run())
    with pytest.raises(ValueError):
        runner.virsh("domstate", "")


def test_safe_arg_allows_normal():
    runner = LibvirtRunner(run_cmd=make_fake_run(stdout="running"))
    # Should not raise
    runner.virsh("domstate", "beagle-100")
    runner.virsh("domstate", "beagle-vm.test")


# ---------------------------------------------------------------------------
# domain_state
# ---------------------------------------------------------------------------

def test_domain_state_returns_stripped():
    runner = LibvirtRunner(run_cmd=make_fake_run(stdout="  shut off  \n"))
    assert runner.domain_state(100) == "shut off"


def test_domain_state_returns_unknown_on_error():
    runner = LibvirtRunner(run_cmd=make_fake_run(returncode=1, stderr="not found"))
    assert runner.domain_state(100) == "unknown"


def test_domain_state_rejects_invalid_vmid():
    runner = LibvirtRunner(run_cmd=make_fake_run())
    with pytest.raises(ValueError):
        runner.domain_state(-1)
    with pytest.raises(ValueError):
        runner.domain_state(0)


# ---------------------------------------------------------------------------
# domifaddr source validation
# ---------------------------------------------------------------------------

def test_domifaddr_rejects_invalid_source():
    runner = LibvirtRunner(run_cmd=make_fake_run())
    with pytest.raises(ValueError):
        runner.domifaddr(100, source="evil; rm -rf /")


def test_domifaddr_valid_sources():
    runner = LibvirtRunner(run_cmd=make_fake_run(stdout=""))
    for src in ("lease", "agent", "arp"):
        runner.domifaddr(100, source=src)  # should not raise
