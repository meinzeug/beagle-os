"""Persistence and summarization helpers for the ubuntu-beagle installer flow.

This service owns the on-disk representation of in-progress and historical
ubuntu-beagle provisioning runs and knows how to shape them into the HTTP
summary the control plane exposes. Collaborators (data dir, json I/O, slug
helper, default profile id) are injected through the constructor so the
service stays agnostic of the Proxmox control plane's module layout.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable


class UbuntuBeagleStateService:
    def __init__(
        self,
        *,
        data_dir: Callable[[], Path],
        load_json_file: Callable[..., Any],
        write_json_file: Callable[..., Any],
        safe_slug: Callable[..., str],
        ubuntu_beagle_profile_id: str,
    ) -> None:
        self._data_dir = data_dir
        self._load_json_file = load_json_file
        self._write_json_file = write_json_file
        self._safe_slug = safe_slug
        self._ubuntu_beagle_profile_id = ubuntu_beagle_profile_id

    def tokens_dir(self) -> Path:
        path = self._data_dir() / "ubuntu-beagle-install"
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o700)
        return path

    def token_path(self, token: str) -> Path:
        return self.tokens_dir() / f"{self._safe_slug(token, 'token')}.json"

    def load(self, token: str) -> dict[str, Any] | None:
        payload = self._load_json_file(self.token_path(token), None)
        return payload if isinstance(payload, dict) else None

    def save(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._write_json_file(self.token_path(token), dict(payload), mode=0o600)
        return payload

    def summarize(
        self,
        payload: dict[str, Any],
        *,
        include_credentials: bool = False,
    ) -> dict[str, Any]:
        state = dict(payload) if isinstance(payload, dict) else {}
        status = str(state.get("status", "")).strip().lower()
        phase = str(state.get("phase", "")).strip()
        message = str(state.get("message", "")).strip()
        if not status:
            if state.get("failed_at") or state.get("error"):
                status = "failed"
                phase = phase or "beagle-create"
                message = message or "Historischer Provisioning-Lauf ist fehlgeschlagen."
            elif state.get("completed_at"):
                status = "completed"
                phase = phase or "complete"
                message = message or "Historischer Provisioning-Lauf wurde abgeschlossen."
            elif state.get("started"):
                status = "installing"
                phase = phase or "autoinstall"
                message = message or "Ubuntu wird installiert."
            else:
                status = "created"
                phase = phase or "awaiting-start"
                message = message or "VM ist angelegt und wartet auf den Start."
        summary = {
            "token": str(state.get("token", "")).strip(),
            "vmid": int(state.get("vmid", 0) or 0),
            "node": str(state.get("node", "")).strip(),
            "name": str(state.get("name", "")).strip(),
            "hostname": str(state.get("hostname", "")).strip(),
            "os_profile": str(state.get("os_profile", self._ubuntu_beagle_profile_id)).strip()
            or self._ubuntu_beagle_profile_id,
            "guest_user": str(state.get("guest_user", "")).strip(),
            "status": status,
            "phase": phase,
            "message": message,
            "started": bool(state.get("started", False)),
            "created_at": str(state.get("created_at", "")).strip(),
            "updated_at": str(state.get("updated_at", "")).strip(),
            "completed_at": str(state.get("completed_at", "")).strip(),
            "failed_at": str(state.get("failed_at", "")).strip(),
            "error": str(state.get("error", "")).strip(),
            "disk_storage": str(state.get("disk_storage", "")).strip(),
            "iso_storage": str(state.get("iso_storage", "")).strip(),
            "bridge": str(state.get("bridge", "")).strip(),
            "public_stream": state.get("public_stream")
            if isinstance(state.get("public_stream"), dict)
            else None,
            "cleanup": state.get("cleanup") if isinstance(state.get("cleanup"), dict) else None,
            "host_restart": state.get("host_restart")
            if isinstance(state.get("host_restart"), dict)
            else None,
            "host_restart_cancelled": state.get("host_restart_cancelled")
            if isinstance(state.get("host_restart_cancelled"), dict)
            else None,
        }
        if include_credentials:
            summary["credentials"] = {
                "guest_user": str(state.get("guest_user", "")).strip(),
                "guest_password": str(state.get("guest_password", "")).strip(),
                "sunshine_user": str(state.get("sunshine_user", "")).strip(),
                "sunshine_password": str(state.get("sunshine_password", "")).strip(),
            }
        return summary

    def list_all(self, *, include_credentials: bool = False) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.tokens_dir().glob("*.json")):
            payload = self._load_json_file(path, None)
            if not isinstance(payload, dict):
                continue
            items.append(self.summarize(payload, include_credentials=include_credentials))
        items.sort(
            key=lambda item: (str(item.get("created_at", "")), int(item.get("vmid", 0))),
            reverse=True,
        )
        return items

    def latest_for_vmid(
        self,
        vmid: int,
        *,
        include_credentials: bool = False,
    ) -> dict[str, Any] | None:
        target = int(vmid)
        for item in self.list_all(include_credentials=include_credentials):
            if int(item.get("vmid", 0) or 0) == target:
                return item
        return None
