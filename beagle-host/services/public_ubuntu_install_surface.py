from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable


class PublicUbuntuInstallSurfaceService:
    def __init__(
        self,
        *,
        cancel_scheduled_ubuntu_beagle_vm_restart: Callable[[dict[str, Any]], dict[str, Any] | None],
        finalize_ubuntu_beagle_install: Callable[..., dict[str, Any]],
        load_ubuntu_beagle_state: Callable[[str], dict[str, Any] | None],
        prepare_ubuntu_beagle_firstboot: Callable[[dict[str, Any]], dict[str, Any]],
        save_ubuntu_beagle_state: Callable[[str, dict[str, Any]], dict[str, Any]],
        service_name: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._cancel_scheduled_ubuntu_beagle_vm_restart = cancel_scheduled_ubuntu_beagle_vm_restart
        self._finalize_ubuntu_beagle_install = finalize_ubuntu_beagle_install
        self._load_ubuntu_beagle_state = load_ubuntu_beagle_state
        self._prepare_ubuntu_beagle_firstboot = prepare_ubuntu_beagle_firstboot
        self._save_ubuntu_beagle_state = save_ubuntu_beagle_state
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")

    @staticmethod
    def _json_response(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    def _envelope(self, **payload: Any) -> dict[str, Any]:
        return {
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            **payload,
        }

    def route_post(
        self,
        path: str,
        *,
        query: dict[str, list[str]],
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        match = re.match(r"^/api/v1/public/ubuntu-install/(?P<token>[A-Za-z0-9._~-]+)/complete$", path)
        if match:
            token = match.group("token")
            state = self._load_ubuntu_beagle_state(token)
            if state is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "ubuntu install token not found"})
            restart_requested = str(query.get("restart", ["1"])[0]).strip().lower() not in {"0", "false", "no", "off"}
            try:
                cleanup = self._finalize_ubuntu_beagle_install(state, restart=restart_requested)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "error": f"failed to finalize install: {exc}"},
                )
            cancelled_restart = self._cancel_scheduled_ubuntu_beagle_vm_restart(state)
            state["completed_at"] = self._utcnow()
            state["updated_at"] = self._utcnow()
            state["status"] = "completed"
            state["phase"] = "complete"
            state["message"] = (
                "Ubuntu ist installiert. Boot-Medien wurden entfernt und die VM wurde neu gestartet."
                if restart_requested
                else "Ubuntu ist installiert. Boot-Medien wurden entfernt; der Gast startet jetzt selbst sauber neu."
            )
            state["cleanup"] = cleanup
            if cancelled_restart:
                state["host_restart_cancelled"] = cancelled_restart
            self._save_ubuntu_beagle_state(token, state)
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(ubuntu_beagle_install=state),
                },
            )

        match = re.match(r"^/api/v1/public/ubuntu-install/(?P<token>[A-Za-z0-9._~-]+)/prepare-firstboot$", path)
        if match:
            token = match.group("token")
            state = self._load_ubuntu_beagle_state(token)
            if state is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "ubuntu install token not found"})
            try:
                cleanup = self._prepare_ubuntu_beagle_firstboot(state)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "error": f"failed to prepare first boot: {exc}"},
                )
            self._save_ubuntu_beagle_state(token, state)
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(ubuntu_beagle_install=state, cleanup=cleanup),
                },
            )

        match = re.match(r"^/api/v1/public/ubuntu-install/(?P<token>[A-Za-z0-9._~-]+)/failed$", path)
        if match:
            token = match.group("token")
            state = self._load_ubuntu_beagle_state(token)
            if state is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "ubuntu install token not found"})
            failure_payload = payload if isinstance(payload, dict) else {}
            state["updated_at"] = self._utcnow()
            state["failed_at"] = self._utcnow()
            state["status"] = "failed"
            state["phase"] = str(failure_payload.get("phase", "firstboot") or "firstboot")
            state["message"] = str(
                failure_payload.get("message", "Ubuntu provisioning im Gast ist fehlgeschlagen.")
                or "Ubuntu provisioning im Gast ist fehlgeschlagen."
            )
            state["error"] = str(failure_payload.get("error", "") or "")
            cancelled_restart = self._cancel_scheduled_ubuntu_beagle_vm_restart(state)
            if cancelled_restart:
                state["host_restart_cancelled"] = cancelled_restart
            self._save_ubuntu_beagle_state(token, state)
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(ubuntu_beagle_install=state),
                },
            )

        return None
