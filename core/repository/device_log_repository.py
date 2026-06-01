from __future__ import annotations

import json
from typing import Any

from core.persistence.sqlite_db import BeagleDb


class DeviceLogRepository:
    """SQLite repository for thin-client log chunks."""

    def __init__(self, db: BeagleDb) -> None:
        self._db = db

    @staticmethod
    def _row_to_entry(row: Any) -> dict[str, Any]:
        payload = json.loads(str(row["payload_json"] or "{}"))
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("entry_id", int(row["entry_id"] or 0))
        payload.setdefault("device_id", str(row["device_id"] or ""))
        payload.setdefault("source", str(row["source"] or ""))
        payload.setdefault("level", str(row["level"] or "info"))
        payload.setdefault("captured_at", str(row["captured_at"] or ""))
        payload.setdefault("content", str(row["content"] or ""))
        return payload

    @staticmethod
    def _normalize(entry: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
        device_id = str(entry.get("device_id") or "").strip()
        if not device_id:
            raise ValueError("entry.device_id is required")
        source = str(entry.get("source") or "").strip() or "unknown"
        level = str(entry.get("level") or "info").strip().lower() or "info"
        captured_at = str(entry.get("captured_at") or "").strip()
        content = str(entry.get("content") or "").rstrip()
        payload_json = json.dumps(entry, sort_keys=True)
        return device_id, source, level, captured_at, content, payload_json

    def append(self, entry: dict[str, Any]) -> dict[str, Any]:
        device_id, source, level, captured_at, content, payload_json = self._normalize(entry)
        with self._db.connect():
            cursor = self._db.connect().execute(
                """
                INSERT INTO device_logs(device_id, source, level, captured_at, content, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (device_id, source, level, captured_at, content, payload_json),
            )
            entry_id = int(cursor.lastrowid or 0)
        row = self._db.connect().execute(
            """
            SELECT entry_id, device_id, source, level, captured_at, content, payload_json
            FROM device_logs
            WHERE entry_id = ?
            """,
            (entry_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"failed to persist device log for {device_id!r}")
        return self._row_to_entry(row)

    def list(
        self,
        device_id: str,
        *,
        limit: int = 200,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT entry_id, device_id, source, level, captured_at, content, payload_json "
            "FROM device_logs WHERE device_id = ?"
        )
        params: list[Any] = [str(device_id)]
        if source is not None and str(source).strip():
            query += " AND source = ?"
            params.append(str(source).strip())
        query += " ORDER BY entry_id DESC LIMIT ?"
        params.append(max(1, int(limit)))
        rows = self._db.connect().execute(query, params).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def count(self, device_id: str) -> int:
        row = self._db.connect().execute(
            "SELECT COUNT(*) AS count FROM device_logs WHERE device_id = ?",
            (str(device_id),),
        ).fetchone()
        return int(row["count"] if row is not None else 0)

    def prune(self, device_id: str, *, keep_last: int = 500) -> int:
        keep = max(1, int(keep_last))
        with self._db.connect():
            cursor = self._db.connect().execute(
                """
                DELETE FROM device_logs
                WHERE device_id = ?
                  AND entry_id NOT IN (
                      SELECT entry_id FROM device_logs
                      WHERE device_id = ?
                      ORDER BY entry_id DESC
                      LIMIT ?
                  )
                """,
                (str(device_id), str(device_id), keep),
            )
            return int(cursor.rowcount or 0)

    def prune_older_than(self, device_id: str, *, cutoff: str) -> int:
        cutoff_value = str(cutoff or "").strip()
        if not cutoff_value:
            return 0
        with self._db.connect():
            cursor = self._db.connect().execute(
                "DELETE FROM device_logs WHERE device_id = ? AND captured_at <> '' AND captured_at < ?",
                (str(device_id), cutoff_value),
            )
            return int(cursor.rowcount or 0)