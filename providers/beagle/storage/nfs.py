from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from core.exec.safe_subprocess import run_cmd as _run_cmd_safe
from core.virtualization.storage import SnapshotSpec, StorageClass, VolumeSpec


class NfsStorageBackend(StorageClass):
    """StorageClass implementation backed by an NFS mount path."""

    _NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
    _SUPPORTED_FORMATS = {"qcow2", "raw"}

    def __init__(
        self,
        *,
        mount_path: str | Path = "/mnt/beagle-nfs",
        default_pool: str = "nfs",
        run_checked: Callable[[list[str]], str] | None = None,
        is_mountpoint: Callable[[Path], bool] | None = None,
    ) -> None:
        self._mount_path = Path(str(mount_path)).expanduser().resolve()
        self._default_pool = self._normalize_name(default_pool, field="pool")
        self._run_checked = run_checked or self._default_run_checked
        self._is_mountpoint = is_mountpoint or (lambda p: p.is_mount())

    @staticmethod
    def _default_run_checked(command: list[str]) -> str:
        result = _run_cmd_safe(command, check=True)
        return str(result.stdout or "").strip()

    def _normalize_name(self, value: str, *, field: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"missing {field}")
        if not self._NAME_PATTERN.fullmatch(normalized):
            raise ValueError(f"invalid {field}: {normalized}")
        return normalized

    def _normalize_format(self, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in self._SUPPORTED_FORMATS:
            raise ValueError(f"unsupported volume format: {value}")
        return normalized

    def _require_mount(self) -> None:
        if not self._mount_path.exists():
            raise FileNotFoundError(f"nfs mount path missing: {self._mount_path}")
        if not self._mount_path.is_dir():
            raise NotADirectoryError(f"nfs mount path is not a directory: {self._mount_path}")
        if not self._is_mountpoint(self._mount_path):
            raise RuntimeError(f"nfs mount path is not mounted: {self._mount_path}")

    def _pool_dir(self, pool_name: str) -> Path:
        pool = self._normalize_name(pool_name, field="pool")
        return self._mount_path / pool

    def _resolve_volume_path(self, volume_id: str) -> Path:
        candidate = Path(str(volume_id or "").strip())
        if not candidate.is_absolute():
            candidate = (self._mount_path / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if not candidate.is_relative_to(self._mount_path):
            raise ValueError("volume path escapes nfs mount_path")
        return candidate

    @staticmethod
    def _volume_payload(path: Path) -> dict[str, Any]:
        fmt = str(path.suffix or "").lstrip(".").lower() or "qcow2"
        size = int(path.stat().st_size) if path.exists() else 0
        return {
            "id": str(path),
            "name": path.stem,
            "pool": path.parent.name,
            "path": str(path),
            "format": fmt,
            "size_bytes": size,
            "driver": "nfs",
        }

    def create_volume(self, spec: VolumeSpec) -> dict[str, Any]:
        self._require_mount()
        if int(spec.size_gib) <= 0:
            raise ValueError("size_gib must be > 0")
        name = self._normalize_name(spec.name, field="name")
        pool = self._normalize_name(spec.pool_name or self._default_pool, field="pool")
        fmt = self._normalize_format(spec.format)
        pool_dir = self._pool_dir(pool)
        pool_dir.mkdir(parents=True, exist_ok=True)
        path = pool_dir / f"{name}.{fmt}"
        if path.exists():
            raise FileExistsError(f"volume already exists: {path}")
        self._run_checked(["qemu-img", "create", "-f", fmt, str(path), f"{int(spec.size_gib)}G"])
        return self._volume_payload(path)

    def delete_volume(self, volume_id: str) -> bool:
        self._require_mount()
        path = self._resolve_volume_path(volume_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def resize_volume(self, volume_id: str, size_gib: int) -> dict[str, Any]:
        self._require_mount()
        if int(size_gib) <= 0:
            raise ValueError("size_gib must be > 0")
        path = self._resolve_volume_path(volume_id)
        if not path.exists():
            raise FileNotFoundError(f"volume not found: {path}")
        self._run_checked(["qemu-img", "resize", str(path), f"{int(size_gib)}G"])
        return self._volume_payload(path)

    def snapshot(self, spec: SnapshotSpec) -> dict[str, Any]:
        self._require_mount()
        path = self._resolve_volume_path(spec.volume_id)
        if not path.exists():
            raise FileNotFoundError(f"volume not found: {path}")
        snap_name = self._normalize_name(spec.name, field="snapshot")
        self._run_checked(["qemu-img", "snapshot", "-c", snap_name, str(path)])
        return {
            "ok": True,
            "volume_id": str(path),
            "name": snap_name,
            "description": str(spec.description or ""),
        }

    def clone(self, source_volume_id: str, target_spec: VolumeSpec, *, linked: bool = True) -> dict[str, Any]:
        self._require_mount()
        source = self._resolve_volume_path(source_volume_id)
        if not source.exists():
            raise FileNotFoundError(f"source volume not found: {source}")
        name = self._normalize_name(target_spec.name, field="name")
        pool = self._normalize_name(target_spec.pool_name or self._default_pool, field="pool")
        fmt = self._normalize_format(target_spec.format)
        target_dir = self._pool_dir(pool)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{name}.{fmt}"
        if target.exists():
            raise FileExistsError(f"target volume already exists: {target}")

        if linked:
            self._run_checked(["qemu-img", "create", "-f", fmt, "-b", str(source), str(target)])
        else:
            self._run_checked(["qemu-img", "convert", "-O", fmt, str(source), str(target)])

        payload = self._volume_payload(target)
        payload["source_volume_id"] = str(source)
        payload["linked"] = bool(linked)
        return payload

    def list_volumes(self, pool_name: str = "") -> list[dict[str, Any]]:
        self._require_mount()
        if pool_name:
            pool_dirs = [self._pool_dir(pool_name)]
        else:
            pool_dirs = [path for path in self._mount_path.iterdir() if path.is_dir()]

        volumes: list[dict[str, Any]] = []
        for pool_dir in pool_dirs:
            if not pool_dir.exists() or not pool_dir.is_dir():
                continue
            for path in sorted(pool_dir.iterdir()):
                if not path.is_file():
                    continue
                fmt = str(path.suffix or "").lstrip(".").lower()
                if fmt not in self._SUPPORTED_FORMATS:
                    continue
                volumes.append(self._volume_payload(path))
        return volumes
