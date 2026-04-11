"""Host-side scheduled VM restart helpers for ubuntu-beagle flows."""

from __future__ import annotations

import os
import signal
from typing import Any, Callable


class UbuntuBeagleRestartService:
    def __init__(
        self,
        *,
        default_wait_timeout_seconds: int,
        kill_process: Callable[[int, int], Any] | None = None,
        kill_process_group: Callable[[int, int], Any] | None = None,
        schedule_vm_restart_after_stop: Callable[[int, int], int],
        utcnow: Callable[[], str],
    ) -> None:
        self._default_wait_timeout_seconds = int(default_wait_timeout_seconds)
        self._kill_process = kill_process or os.kill
        self._kill_process_group = kill_process_group or os.killpg
        self._schedule_vm_restart_after_stop = schedule_vm_restart_after_stop
        self._utcnow = utcnow

    def schedule(self, vmid: int, *, wait_timeout_seconds: int | None = None) -> dict[str, Any]:
        wait_timeout = max(60, int(wait_timeout_seconds or self._default_wait_timeout_seconds))
        pid = self._schedule_vm_restart_after_stop(int(vmid), wait_timeout)
        return {
            "vmid": int(vmid),
            "pid": int(pid),
            "wait_timeout_seconds": wait_timeout,
            "scheduled_at": self._utcnow(),
        }

    def ensure_restart_state(self, state: dict[str, Any], vmid: int) -> dict[str, Any]:
        restart_state = state.get("host_restart") if isinstance(state.get("host_restart"), dict) else None
        if self.restart_running(restart_state):
            return dict(restart_state or {})
        restart_state = self.schedule(int(vmid))
        state["host_restart"] = restart_state
        return restart_state

    def restart_running(self, restart_state: dict[str, Any] | None) -> bool:
        pid = self._restart_pid(restart_state)
        if pid <= 0:
            return False
        try:
            self._kill_process(pid, 0)
        except OSError:
            return False
        return True

    def cancel(self, state: dict[str, Any]) -> dict[str, Any] | None:
        restart_state = state.get("host_restart") if isinstance(state.get("host_restart"), dict) else None
        if not restart_state:
            return None
        pid = self._restart_pid(restart_state)
        result = dict(restart_state)
        result["cancelled_at"] = self._utcnow()
        if pid <= 0:
            state.pop("host_restart", None)
            return result
        try:
            self._kill_process_group(pid, signal.SIGTERM)
            result["cancelled"] = True
        except ProcessLookupError:
            result["cancelled"] = False
            result["reason"] = "not-running"
        except OSError as exc:
            result["cancelled"] = False
            result["reason"] = str(exc)
        state.pop("host_restart", None)
        return result

    @staticmethod
    def _restart_pid(restart_state: dict[str, Any] | None) -> int:
        if not isinstance(restart_state, dict):
            return 0
        try:
            return int(restart_state.get("pid", 0) or 0)
        except (TypeError, ValueError):
            return 0
