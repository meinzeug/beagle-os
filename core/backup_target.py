"""BackupTarget protocol and factory for Beagle backup storage backends."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BackupTarget(Protocol):
    """Storage backend protocol for Beagle backup chunks / snapshots."""

    def write_chunk(self, chunk_id: str, data: bytes) -> None:
        """Write a data chunk identified by chunk_id to the target store."""
        ...

    def read_chunk(self, chunk_id: str) -> bytes:
        """Read a data chunk identified by chunk_id from the target store."""
        ...

    def list_snapshots(self, *, prefix: str = "") -> list[dict[str, Any]]:
        """List available snapshots.

        Each entry has at least: snapshot_id (str), size (int), modified (float | str).
        """
        ...

    def delete_snapshot(self, snapshot_id: str) -> None:
        """Delete a snapshot / chunk from the target store."""
        ...


def make_target(config: dict[str, Any]) -> BackupTarget:
    """Factory: create a BackupTarget implementation from a config dict.

    Required key: 'type' — one of 'local', 'nfs', 's3'.
    Additional keys depend on the type (see individual implementations).
    """
    kind = str(config.get("type") or "local").lower()
    if kind == "local":
        from core.backup_targets.local import LocalBackupTarget  # noqa: PLC0415
        return LocalBackupTarget(base_path=str(config.get("path") or "/var/backups/beagle"))
    if kind == "nfs":
        from core.backup_targets.nfs import NfsBackupTarget  # noqa: PLC0415
        return NfsBackupTarget(mount_point=str(config.get("mount_point") or "/mnt/beagle-backup"))
    if kind == "s3":
        from core.backup_targets.s3 import S3BackupTarget  # noqa: PLC0415
        return S3BackupTarget(
            bucket=str(config.get("bucket") or ""),
            prefix=str(config.get("prefix") or "beagle-backup/"),
            endpoint_url=config.get("endpoint_url") or None,
            access_key=config.get("access_key") or None,
            secret_key=config.get("secret_key") or None,
            encryption_key=config.get("encryption_key") or None,
        )
    raise ValueError(f"Unknown backup target type: {kind!r}")
