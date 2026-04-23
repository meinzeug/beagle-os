"""NfsBackupTarget — delegates to LocalBackupTarget on a pre-mounted NFS share."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.backup_targets.local import LocalBackupTarget


class NfsBackupTarget:
    """BackupTarget backed by a pre-mounted NFS share.

    The operator is responsible for mounting the NFS share before backups run
    (e.g. via /etc/fstab or a systemd mount unit). This class validates that
    the mount point directory is accessible and then delegates all I/O to a
    LocalBackupTarget rooted at the mount point.
    """

    def __init__(self, *, mount_point: str) -> None:
        mp = str(mount_point or "").strip()
        if not mp.startswith("/"):
            raise ValueError("NFS mount_point must be an absolute path")
        if ".." in mp:
            raise ValueError("NFS mount_point must not contain '..'")
        self._mount_point = mp
        self._local = LocalBackupTarget(base_path=mp)

    def _assert_mounted(self) -> None:
        if not Path(self._mount_point).is_dir():
            raise RuntimeError(
                f"NFS mount point not available: {self._mount_point!r}. "
                "Ensure the NFS share is mounted before running backups."
            )

    def write_chunk(self, chunk_id: str, data: bytes) -> None:
        self._assert_mounted()
        self._local.write_chunk(chunk_id, data)

    def read_chunk(self, chunk_id: str) -> bytes:
        self._assert_mounted()
        return self._local.read_chunk(chunk_id)

    def list_snapshots(self, *, prefix: str = "") -> list[dict[str, Any]]:
        self._assert_mounted()
        return self._local.list_snapshots(prefix=prefix)

    def delete_snapshot(self, snapshot_id: str) -> None:
        self._assert_mounted()
        self._local.delete_snapshot(snapshot_id)
