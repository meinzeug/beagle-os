from __future__ import annotations

import re
from typing import Any, Callable

from core.exec.safe_subprocess import run_cmd as _run_cmd_safe
from core.virtualization.storage import SnapshotSpec, StorageClass, VolumeSpec


class LvmThinStorageBackend(StorageClass):
    """StorageClass implementation backed by LVM thin volumes."""

    _NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
    _SUPPORTED_FORMATS = {"raw", "qcow2"}

    def __init__(
        self,
        *,
        volume_group: str = "beagle-vg",
        thin_pool: str = "beagle-thinpool",
        run_checked: Callable[[list[str]], str] | None = None,
    ) -> None:
        self._vg = self._normalize_name(volume_group, field="volume_group")
        self._thin_pool = self._normalize_name(thin_pool, field="thin_pool")
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

    def _lv_ref(self, lv_name: str) -> str:
        return f"{self._vg}/{lv_name}"

    def _device_path(self, lv_name: str) -> str:
        return f"/dev/{self._vg}/{lv_name}"

    def _payload(self, lv_name: str, *, size_bytes: int = 0, origin: str = "", fmt: str = "raw") -> dict[str, Any]:
        return {
            "id": self._lv_ref(lv_name),
            "name": lv_name,
            "pool": self._thin_pool,
            "path": self._device_path(lv_name),
            "format": fmt,
            "size_bytes": int(size_bytes),
            "origin": str(origin or ""),
            "driver": "lvm_thin",
        }

    def create_volume(self, spec: VolumeSpec) -> dict[str, Any]:
        if int(spec.size_gib) <= 0:
            raise ValueError("size_gib must be > 0")
        lv_name = self._normalize_name(spec.name, field="name")
        fmt = self._normalize_format(spec.format)
        self._run_checked(
            [
                "lvcreate",
                "--yes",
                "--thin",
                "-V",
                f"{int(spec.size_gib)}G",
                "-n",
                lv_name,
                self._lv_ref(str(spec.pool_name or self._thin_pool)),
            ]
        )
        return self._payload(lv_name, fmt=fmt)

    def delete_volume(self, volume_id: str) -> bool:
        lv_ref = str(volume_id or "").strip()
        if not lv_ref:
            raise ValueError("missing volume_id")
        self._run_checked(["lvremove", "--yes", lv_ref])
        return True

    def resize_volume(self, volume_id: str, size_gib: int) -> dict[str, Any]:
        if int(size_gib) <= 0:
            raise ValueError("size_gib must be > 0")
        lv_ref = str(volume_id or "").strip()
        if not lv_ref:
            raise ValueError("missing volume_id")
        self._run_checked(["lvresize", "--yes", "-L", f"{int(size_gib)}G", lv_ref])
        lv_name = lv_ref.split("/")[-1]
        return self._payload(lv_name)

    def snapshot(self, spec: SnapshotSpec) -> dict[str, Any]:
        lv_ref = str(spec.volume_id or "").strip()
        if not lv_ref:
            raise ValueError("missing volume_id")
        snap_name = self._normalize_name(spec.name, field="snapshot")
        self._run_checked(["lvcreate", "--yes", "-s", "-n", snap_name, lv_ref])
        return {
            "ok": True,
            "volume_id": lv_ref,
            "name": snap_name,
            "description": str(spec.description or ""),
            "snapshot_id": self._lv_ref(snap_name),
        }

    def clone(self, source_volume_id: str, target_spec: VolumeSpec, *, linked: bool = True) -> dict[str, Any]:
        source_ref = str(source_volume_id or "").strip()
        if not source_ref:
            raise ValueError("missing source_volume_id")
        target_name = self._normalize_name(target_spec.name, field="name")
        fmt = self._normalize_format(target_spec.format)

        if linked:
            self._run_checked(["lvcreate", "--yes", "-s", "-n", target_name, source_ref])
        else:
            if int(target_spec.size_gib) <= 0:
                raise ValueError("size_gib must be > 0")
            self._run_checked(
                [
                    "lvcreate",
                    "--yes",
                    "--thin",
                    "-V",
                    f"{int(target_spec.size_gib)}G",
                    "-n",
                    target_name,
                    self._lv_ref(str(target_spec.pool_name or self._thin_pool)),
                ]
            )
            self._run_checked(["qemu-img", "convert", "-O", "raw", self._device_path(source_ref.split("/")[-1]), self._device_path(target_name)])

        payload = self._payload(target_name, origin=source_ref, fmt=fmt)
        payload["source_volume_id"] = source_ref
        payload["linked"] = bool(linked)
        return payload

    def list_volumes(self, pool_name: str = "") -> list[dict[str, Any]]:
        del pool_name
        raw = self._run_checked(
            [
                "lvs",
                "--noheadings",
                "--units",
                "b",
                "--nosuffix",
                "-o",
                "lv_name,lv_size,pool_lv,origin,lv_attr",
                self._vg,
            ]
        )
        volumes: list[dict[str, Any]] = []
        for line in str(raw or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            parts = re.split(r"\s+", stripped)
            if len(parts) < 5:
                continue
            lv_name, lv_size, pool_lv, origin, lv_attr = parts[:5]
            if pool_lv != self._thin_pool:
                continue
            # Thin volumes usually start with 'V' (virtual) in lv_attr.
            if not lv_attr.startswith("V"):
                continue
            try:
                size_bytes = int(float(lv_size))
            except ValueError:
                size_bytes = 0
            volumes.append(self._payload(lv_name, size_bytes=size_bytes, origin=origin if origin != "-" else ""))
        return volumes
