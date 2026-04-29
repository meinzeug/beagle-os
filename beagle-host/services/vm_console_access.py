from __future__ import annotations

import ipaddress
import os
import secrets
import socket
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from core.persistence.json_state_store import JsonStateStore

import sys as _sys
_PROVIDERS_DIR = Path(__file__).resolve().parents[2] / "providers" / "beagle"
if str(_PROVIDERS_DIR) not in _sys.path:
    _sys.path.insert(0, str(_PROVIDERS_DIR))
from libvirt_runner import LibvirtRunner as _LibvirtRunner

_LIBVIRT = _LibvirtRunner()

_NOVNC_TOKEN_TTL_SECONDS: float = 30.0


class VmConsoleAccessService:
    def __init__(
        self,
        *,
        host_provider_kind: str,
        listify: Callable[[object], list[str]],
        novnc_path: str,
        novnc_token_file: str,
        public_server_name: str,
    ) -> None:
        self._host_provider_kind = str(host_provider_kind or "").strip().lower()
        self._listify = listify
        self._novnc_path = str(novnc_path or "/novnc").strip() or "/novnc"
        # Legacy plain-text token file path (kept for reference; not used for new tokens).
        self._novnc_token_file = Path(str(novnc_token_file or "/etc/beagle/novnc/tokens")).expanduser()
        # JSON store used by BeagleTokenFile plugin (single-use, TTL-based).
        self._novnc_console_token_store = self._novnc_token_file.parent / "console-tokens.json"
        self._public_server_name = str(public_server_name or "").strip()

    @staticmethod
    def _libvirt_guest_ip(vmid: int, domain_name: str | None = None) -> str | None:
        """Try to find the guest's primary IPv4 address via the QEMU guest agent."""
        from core.validation.identifiers import validate_vmid
        vmid_int = validate_vmid(vmid)
        default_domain = f"beagle-{vmid_int}"
        domain = str(domain_name or "").strip() or default_domain
        for src in ("agent", "lease"):
            for dom in (domain, default_domain):
                try:
                    raw = _LIBVIRT.virsh("domifaddr", dom, "--source", src)
                except Exception:
                    continue
                for line in raw.splitlines():
                    parts = line.split()
                    # virsh domifaddr output: iface  MAC  protocol  address/prefix
                    if len(parts) >= 4 and parts[2] == "ipv4":
                        addr = parts[3].split("/")[0]
                        try:
                            ip = ipaddress.IPv4Address(addr)
                            if not ip.is_loopback:
                                return str(ip)
                        except Exception:
                            continue
        return None

    @staticmethod
    def _libvirt_vnc_port(vmid: int, domain_name: str | None = None) -> int | None:
        from core.validation.identifiers import validate_vmid
        vmid_int = validate_vmid(vmid)
        default_domain = f"beagle-{vmid_int}"
        domain = str(domain_name or "").strip() or default_domain
        try:
            raw = _LIBVIRT.vncdisplay(domain)
        except Exception:
            if domain == default_domain:
                return None
            try:
                raw = _LIBVIRT.vncdisplay(default_domain)
            except Exception:
                return None
        result_stdout = raw
        display = str(result_stdout or "").strip()
        if not display:
            return None
        if display.startswith(":") and display[1:].isdigit():
            return 5900 + int(display[1:])
        if ":" in display:
            tail = display.rsplit(":", 1)[-1]
            if tail.isdigit():
                return 5900 + int(tail)
        return None

    def _create_ephemeral_novnc_token(self, *, target_port: int, target_host: str = "127.0.0.1") -> str:
        """Generate a single-use noVNC token valid for NOVNC_TOKEN_TTL_SECONDS.

        Tokens are stored in a JSON file read by the BeagleTokenFile websockify
        plugin.  Each token is a fresh 32-byte URL-safe random value; it expires
        30 seconds after creation and is consumed (marked used) on first lookup.
        Expired and used entries are pruned on every write.
        """
        store_path = self._novnc_console_token_store
        store_path.parent.mkdir(parents=True, exist_ok=True)
        _token_store = JsonStateStore(store_path, default_factory=dict, mode=0o600)

        # Load existing store
        raw_store = _token_store.load()
        store: dict[str, Any] = raw_store if isinstance(raw_store, dict) else {}

        # Prune expired / used entries
        now = time.time()
        store = {
            t: e
            for t, e in store.items()
            if not e.get("used") and (now - float(e.get("created_at") or 0)) <= _NOVNC_TOKEN_TTL_SECONDS
        }

        # Issue new token
        token = secrets.token_urlsafe(32)
        store[token] = {
            "host": str(target_host or "127.0.0.1"),
            "port": int(target_port),
            "created_at": now,
            "used": False,
        }

        # Write atomically with mode 600
        _token_store.save(store)
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
            token = self._create_ephemeral_novnc_token(target_port=5901, target_host=guest_ip)
        else:
            # Fall back to QEMU VGA VNC on localhost (shows TTY1 on KMS guests,
            # but at least works as a fallback during firstboot/provisioning).
            port = self._libvirt_vnc_port(vmid, domain_name)
            if port is None:
                return None
            token = self._create_ephemeral_novnc_token(target_port=port)
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
