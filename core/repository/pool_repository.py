from __future__ import annotations

import json
from typing import Any

from core.persistence.sqlite_db import BeagleDb


class PoolRepository:
    """SQLite repository for Desktop Pool rows."""

    def __init__(self, db: BeagleDb) -> None:
        self._db = db

    @staticmethod
    def _row_to_pool(row: Any) -> dict[str, Any]:
        payload = json.loads(str(row["payload_json"] or "{}"))
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("pool_id", str(row["pool_id"] or ""))
        payload.setdefault("display_name", str(row["display_name"] or ""))
        payload.setdefault("template_id", str(row["template_id"] or ""))
        payload.setdefault("status", str(row["status"] or ""))
        return payload

    @staticmethod
    def _normalize(pool: dict[str, Any]) -> tuple[str, str, str, str, str]:
        pool_id = str(pool.get("pool_id") or "").strip()
        if not pool_id:
            raise ValueError("pool.pool_id is required")
        display_name = str(
            pool.get("display_name") or pool.get("name") or pool_id
        ).strip()
        template_id = str(pool.get("template_id") or "").strip()
        status = str(pool.get("status") or "active").strip()
        payload_json = json.dumps(pool, sort_keys=True)
        return pool_id, display_name, template_id, status, payload_json

    def get(self, pool_id: str) -> dict[str, Any] | None:
        row = self._db.connect().execute(
            """
            SELECT pool_id, display_name, template_id, status, payload_json
            FROM pools
            WHERE pool_id = ?
            """,
            (str(pool_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_pool(row)

    def list(
        self,
        *,
        status: str | None = None,
        template_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT pool_id, display_name, template_id, status, payload_json FROM pools WHERE 1=1"
        params: list[Any] = []
        if status is not None:
            query += " AND status = ?"
            params.append(str(status))
        if template_id is not None:
            query += " AND template_id = ?"
            params.append(str(template_id))
        query += " ORDER BY pool_id"
        rows = self._db.connect().execute(query, params).fetchall()
        return [self._row_to_pool(r) for r in rows]

    def save(self, pool: dict[str, Any]) -> dict[str, Any]:
        pool_id, display_name, template_id, status, payload_json = self._normalize(pool)
        with self._db.connect():
            self._db.connect().execute(
                """
                INSERT INTO pools (pool_id, display_name, template_id, status, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(pool_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    template_id  = excluded.template_id,
                    status       = excluded.status,
                    payload_json = excluded.payload_json,
                    updated_at   = CURRENT_TIMESTAMP
                """,
                (pool_id, display_name, template_id, status, payload_json),
            )
        stored = self.get(pool_id)
        if stored is None:
            raise RuntimeError(f"failed to persist pool {pool_id!r}")
        return stored

    def delete(self, pool_id: str) -> bool:
        with self._db.connect():
            cursor = self._db.connect().execute(
                "DELETE FROM pools WHERE pool_id = ?",
                (str(pool_id),),
            )
            return int(cursor.rowcount or 0) > 0
