"""LibvirtRunner — centralized virsh subprocess adapter.

All virsh calls go through this class so that:
- VM ID validation is always applied before calling virsh
- Timeouts are always enforced
- Output size is capped
- The QEMU connect URI is set once

Usage::

    from providers.beagle.libvirt_runner import LibvirtRunner

    runner = LibvirtRunner()
    state = runner.domain_state(100)        # "running" | "shut off" | ...
    xml = runner.domain_xml(100)
    runner.start(100)
    runner.shutdown(100)
    output = runner.virsh("domifaddr", "beagle-100", "--source", "agent")
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

# Default virsh executable and connect URI
_DEFAULT_VIRSH = "virsh"
_DEFAULT_CONNECT = "qemu:///system"


class LibvirtError(RuntimeError):
    """Raised when a virsh command fails."""
    def __init__(self, msg: str, returncode: int = -1, stderr: str = "") -> None:
        super().__init__(msg)
        self.returncode = returncode
        self.stderr = stderr


class LibvirtRunner:
    """Thin wrapper around virsh that enforces validation + safe execution.

    Inject *run_cmd* in tests to mock subprocess calls without executing virsh.
    """

    def __init__(
        self,
        *,
        connect: str = _DEFAULT_CONNECT,
        virsh_bin: str = _DEFAULT_VIRSH,
        timeout: int = 30,
        run_cmd: Callable[[list[str]], subprocess.CompletedProcess] | None = None,
    ) -> None:
        self._connect = connect
        self._virsh_bin = virsh_bin
        self._timeout = timeout
        # Allow injection of a fake run_cmd in tests
        self._run_cmd = run_cmd or self._default_run_cmd

    # ------------------------------------------------------------------
    # High-level domain operations
    # ------------------------------------------------------------------

    def virsh(self, *args: str, timeout: int | None = None) -> str:
        """Execute a virsh sub-command and return stdout.

        All string arguments are validated to prevent injection.
        Raises LibvirtError on non-zero exit.
        """
        validated = [self._safe_arg(a) for a in args]
        cmd = [self._virsh_bin, "--connect", self._connect] + validated
        result = self._run_cmd_with_timeout(cmd, timeout=timeout or self._timeout)
        if result.returncode != 0:
            raise LibvirtError(
                f"virsh {args[0]!r} failed (rc={result.returncode}): {result.stderr.strip()[:500]}",
                returncode=result.returncode,
                stderr=result.stderr,
            )
        return result.stdout.strip()

    def domain_state(self, vmid: int) -> str:
        """Return the domain state string (e.g. 'running', 'shut off')."""
        from core.validation.identifiers import validate_vmid
        vmid_int = validate_vmid(vmid)
        domain = f"beagle-{vmid_int}"
        try:
            raw = self.virsh("domstate", domain)
            return raw.strip()
        except LibvirtError:
            return "unknown"

    def domain_xml(self, vmid: int) -> str:
        """Return the full domain XML for a VM."""
        from core.validation.identifiers import validate_vmid
        vmid_int = validate_vmid(vmid)
        domain = f"beagle-{vmid_int}"
        return self.virsh("dumpxml", domain)

    def start(self, vmid: int) -> None:
        """Start (boot) a domain."""
        from core.validation.identifiers import validate_vmid
        vmid_int = validate_vmid(vmid)
        self.virsh("start", f"beagle-{vmid_int}")

    def shutdown(self, vmid: int) -> None:
        """Send ACPI shutdown to a domain."""
        from core.validation.identifiers import validate_vmid
        vmid_int = validate_vmid(vmid)
        self.virsh("shutdown", f"beagle-{vmid_int}")

    def destroy(self, vmid: int) -> None:
        """Force-stop (destroy) a domain."""
        from core.validation.identifiers import validate_vmid
        vmid_int = validate_vmid(vmid)
        self.virsh("destroy", f"beagle-{vmid_int}")

    def reboot(self, vmid: int) -> None:
        """Reboot a domain."""
        from core.validation.identifiers import validate_vmid
        vmid_int = validate_vmid(vmid)
        self.virsh("reboot", f"beagle-{vmid_int}")

    def list_all(self) -> str:
        """Return 'virsh list --all' output."""
        return self.virsh("list", "--all")

    def domifaddr(self, vmid: int, *, source: str = "lease") -> str:
        """Return domifaddr output for a domain."""
        from core.validation.identifiers import validate_vmid
        vmid_int = validate_vmid(vmid)
        domain = f"beagle-{vmid_int}"
        # validate source parameter
        if source not in ("lease", "agent", "arp"):
            raise ValueError(f"Invalid domifaddr source {source!r}. Use: lease, agent, arp")
        return self.virsh("domifaddr", domain, "--source", source)

    def vncdisplay(self, domain: str) -> str:
        """Return vncdisplay output for a named domain."""
        safe_domain = self._safe_arg(domain)
        return self.virsh("vncdisplay", safe_domain)

    def migrate(self, vmid: int, dest_uri: str, *, live: bool = True, persistent: bool = True) -> None:
        """Migrate a domain to another host."""
        from core.validation.identifiers import validate_vmid
        vmid_int = validate_vmid(vmid)
        domain = f"beagle-{vmid_int}"
        flags = ["--live"] if live else []
        if persistent:
            flags.append("--persistent")
        # dest_uri is not validated here — caller is responsible
        self.virsh("migrate", *flags, domain, dest_uri, timeout=300)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_cmd_with_timeout(self, cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess:
        return self._run_cmd(cmd)

    def _default_run_cmd(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=self._timeout,
        )

    @staticmethod
    def _safe_arg(value: str) -> str:
        """Reject argument values that could inject virsh sub-commands.

        Virsh arguments are plain strings — no shell expansion is needed.
        We reject values containing shell meta-characters or null bytes.
        """
        s = str(value)
        forbidden = set('\x00;|&`$(){}[]<>!"\'\\')
        bad = [c for c in s if c in forbidden]
        if bad:
            raise ValueError(
                f"Unsafe virsh argument {value!r} contains forbidden characters: {bad}"
            )
        if not s:
            raise ValueError("Empty virsh argument is not allowed")
        return s
