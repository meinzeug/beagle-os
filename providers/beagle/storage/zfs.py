from __future__ import annotations

import re
from typing import Any, Callable

from core.exec.safe_subprocess import run_cmd as _run_cmd_safe
from core.virtualization.storage import SnapshotSpec, StorageClass, VolumeSpec


class ZfsStorageBackend(StorageClass):
    """StorageClass implementation backed by ZFS zvol datasets."""

    _NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
    _SUPPORTED_FORMATS = {"raw", "qcow2"}

    def __init__(
        self,
        *,
        zpool: str = "beagle",
        dataset_prefix: str = "vm",
        run_checked: Callable[[list[str]], str] | None = None,
    ) -> None:
        self._zpool = self._normalize_name(zpool, field="zpool")
        self._dataset_prefix = self._normalize_name(dataset_prefix, field="dataset_prefix")
        self._run_checked = run_checked or self._default_run_checked

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

    def _dataset_name(self, volume_name: str) -> str:
        clean = self._normalize_name(volume_name, field="name")
        return f"{self._zpool}/{self._dataset_prefix}/{clean}"

    @staticmethod
    def _snapshot_name(dataset: str, snap_name: str) -> str:
        return f"{dataset}@{snap_name}"

    def _payload(self, dataset: str, *, size_bytes: int = 0, origin: str = "", fmt: str = "raw") -> dict[str, Any]:
        name = dataset.split("/")[-1]
        return {
            "id": dataset,
            "name": name,
            "pool": self._zpool,
            "path": f"/dev/zvol/{dataset}",
            "format": fmt,
            "size_bytes": int(size_bytes),
            "origin": str(origin or ""),
            "driver": "zfs",
        }

    def create_volume(self, spec: VolumeSpec) -> dict[str, Any]:
        if int(spec.size_gib) <= 0:
            raise ValueError("size_gib must be > 0")
        fmt = self._normalize_format(spec.format)
        dataset = self._dataset_name(spec.name)
        self._run_checked(["zfs", "create", "-V", f"{int(spec.size_gib)}G", dataset])
        return self._payload(dataset, fmt=fmt)

    def delete_volume(self, volume_id: str) -> bool:
        dataset = str(volume_id or "").strip()
        if not dataset:
            raise ValueError("missing volume_id")
        self._run_checked(["zfs", "destroy", "-r", dataset])
        return True

    def resize_volume(self, volume_id: str, size_gib: int) -> dict[str, Any]:
        if int(size_gib) <= 0:
            raise ValueError("size_gib must be > 0")
        dataset = str(volume_id or "").strip()
        if not dataset:
            raise ValueError("missing volume_id")
        self._run_checked(["zfs", "set", f"volsize={int(size_gib)}G", dataset])
        return self._payload(dataset)

    def snapshot(self, spec: SnapshotSpec) -> dict[str, Any]:
        dataset = str(spec.volume_id or "").strip()
        if not dataset:
            raise ValueError("missing volume_id")
        snap_name = self._normalize_name(spec.name, field="snapshot")
        snap = self._snapshot_name(dataset, snap_name)
        self._run_checked(["zfs", "snapshot", snap])
        return {
            "ok": True,
            "volume_id": dataset,
            "name": snap_name,
            "description": str(spec.description or ""),
            "snapshot_id": snap,
        }

    def clone(self, source_volume_id: str, target_spec: VolumeSpec, *, linked: bool = True) -> dict[str, Any]:
        del linked  # ZFS clone is copy-on-write by design.
        source = str(source_volume_id or "").strip()
        if not source:
            raise ValueError("missing source_volume_id")
        target_fmt = self._normalize_format(target_spec.format)
        target_dataset = self._dataset_name(target_spec.name)
        temp_snap = self._snapshot_name(source, f"clone-{self._normalize_name(target_spec.name, field='snapshot')}")
        self._run_checked(["zfs", "snapshot", temp_snap])
        self._run_checked(["zfs", "clone", temp_snap, target_dataset])
        payload = self._payload(target_dataset, origin=source, fmt=target_fmt)
        payload["source_volume_id"] = source
        payload["linked"] = True
        return payload

    def list_volumes(self, pool_name: str = "") -> list[dict[str, Any]]:
        del pool_name
        prefix = f"{self._zpool}/{self._dataset_prefix}"
        raw = self._run_checked(["zfs", "list", "-H", "-p", "-o", "name,volsize,origin", "-t", "volume", "-r", prefix])
        volumes: list[dict[str, Any]] = []
        for line in str(raw or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split("\t")
            if len(parts) < 3:
                continue
            dataset, size_text, origin = parts[:3]
            try:
                size_bytes = int(size_text)
            except ValueError:
                size_bytes = 0
            volumes.append(self._payload(dataset, size_bytes=size_bytes, origin="" if origin == "-" else origin))
        return volumes
