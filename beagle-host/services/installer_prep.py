"""Installer-preparation and Sunshine-readiness helpers.

This service owns the host-side state file paths, quick Sunshine probing,
default/summary payload shaping, and the orchestration that starts the
installer-prep script in the background. The control plane keeps thin
wrapper functions so HTTP handlers do not change during the migration.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable


class InstallerPrepService:
    def __init__(
        self,
        *,
        build_profile: Callable[[Any], dict[str, Any]],
        data_dir: Callable[[], Path],
        ensure_vm_secret: Callable[[Any], dict[str, Any]],
        guest_exec_out_data: Callable[[int, str], str],
        installer_prep_script_file: Path,
        installer_profile_surface: Callable[..., dict[str, Any]],
        load_json_file: Callable[[Path, Any], Any],
        public_installer_iso_url: Callable[[], str],
        root_dir: Path,
        safe_slug: Callable[..., str],
        timestamp_age_seconds: Callable[[str], int | None],
        utcnow: Callable[[], str],
        write_json_file: Callable[..., Any],
        popen: Callable[..., Any] | None = None,
    ) -> None:
        self._build_profile = build_profile
        self._data_dir = data_dir
        self._ensure_vm_secret = ensure_vm_secret
        self._guest_exec_out_data = guest_exec_out_data
        self._installer_prep_script_file = Path(installer_prep_script_file)
        self._installer_profile_surface = installer_profile_surface
        self._load_json_file = load_json_file
        self._public_installer_iso_url = public_installer_iso_url
        self._root_dir = Path(root_dir)
        self._safe_slug = safe_slug
        self._timestamp_age_seconds = timestamp_age_seconds
        self._utcnow = utcnow
        self._write_json_file = write_json_file
        self._popen = popen or subprocess.Popen

    def prep_dir(self) -> Path:
        path = self._data_dir() / "installer-prep"
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o700)
        return path

    def state_path(self, node: str, vmid: int) -> Path:
        safe_node = self._safe_slug(node, "unknown")
        return self.prep_dir() / f"{safe_node}-{int(vmid)}.json"

    def log_path(self, node: str, vmid: int) -> Path:
        safe_node = self._safe_slug(node, "unknown")
        return self.prep_dir() / f"{safe_node}-{int(vmid)}.log"

    def load_state(self, node: str, vmid: int) -> dict[str, Any] | None:
        payload = self._load_json_file(self.state_path(node, vmid), None)
        return payload if isinstance(payload, dict) else None

    def quick_sunshine_status(self, vmid: int) -> dict[str, Any]:
        output = self._guest_exec_out_data(
            vmid,
            "binary=0; service=0; process=0; "
            "command -v sunshine >/dev/null 2>&1 && binary=1; "
            "(systemctl is-active sunshine >/dev/null 2>&1 || systemctl is-active beagle-sunshine.service >/dev/null 2>&1) && service=1; "
            "pgrep -x sunshine >/dev/null 2>&1 && process=1; "
            "printf '{\"binary\":%s,\"service\":%s,\"process\":%s}\\n' \"$binary\" \"$service\" \"$process\"",
        )
        text = output.strip().splitlines()[-1] if output.strip() else ""
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"binary": 0, "service": 0, "process": 0}
        return {
            "binary": bool(payload.get("binary")),
            "service": bool(payload.get("service")),
            "process": bool(payload.get("process")),
        }

    def default_state(self, vm: Any, sunshine_status: dict[str, Any] | None = None) -> dict[str, Any]:
        profile = self._build_profile(vm)
        profile_surface = self._installer_profile_surface(
            profile,
            vmid=vm.vmid,
            installer_iso_url=self._public_installer_iso_url(),
        )
        quick = sunshine_status if isinstance(sunshine_status, dict) else self.quick_sunshine_status(vm.vmid)
        eligible = bool(profile.get("installer_target_eligible"))
        ready = (
            eligible
            and bool(quick.get("binary"))
            and bool(quick.get("service"))
            and bool(profile.get("stream_host"))
            and bool(profile.get("moonlight_port"))
        )
        if not eligible:
            status = "unsupported"
            phase = "target"
            progress = 100
            message = str(profile.get("installer_target_message") or "Diese VM ist kein geeignetes Sunshine-Streaming-Ziel.")
        elif ready:
            status = "ready"
            phase = "complete"
            progress = 100
            message = "Sunshine ist aktiv. Das VM-spezifische USB-Installer-Skript ist sofort verfuegbar."
        else:
            status = "idle"
            phase = "inspect"
            progress = 0
            message = "Download startet zuerst die Sunshine-Pruefung und die Stream-Vorbereitung fuer diese VM."
        return {
            "vmid": vm.vmid,
            "node": vm.node,
            "status": status,
            "phase": phase,
            "progress": progress,
            "message": message,
            "updated_at": self._utcnow(),
            **profile_surface,
            "installer_target_status": "ready" if ready else ("preparing" if eligible else "unsupported"),
            "sunshine_status": {
                "binary": bool(quick.get("binary")),
                "service": bool(quick.get("service")),
                "process": bool(quick.get("process")),
            },
            "ready": ready,
        }

    def summarize_state(self, vm: Any, state: dict[str, Any] | None = None) -> dict[str, Any]:
        profile = self._build_profile(vm)
        profile_surface = self._installer_profile_surface(
            profile,
            vmid=vm.vmid,
            installer_iso_url=self._public_installer_iso_url(),
        )
        payload = dict(state) if isinstance(state, dict) else self.default_state(vm)
        quick = self.quick_sunshine_status(vm.vmid)
        payload["sunshine_status"] = {
            "binary": bool(quick.get("binary")),
            "service": bool(quick.get("service")),
            "process": bool(quick.get("process")),
        }
        payload["ready"] = str(payload.get("status", "")).strip().lower() == "ready"
        payload.setdefault("vmid", vm.vmid)
        payload.setdefault("node", vm.node)
        payload["contract_version"] = str(payload.get("contract_version") or profile_surface["contract_version"])
        payload["installer_url"] = str(payload.get("installer_url") or profile_surface["installer_url"])
        payload["live_usb_url"] = str(payload.get("live_usb_url") or profile_surface["live_usb_url"])
        payload["installer_windows_url"] = str(payload.get("installer_windows_url") or profile_surface["installer_windows_url"])
        payload["live_usb_windows_url"] = str(payload.get("live_usb_windows_url") or profile_surface["live_usb_windows_url"])
        payload["installer_iso_url"] = str(payload.get("installer_iso_url") or profile_surface["installer_iso_url"])
        payload["stream_host"] = str(payload.get("stream_host") or profile_surface["stream_host"])
        payload["moonlight_port"] = str(payload.get("moonlight_port") or profile_surface["moonlight_port"])
        payload["sunshine_api_url"] = str(payload.get("sunshine_api_url") or profile_surface["sunshine_api_url"])
        payload["installer_target_eligible"] = bool(payload.get("installer_target_eligible", profile_surface["installer_target_eligible"]))
        payload["installer_target_message"] = str(payload.get("installer_target_message") or profile_surface["installer_target_message"])
        payload["installer_target_status"] = "ready" if payload["ready"] else ("preparing" if payload["installer_target_eligible"] else "unsupported")
        return payload

    def is_running(self, state: dict[str, Any] | None) -> bool:
        if not isinstance(state, dict):
            return False
        if str(state.get("status", "")).strip().lower() != "running":
            return False
        age = self._timestamp_age_seconds(str(state.get("updated_at", "")))
        return age is None or age < 900

    def start(self, vm: Any) -> dict[str, Any]:
        state_path = self.state_path(vm.node, vm.vmid)
        log_path = self.log_path(vm.node, vm.vmid)
        state = self.load_state(vm.node, vm.vmid)
        default_state = self.default_state(vm)
        vm_secret = self._ensure_vm_secret(vm)
        if not bool(default_state.get("installer_target_eligible")):
            return self.summarize_state(vm, default_state)
        if self.is_running(state):
            return self.summarize_state(vm, state)
        if not self._installer_prep_script_file.is_file():
            raise FileNotFoundError(f"installer prep script missing: {self._installer_prep_script_file}")

        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("ab")
        env = os.environ.copy()
        env.update(
            {
                "VMID": str(vm.vmid),
                "NODE": vm.node,
                "BEAGLE_INSTALLER_PREP_STATE_FILE": str(state_path),
                "BEAGLE_SUNSHINE_DEFAULT_USER": str(vm_secret.get("sunshine_username", "")),
                "BEAGLE_SUNSHINE_DEFAULT_PASSWORD": str(vm_secret.get("sunshine_password", "")),
                "BEAGLE_SUNSHINE_DEFAULT_PIN": str(vm_secret.get("sunshine_pin", "")),
            }
        )
        try:
            self._popen(
                [str(self._installer_prep_script_file), "--vmid", str(vm.vmid), "--node", vm.node],
                cwd=str(self._root_dir),
                env=env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        finally:
            log_handle.close()

        bootstrap_state = self.summarize_state(
            vm,
            {
                "vmid": vm.vmid,
                "node": vm.node,
                "status": "running",
                "phase": "queue",
                "progress": 1,
                "message": f"Sunshine-Pruefung fuer VM {vm.vmid} wurde gestartet.",
                "requested_at": self._utcnow(),
                "started_at": self._utcnow(),
                "updated_at": self._utcnow(),
            },
        )
        self._write_json_file(state_path, bootstrap_state, mode=0o600)
        return bootstrap_state
