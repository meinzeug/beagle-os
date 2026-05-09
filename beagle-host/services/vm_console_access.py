from __future__ import annotations

import ipaddress
import os
import secrets
import socket
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs
from urllib.parse import quote
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from core.persistence.json_state_store import JsonStateStore

import sys as _sys
_PROVIDERS_DIR = Path(__file__).resolve().parents[2] / "providers" / "beagle"
if str(_PROVIDERS_DIR) not in _sys.path:
    _sys.path.insert(0, str(_PROVIDERS_DIR))
from libvirt_runner import LibvirtRunner as _LibvirtRunner

_LIBVIRT = _LibvirtRunner()

_NOVNC_TOKEN_TTL_SECONDS: float = 30.0
_SPICE_TICKET_TTL_SECONDS: int = 30


class VmConsoleAccessService:
    def __init__(
        self,
        *,
        ensure_vm_secret: Callable[[Any], dict[str, Any]] | None,
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
        self._ensure_vm_secret = ensure_vm_secret or (lambda _vm: {})

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

    @staticmethod
    def _extract_spice_ports_from_uri(uri: str) -> tuple[int, int]:
        parsed = urlparse(str(uri or "").strip())
        port = int(parsed.port or 0)
        tls_port = 0
        query = parse_qs(parsed.query, keep_blank_values=True)
        for key in ("tls-port", "tls_port", "tlsPort"):
            values = query.get(key) or []
            for value in values:
                try:
                    candidate = int(str(value).strip() or "0")
                except ValueError:
                    candidate = 0
                if candidate > 0:
                    tls_port = candidate
                    break
            if tls_port > 0:
                break
        return port, tls_port

    def _libvirt_spice_graphics(self, vmid: int, domain_name: str | None = None) -> dict[str, Any] | None:
        from core.validation.identifiers import validate_vmid

        vmid_int = validate_vmid(vmid)
        default_domain = f"beagle-{vmid_int}"
        domain = str(domain_name or "").strip() or default_domain

        for dom in (domain, default_domain):
            try:
                raw_display = _LIBVIRT.virsh("domdisplay", dom, "--type", "spice")
            except Exception:
                raw_display = ""
            if raw_display:
                try:
                    parsed = urlparse(raw_display.strip())
                except Exception:
                    parsed = None
                if parsed and parsed.scheme == "spice":
                    port, tls_port = self._extract_spice_ports_from_uri(raw_display)
                    return {
                        "listen": str(parsed.hostname or "").strip(),
                        "port": int(port or 0),
                        "tls_port": int(tls_port or 0),
                        "password": "",
                    }

            try:
                raw_xml = _LIBVIRT.virsh("dumpxml", dom)
            except Exception:
                continue
            try:
                root = ET.fromstring(raw_xml)
            except ET.ParseError:
                continue
            graphics = root.find("./devices/graphics[@type='spice']")
            if graphics is None:
                continue
            attrs = graphics.attrib
            listen = str(attrs.get("listen") or "").strip()
            if not listen:
                listen_node = graphics.find("./listen")
                if listen_node is not None:
                    listen = str(listen_node.attrib.get("address") or "").strip()
            port = int(str(attrs.get("port") or "0") or "0")
            tls_raw = attrs.get("tlsPort") or attrs.get("tlsport") or attrs.get("tls-port") or "0"
            tls_port = int(str(tls_raw or "0") or "0")
            return {
                "listen": listen,
                "port": port,
                "tls_port": tls_port,
                "password": str(attrs.get("passwd") or ""),
            }
        return None

    @staticmethod
    def _build_spice_vv_content(
        *,
        host: str,
        vmid: int,
        title: str,
        port: int,
        tls_port: int,
        password: str,
    ) -> str:
        lines = [
            "[virt-viewer]",
            "type=spice",
            f"host={host}",
            f"title={title}",
            f"port={int(port)}",
            "delete-this-file=1",
            "fullscreen=0",
            "enable-usbredir=1",
        ]
        if int(tls_port) > 0:
            lines.append(f"tls-port={int(tls_port)}")
        if str(password or "").strip():
            lines.append(f"password={password}")
        return "\n".join(lines) + "\n"

    def _issue_ephemeral_spice_ticket(self, *, vmid: int, domain_name: str | None = None) -> str:
        from core.validation.identifiers import validate_vmid

        vmid_int = validate_vmid(vmid)
        default_domain = f"beagle-{vmid_int}"
        domain = str(domain_name or "").strip() or default_domain
        ticket = secrets.token_hex(16)
        ttl_seconds = max(1, int(_SPICE_TICKET_TTL_SECONDS))
        last_error: Exception | None = None

        for dom in (domain, default_domain):
            try:
                _LIBVIRT.virsh("qemu-monitor-command", dom, "--hmp", f"set_password spice {ticket}")
                _LIBVIRT.virsh("qemu-monitor-command", dom, "--hmp", f"expire_password spice +{ttl_seconds}")
                return ticket
            except Exception as exc:
                last_error = exc

        detail = str(last_error or "unknown error").strip()
        raise RuntimeError(f"SPICE-Ticket konnte nicht gesetzt werden: {detail}")

    def build_spice_access(self, vm: Any) -> dict[str, Any]:
        vmid = int(getattr(vm, "vmid", 0) or 0)
        node = str(getattr(vm, "node", "") or "").strip()
        host = self._public_server_name or node
        if vmid <= 0 or not host:
            return {
                "provider": self._host_provider_kind or "unknown",
                "available": False,
                "host": "",
                "port": 0,
                "tls_port": 0,
                "reason": "VM-Kontext fuer SPICE unvollstaendig.",
            }
        if self._host_provider_kind != "beagle":
            return {
                "provider": self._host_provider_kind or "unknown",
                "available": False,
                "host": "",
                "port": 0,
                "tls_port": 0,
                "reason": "SPICE ist fuer diesen Provider noch nicht implementiert.",
            }

        vm_domain = str(getattr(vm, "name", "") or "").strip() or None
        graphics = self._libvirt_spice_graphics(vmid=vmid, domain_name=vm_domain)
        if not graphics:
            return {
                "provider": "beagle",
                "available": False,
                "host": "",
                "port": 0,
                "tls_port": 0,
                "reason": "SPICE-Display der VM ist aktuell nicht verfuegbar.",
            }

        port = int(graphics.get("port") or 0)
        tls_port = int(graphics.get("tls_port") or 0)
        if port <= 0 and tls_port <= 0:
            return {
                "provider": "beagle",
                "available": False,
                "host": "",
                "port": 0,
                "tls_port": 0,
                "reason": "SPICE-Ports der VM sind aktuell nicht aktiv (laeuft die VM?).",
            }

        resolved_host = self._resolve_novnc_host(host)
        return {
            "provider": "beagle",
            "available": True,
            "host": resolved_host,
            "port": port,
            "tls_port": tls_port,
            "reason": "",
        }

    def render_spice_vv(self, vm: Any) -> tuple[bytes, str]:
        vmid = int(getattr(vm, "vmid", 0) or 0)
        name = str(getattr(vm, "name", "") or "").strip() or f"VM {vmid}"
        access = self.build_spice_access(vm)
        if not access.get("available"):
            raise ValueError(str(access.get("reason") or "SPICE ist fuer diese VM nicht verfuegbar."))

        vm_domain = str(getattr(vm, "name", "") or "").strip() or None
        try:
            # Match Proxmox behavior: issue a per-request SPICE ticket with short TTL.
            password = self._issue_ephemeral_spice_ticket(vmid=vmid, domain_name=vm_domain)
        except Exception as exc:
            raise ValueError(f"SPICE-Ticket konnte nicht erstellt werden: {exc}") from exc
        vv_text = self._build_spice_vv_content(
            host=str(access.get("host") or "").strip(),
            vmid=vmid,
            title=f"Beagle VM {vmid} ({name})",
            port=int(access.get("port") or 0),
            tls_port=int(access.get("tls_port") or 0),
            password=password,
        )
        return vv_text.encode("utf-8"), f"beagle-vm-{vmid}.vv"

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
