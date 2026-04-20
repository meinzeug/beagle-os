from __future__ import annotations

import ipaddress
import json
import os
import secrets
import socket
import subprocess
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote


class VmConsoleAccessService:
    def __init__(
        self,
        *,
        host_provider_kind: str,
        listify: Callable[[object], list[str]],
        novnc_path: str,
        novnc_token_file: str,
        proxmox_ui_ports_raw: str,
        public_server_name: str,
    ) -> None:
        self._host_provider_kind = str(host_provider_kind or "").strip().lower()
        self._listify = listify
        self._novnc_path = str(novnc_path or "/novnc").strip() or "/novnc"
        self._novnc_token_file = Path(str(novnc_token_file or "/etc/beagle/novnc/tokens")).expanduser()
        self._proxmox_ui_ports_raw = str(proxmox_ui_ports_raw or "")
        self._public_server_name = str(public_server_name or "").strip()

    def _proxmox_ui_port(self) -> int:
        for value in self._listify(self._proxmox_ui_ports_raw):
            text = str(value or "").strip()
            if text.isdigit():
                return int(text)
        return 8006

    @staticmethod
    def _libvirt_guest_ip(vmid: int, domain_name: str | None = None) -> str | None:
        """Try to find the guest's primary IPv4 address via the QEMU guest agent."""
        default_domain = f"beagle-{int(vmid)}"
        domain = str(domain_name or "").strip() or default_domain
        for src in ("agent", "lease"):
            for dom in (domain, default_domain):
                result = subprocess.run(
                    ["virsh", "--connect", "qemu:///system", "domifaddr", dom, "--source", src],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    check=False,
                )
                if result.returncode != 0:
                    continue
                for line in result.stdout.splitlines():
                    parts = line.split()
                    # virsh domifaddr output: iface  MAC  protocol  address/prefix
                    if len(parts) >= 4 and parts[2] == "ipv4":
                        addr = parts[3].split("/")[0]
                        try:
                            import ipaddress
                            ip = ipaddress.IPv4Address(addr)
                            if not ip.is_loopback:
                                return str(ip)
                        except Exception:
                            continue
        return None

    @staticmethod
    def _libvirt_vnc_port(vmid: int, domain_name: str | None = None) -> int | None:
        default_domain = f"beagle-{int(vmid)}"
        domain = str(domain_name or "").strip() or default_domain
        result = subprocess.run(
            ["virsh", "--connect", "qemu:///system", "vncdisplay", domain],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        # If the display name doesn't match the libvirt domain, retry with the
        # canonical beagle-{vmid} pattern (vm.name is the display name, not the
        # libvirt domain name).
        if result.returncode != 0 and domain != default_domain:
            result = subprocess.run(
                ["virsh", "--connect", "qemu:///system", "vncdisplay", default_domain],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        if result.returncode != 0:
            return None
        display = str(result.stdout or "").strip()
        if not display:
            return None
        if display.startswith(":") and display[1:].isdigit():
            return 5900 + int(display[1:])
        if ":" in display:
            tail = display.rsplit(":", 1)[-1]
            if tail.isdigit():
                return 5900 + int(tail)
        return None

    def _upsert_beagle_novnc_token(self, *, vmid: int, target_port: int, target_host: str = "127.0.0.1") -> str:
        token = self._get_or_create_vm_secret_token(vmid)
        line = f"{token}: {target_host}:{int(target_port)}"
        token_file = self._novnc_token_file
        token_file.parent.mkdir(parents=True, exist_ok=True)
        entries: list[str] = []
        if token_file.exists():
            for raw in token_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                text = str(raw or "").strip()
                if not text or text.startswith("#"):
                    continue
                key = text.split(":", 1)[0].strip()
                if key == token:
                    continue
                entries.append(text)
        entries.append(line)
        tmp = token_file.with_suffix(token_file.suffix + ".tmp")
        tmp.write_text("\n".join(entries) + "\n", encoding="utf-8")
        tmp.replace(token_file)
        return token

    def _vm_secrets_path(self) -> Path:
        return self._novnc_token_file.parent / "vm-tokens.json"

    def _get_or_create_vm_secret_token(self, vmid: int) -> str:
        """Return the persistent secret token for vmid, creating one if needed.

        Tokens are stored in a separate file (mode 600) so that the predictable
        vm-{vmid} pattern is never used as a noVNC token.  Each token is a
        32-byte URL-safe random value generated by secrets.token_urlsafe().
        """
        secrets_path = self._vm_secrets_path()
        key = str(int(vmid))
        store: dict[str, str] = {}
        if secrets_path.exists():
            try:
                raw = secrets_path.read_text(encoding="utf-8", errors="ignore")
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    store = {str(k): str(v) for k, v in loaded.items() if k and v}
            except Exception:
                pass
        if key in store:
            return store[key]
        token = secrets.token_urlsafe(32)
        store[key] = token
        secrets_path.parent.mkdir(parents=True, exist_ok=True)
        # Write atomically; restrict permissions to owner-only (mode 600).
        tmp = secrets_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(store, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(secrets_path)
        return token

    @staticmethod
    def _is_ip_literal(value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        try:
            ipaddress.ip_address(text)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_loopback_ip(value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        try:
            return ipaddress.ip_address(text).is_loopback
        except ValueError:
            return False

    @staticmethod
    def _primary_ipv4() -> str | None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't send packets; used to ask kernel for preferred source IP.
            sock.connect(("1.1.1.1", 80))
            candidate = str(sock.getsockname()[0] or "").strip()
            if candidate and not candidate.startswith("127."):
                return candidate
            return None
        except OSError:
            return None
        finally:
            sock.close()

    def _resolve_novnc_host(self, host: str) -> str:
        candidate = str(host or "").strip()
        if not candidate:
            fallback = self._primary_ipv4()
            return fallback or candidate
        # Already an IP literal – use as-is.
        if self._is_ip_literal(candidate):
            return candidate
        # FQDN with dots (e.g. myserver.example.com): keep the name so that
        # Let's Encrypt / public TLS certs remain valid.
        if "." in candidate:
            return candidate
        # Bare hostname (e.g. "beagleserver"): resolve to IP so that thin
        # clients that have no matching DNS entry can still connect.
        try:
            resolved = socket.gethostbyname(candidate)
        except OSError:
            resolved = ""
        if resolved and not self._is_loopback_ip(resolved):
            return resolved
        fallback = self._primary_ipv4()
        return fallback or candidate

    @staticmethod
    def _tcp_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
        """Return True if a TCP connection to host:port can be established within timeout."""
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except OSError:
            return False

    def _beagle_novnc_url(self, *, host: str, vmid: int, domain_name: str | None = None) -> str | None:
        # Prefer guest-side x11vnc (port 5901) which captures the actual X11 display.
        # QEMU's built-in VNC captures the VGA text buffer (TTY1) which does not
        # show the XFCE session when the guest uses KMS/modesetting (Virtual-1).
        guest_ip = self._libvirt_guest_ip(vmid, domain_name)
        if guest_ip and self._tcp_port_open(guest_ip, 5901):
            token = self._upsert_beagle_novnc_token(vmid=vmid, target_port=5901, target_host=guest_ip)
        else:
            # Fall back to QEMU VGA VNC on localhost (shows TTY1 on KMS guests,
            # but at least works as a fallback during firstboot/provisioning).
            port = self._libvirt_vnc_port(vmid, domain_name)
            if port is None:
                return None
            token = self._upsert_beagle_novnc_token(vmid=vmid, target_port=port)
        resolved_host = self._resolve_novnc_host(host)
        base_path = self._novnc_path.strip()
        if not base_path.startswith("/"):
            base_path = "/" + base_path
        base_path = base_path.rstrip("/")
        token_q = quote(token, safe="")
        path_q = quote(f"beagle-novnc/websockify?token={token_q}", safe="/?=&")
        return f"https://{resolved_host}{base_path}/vnc.html?autoconnect=1&resize=scale&path={path_q}"

    def build_novnc_access(self, vm: Any) -> dict[str, Any]:
        vmid = int(getattr(vm, "vmid", 0) or 0)
        node = str(getattr(vm, "node", "") or "").strip()
        host = self._public_server_name or node
        if vmid <= 0 or not host:
            return {
                "provider": self._host_provider_kind or "unknown",
                "available": False,
                "url": "",
                "reason": "VM-Kontext fuer noVNC unvollstaendig.",
            }
        if self._host_provider_kind == "proxmox":
            if not node:
                return {
                    "provider": "proxmox",
                    "available": False,
                    "url": "",
                    "reason": "VM-Kontext fuer noVNC unvollstaendig.",
                }
            port = self._proxmox_ui_port()
            params = "console=kvm&novnc=1&resize=scale&vmid={vmid}&node={node}".format(
                vmid=vmid,
                node=quote(node, safe=""),
            )
            return {
                "provider": "proxmox",
                "available": True,
                "url": f"https://{host}:{port}/?{params}",
                "reason": "",
            }
        if self._host_provider_kind == "beagle":
            vm_domain = str(getattr(vm, "name", "") or "").strip() or None
            url = self._beagle_novnc_url(host=host, vmid=vmid, domain_name=vm_domain)
            if not url:
                return {
                    "provider": "beagle",
                    "available": False,
                    "url": "",
                    "reason": "VNC-Display der VM ist aktuell nicht verfuegbar (laeuft die VM?).",
                }
            return {
                "provider": "beagle",
                "available": True,
                "url": url,
                "reason": "",
            }
        return {
            "provider": self._host_provider_kind or "unknown",
            "available": False,
            "url": "",
            "reason": "noVNC ist fuer diesen Provider noch nicht implementiert.",
        }
