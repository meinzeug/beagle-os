"""Shared runtime data-root and managed subdirectory helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable


class RuntimePathsService:
    def __init__(
        self,
        *,
        preferred_data_dir: Path,
        fallback_data_dir: Path,
        chmod_path: Callable[[Path, int], None],
        mkdir_path: Callable[[Path], None],
    ) -> None:
        self._preferred_data_dir = Path(preferred_data_dir)
        self._fallback_data_dir = Path(fallback_data_dir)
        self._chmod_path = chmod_path
        self._mkdir_path = mkdir_path
        self._effective_data_dir = self._preferred_data_dir

    def _ensure_directory(self, path: Path, *, mode: int = 0o700) -> Path:
        target = Path(path)
        self._mkdir_path(target)
        try:
            self._chmod_path(target, mode)
        except OSError:
            pass
        return target

    def ensure_data_dir(self) -> Path:
        try:
            self._effective_data_dir = self._ensure_directory(self._preferred_data_dir)
        except PermissionError:
            self._effective_data_dir = self._ensure_directory(self._fallback_data_dir)
        return self._effective_data_dir

    def data_dir(self) -> Path:
        return self._effective_data_dir

    def ensure_named_dir(self, name: str, *, mode: int = 0o700) -> Path:
        return self._ensure_directory(self.data_dir() / str(name or "").strip(), mode=mode)

    def endpoints_dir(self) -> Path:
        return self.ensure_named_dir("endpoints")

    def actions_dir(self) -> Path:
        return self.ensure_named_dir("actions")

    def support_bundles_dir(self) -> Path:
        return self.ensure_named_dir("support-bundles")

    def policies_dir(self) -> Path:
        return self.ensure_named_dir("policies")
