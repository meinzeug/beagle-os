"""Shared subprocess execution helpers for host-side runtime code."""

from __future__ import annotations

import json
import subprocess
from typing import Any, Callable


class RuntimeExecService:
    def __init__(
        self,
        *,
        default_timeout_seconds: float,
        default_timeout_sentinel: object,
        run_subprocess: Callable[..., Any] | None = None,
    ) -> None:
        self._default_timeout_seconds = float(default_timeout_seconds)
        self._default_timeout_sentinel = default_timeout_sentinel
        self._run_subprocess = run_subprocess or subprocess.run

    def run_json(self, command: list[str], *, timeout: float | None | object) -> Any:
        try:
            result = self._run_subprocess(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self._normalize_timeout(timeout),
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        try:
            return json.loads(result.stdout or "null")
        except json.JSONDecodeError:
            return None

    def run_text(self, command: list[str], *, timeout: float | None | object) -> str:
        try:
            result = self._run_subprocess(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self._normalize_timeout(timeout),
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ""
        return result.stdout

    def run_checked(self, command: list[str], *, timeout: float | None | object) -> str:
        result = self._run_subprocess(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=self._normalize_timeout(timeout),
        )
        return result.stdout

    def _normalize_timeout(self, timeout: float | None | object) -> float | None:
        if timeout is self._default_timeout_sentinel:
            return self._default_timeout_seconds
        return timeout if isinstance(timeout, (int, float)) or timeout is None else self._default_timeout_seconds
