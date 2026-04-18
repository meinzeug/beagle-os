from __future__ import annotations

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
    def _libvirt_vnc_port(vmid: int) -> int | None:
        domain = f"beagle-{int(vmid)}"
        result = subprocess.run(
            ["virsh", "--connect", "qemu:///system", "vncdisplay", domain],
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

    def _upsert_beagle_novnc_token(self, *, vmid: int, target_port: int) -> str:
        token = f"vm-{int(vmid)}"
        line = f"{token}: 127.0.0.1:{int(target_port)}"
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

    def _beagle_novnc_url(self, *, host: str, vmid: int) -> str | None:
        port = self._libvirt_vnc_port(vmid)
        if port is None:
            return None
        token = self._upsert_beagle_novnc_token(vmid=vmid, target_port=port)
        base_path = self._novnc_path.strip()
        if not base_path.startswith("/"):
            base_path = "/" + base_path
        base_path = base_path.rstrip("/")
        token_q = quote(token, safe="")
        path_q = quote(f"beagle-novnc/websockify?token={token_q}", safe="/?=&")
        return f"https://{host}{base_path}/vnc.html?autoconnect=1&resize=scale&path={path_q}"

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
            url = self._beagle_novnc_url(host=host, vmid=vmid)
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
