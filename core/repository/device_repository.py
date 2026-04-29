from __future__ import annotations

import json
from typing import Any

from core.persistence.sqlite_db import BeagleDb


class DeviceRepository:
    """SQLite repository for enrolled endpoint devices."""

    def __init__(self, db: BeagleDb) -> None:
        self._db = db

    @staticmethod
    def _row_to_device(row: Any) -> dict[str, Any]:
        payload = json.loads(str(row["payload_json"] or "{}"))
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("device_id", str(row["device_id"] or ""))
        payload.setdefault("fingerprint", str(row["fingerprint"] or ""))
        payload.setdefault("hostname", str(row["hostname"] or ""))
        payload.setdefault("status", str(row["status"] or ""))
        payload.setdefault("assigned_pool_id", row["assigned_pool_id"])
        payload.setdefault("last_seen", str(row["last_seen_at"] or ""))
        return payload

    @staticmethod
    def _normalize(device: dict[str, Any]) -> tuple[str, str, str, str, str | None, str, str]:
        device_id = str(device.get("device_id") or "").strip()
        if not device_id:
            raise ValueError("device.device_id is required")
        fingerprint = str(device.get("fingerprint") or "").strip()
        hostname = str(device.get("hostname") or "").strip()
        status = str(device.get("status") or "").strip()
        assigned_pool_value = str(device.get("assigned_pool_id") or "").strip()
        assigned_pool_id = assigned_pool_value or None
        last_seen_at = str(device.get("last_seen") or device.get("last_seen_at") or "").strip()
        payload_json = json.dumps(device, sort_keys=True)
        return device_id, fingerprint, hostname, status, assigned_pool_id, last_seen_at, payload_json

    def get(self, device_id: str) -> dict[str, Any] | None:
        row = self._db.connect().execute(
            """
            SELECT device_id, fingerprint, hostname, status, assigned_pool_id, last_seen_at, payload_json
            FROM devices
            WHERE device_id = ?
            """,
            (str(device_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_device(row)

    def list(
        self,
        *,
        status: str | None = None,
        fingerprint: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT device_id, fingerprint, hostname, status, assigned_pool_id, last_seen_at, payload_json "
            "FROM devices WHERE 1=1"
        )
        params: list[Any] = []
        if status is not None:
            query += " AND status = ?"
            params.append(str(status))
        if fingerprint is not None:
            query += " AND fingerprint = ?"
            params.append(str(fingerprint))
        query += " ORDER BY device_id"
        rows = self._db.connect().execute(query, tuple(params)).fetchall()
        return [self._row_to_device(row) for row in rows]

    def save(self, device: dict[str, Any]) -> dict[str, Any]:
        device_id, fingerprint, hostname, status, assigned_pool_id, last_seen_at, payload_json = self._normalize(device)
        with self._db.connect():
            self._db.connect().execute(
                """
                INSERT INTO devices(device_id, fingerprint, hostname, status, assigned_pool_id, last_seen_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    fingerprint = excluded.fingerprint,
                    hostname = excluded.hostname,
                    status = excluded.status,
                    assigned_pool_id = excluded.assigned_pool_id,
                    last_seen_at = excluded.last_seen_at,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (device_id, fingerprint, hostname, status, assigned_pool_id, last_seen_at, payload_json),
            )
        stored = self.get(device_id)
        if stored is None:
            raise RuntimeError(f"failed to persist device {device_id}")
        return stored

    def delete(self, device_id: str) -> bool:
        with self._db.connect():
            cursor = self._db.connect().execute("DELETE FROM devices WHERE device_id = ?", (str(device_id),))
            return int(cursor.rowcount or 0) > 0
