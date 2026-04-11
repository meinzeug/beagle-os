"""Guest-USB attachment and tunnel-state helpers for Beagle host VMs.

This service owns guest-side usbip/vhci parsing, attachment polling, and
the attach/detach orchestration that combines endpoint report data with the
per-VM USB tunnel secret. The control plane keeps thin wrappers so the HTTP
handler signatures and response payloads do not change during migration.
"""

from __future__ import annotations

import re
from typing import Any, Callable


class VmUsbService:
    def __init__(
        self,
        *,
        ensure_vm_secret: Callable[[Any], dict[str, Any]],
        guest_exec_out_data: Callable[[int, str], str],
        guest_exec_payload: Callable[[int, str], dict[str, Any]],
        load_endpoint_report: Callable[[str, int], dict[str, Any] | None],
        monotonic: Callable[[], float],
        shlex_quote: Callable[[str], str],
        sleep: Callable[[float], None],
        summarize_endpoint_report: Callable[[dict[str, Any]], dict[str, Any]],
        public_server_name: str,
        usb_tunnel_attach_host: str,
        usb_tunnel_user: str,
    ) -> None:
        self._ensure_vm_secret = ensure_vm_secret
        self._guest_exec_out_data = guest_exec_out_data
        self._guest_exec_payload = guest_exec_payload
        self._load_endpoint_report = load_endpoint_report
        self._monotonic = monotonic
        self._shlex_quote = shlex_quote
        self._sleep = sleep
        self._summarize_endpoint_report = summarize_endpoint_report
        self._public_server_name = str(public_server_name or "")
        self._usb_tunnel_attach_host = str(usb_tunnel_attach_host or "")
        self._usb_tunnel_user = str(usb_tunnel_user or "")

    def parse_usbip_port_output(self, output: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for raw_line in str(output or "").splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                continue
            port_match = re.match(r"Port (\d+):", line.strip())
            if port_match:
                if current:
                    items.append(current)
                current = {"port": int(port_match.group(1))}
                continue
            if current is None:
                continue
            if "Remote Bus ID" in line:
                current["busid"] = line.split("Remote Bus ID:", 1)[1].strip()
            elif "Remote bus/dev" in line:
                current["remote_device"] = line.split("Remote bus/dev", 1)[1].strip(": ").strip()
            elif "Remote Bus ID" not in line and "-> usbip" in line:
                current["device"] = line.strip()
                match = re.search(r"/([^/\s]+)\s*$", line.strip())
                if match and not current.get("busid"):
                    current["busid"] = match.group(1)
            elif "1-" in line and "usbip" not in line and not current.get("busid"):
                current["device"] = line.strip()
        if current:
            items.append(current)
        return items

    def parse_vhci_status_output(self, output: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for raw_line in str(output or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("hub ") or (not line.startswith("hs  ") and not line.startswith("ss  ")):
                continue
            parts = line.split()
            if len(parts) < 6:
                continue
            local_busid = parts[-1]
            if local_busid in {"0-0", "000000"}:
                continue
            try:
                port = int(parts[1])
            except ValueError:
                port = 0
            items.append(
                {
                    "port": port,
                    "local_busid": local_busid,
                    "device": line,
                }
            )
        return items

    def guest_usb_attachment_state(self, vmid: int) -> dict[str, Any]:
        output = self._guest_exec_out_data(int(vmid), "command -v usbip >/dev/null 2>&1 && usbip port || true")
        attached = self.parse_usbip_port_output(output)
        vhci_output = self._guest_exec_out_data(int(vmid), "cat /sys/devices/platform/vhci_hcd.0/status 2>/dev/null || true")
        vhci_attached = self.parse_vhci_status_output(vhci_output)
        return {
            "attached": attached if attached else vhci_attached,
            "attached_count": len(attached if attached else vhci_attached),
            "usbip_available": bool(
                self._guest_exec_out_data(int(vmid), "command -v usbip >/dev/null 2>&1 && echo yes || true").strip()
            ),
            "vhci_attached": vhci_attached,
        }

    def wait_for_guest_usb_attachment(self, vmid: int, busid: str, *, timeout_seconds: float) -> dict[str, Any]:
        deadline = self._monotonic() + max(1.0, timeout_seconds)
        last_state: dict[str, Any] = self.guest_usb_attachment_state(int(vmid))
        expected = str(busid).strip()
        while self._monotonic() < deadline:
            attached = last_state.get("attached", []) if isinstance(last_state, dict) else []
            if any(str(item.get("busid", "")).strip() == expected for item in attached):
                return last_state
            vhci_attached = last_state.get("vhci_attached", []) if isinstance(last_state, dict) else []
            if vhci_attached:
                return last_state
            self._sleep(1)
            last_state = self.guest_usb_attachment_state(int(vmid))
        return last_state

    def build_vm_usb_state(self, vm: Any, report: dict[str, Any] | None = None) -> dict[str, Any]:
        secret = self._ensure_vm_secret(vm)
        endpoint_payload = report if isinstance(report, dict) else (self._load_endpoint_report(vm.node, vm.vmid) or {})
        endpoint_summary = self._summarize_endpoint_report(endpoint_payload)
        guest_state = self.guest_usb_attachment_state(vm.vmid)
        return {
            "enabled": True,
            "tunnel_host": self._public_server_name,
            "attach_host": self._usb_tunnel_attach_host,
            "tunnel_user": self._usb_tunnel_user,
            "tunnel_port": int(secret.get("usb_tunnel_port", 0) or 0),
            "tunnel_state": endpoint_summary.get("usb_tunnel_state", ""),
            "device_count": endpoint_summary.get("usb_device_count", 0),
            "bound_count": endpoint_summary.get("usb_bound_count", 0),
            "devices": endpoint_summary.get("usb_devices", []),
            "attached": guest_state.get("attached", []),
            "attached_count": guest_state.get("attached_count", 0),
            "guest_usbip_available": guest_state.get("usbip_available", False),
        }

    def attach_usb_to_guest(self, vm: Any, busid: str) -> dict[str, Any]:
        secret = self._ensure_vm_secret(vm)
        tunnel_port = int(secret.get("usb_tunnel_port", 0) or 0)
        if tunnel_port <= 0:
            raise RuntimeError("missing usb tunnel port")
        escaped_busid = self._shlex_quote(str(busid))
        command = (
            "set -euo pipefail; "
            "command -v usbip >/dev/null 2>&1 || { echo 'usbip missing in guest' >&2; exit 40; }; "
            "modprobe vhci-hcd >/dev/null 2>&1 || true; "
            f"if usbip port 2>/dev/null | grep -Fq 'Remote Bus ID: {str(busid)}'; then "
            "  usbip port; "
            "  exit 0; "
            "fi; "
            "ready=0; "
            "for _attempt in $(seq 1 12); do "
            f"  if timeout 2 bash -lc 'exec 3<>/dev/tcp/{self._usb_tunnel_attach_host}/{tunnel_port}' >/dev/null 2>&1; then "
            "    ready=1; "
            "    break; "
            "  fi; "
            "  sleep 1; "
            "done; "
            "[ \"$ready\" = \"1\" ] || { echo 'usb tunnel not reachable from guest' >&2; exit 41; }; "
            f"usbip --tcp-port {tunnel_port} attach -r {self._shlex_quote(self._usb_tunnel_attach_host)} -b {escaped_busid}; "
            "usbip port"
        )
        payload = self._guest_exec_payload(vm.vmid, command, timeout_seconds=30)
        output = str(payload.get("out-data", "") or "")
        error_output = str(payload.get("err-data", "") or "").strip()
        exit_code = int(payload.get("exitcode", 1) or 1)
        guest_state = self.wait_for_guest_usb_attachment(vm.vmid, busid, timeout_seconds=8)
        attached = guest_state.get("attached", []) if isinstance(guest_state, dict) else []
        vhci_attached = guest_state.get("vhci_attached", []) if isinstance(guest_state, dict) else []
        if exit_code != 0 and not attached and not vhci_attached:
            raise RuntimeError(error_output or output or "usb attach failed")
        if not attached and not vhci_attached:
            raise RuntimeError(error_output or "usb attach completed but guest state did not confirm attachment")
        return {
            "busid": busid,
            "tunnel_port": tunnel_port,
            "attach_host": self._usb_tunnel_attach_host,
            "attached": attached or vhci_attached or self.parse_usbip_port_output(output),
            "guest_state": guest_state,
            "raw_output": output,
            "raw_error": error_output,
        }

    def detach_usb_from_guest(self, vm: Any, *, port: int | None = None, busid: str = "") -> dict[str, Any]:
        guest_state = self.guest_usb_attachment_state(vm.vmid)
        attached = guest_state.get("attached", []) if isinstance(guest_state, dict) else []
        detach_port = int(port) if port is not None else None
        if detach_port is None and busid:
            for item in attached:
                if str(item.get("busid", "")).strip() == str(busid).strip():
                    detach_port = int(item.get("port", 0) or 0)
                    break
        if detach_port is None or detach_port < 0:
            raise RuntimeError("usb device is not attached in guest")
        command = f"set -euo pipefail; usbip detach -p {int(detach_port)}; usbip port || true"
        payload = self._guest_exec_payload(vm.vmid, command, timeout_seconds=15)
        output = str(payload.get("out-data", "") or "")
        error_output = str(payload.get("err-data", "") or "").strip()
        exit_code = int(payload.get("exitcode", 1) or 1)
        post_state = self.guest_usb_attachment_state(vm.vmid)
        remaining = post_state.get("attached", []) if isinstance(post_state, dict) else []
        if busid:
            still_attached = any(str(item.get("busid", "")).strip() == str(busid).strip() for item in remaining)
        else:
            still_attached = any(int(item.get("port", -1) or -1) == int(detach_port) for item in remaining)
        if exit_code != 0 and still_attached:
            raise RuntimeError(error_output or output or "usb detach failed")
        return {
            "detached_port": int(detach_port),
            "busid": busid,
            "attached": remaining or self.parse_usbip_port_output(output),
            "raw_output": output,
            "raw_error": error_output,
        }
