from __future__ import annotations

import json
from typing import Any

from core.persistence.sqlite_db import BeagleDb


class SessionRepository:
    """SQLite repository for active and historical sessions."""

    def __init__(self, db: BeagleDb) -> None:
        self._db = db

    @staticmethod
    def _row_to_session(row: Any) -> dict[str, Any]:
        payload = json.loads(str(row["payload_json"] or "{}"))
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("session_id", str(row["session_id"] or ""))
        payload.setdefault("pool_id", str(row["pool_id"] or ""))
        payload.setdefault("user_id", str(row["user_id"] or ""))
        payload.setdefault("vmid", row["vmid"])
        payload.setdefault("node_id", str(row["node_id"] or ""))
        payload.setdefault("status", str(row["status"] or ""))
        return payload

    @staticmethod
    def _normalize(session: dict[str, Any]) -> tuple[str, str, str, int | None, str, str, str]:
        session_id = str(session.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("session.session_id is required")
        pool_id = str(session.get("pool_id") or "").strip()
        if not pool_id:
            raise ValueError("session.pool_id is required")
        user_id = str(session.get("user_id") or "").strip()
        vmid_value = int(session.get("vmid") or 0)
        vmid = vmid_value if vmid_value > 0 else None
        node_id = str(session.get("node_id") or "").strip()
        status = str(session.get("status") or "").strip()
        payload_json = json.dumps(session, sort_keys=True)
        return session_id, pool_id, user_id, vmid, node_id, status, payload_json

    def get(self, session_id: str) -> dict[str, Any] | None:
        row = self._db.connect().execute(
            """
            SELECT session_id, pool_id, user_id, vmid, node_id, status, payload_json
            FROM sessions
            WHERE session_id = ?
            """,
            (str(session_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def list(
        self,
        *,
        pool_id: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT session_id, pool_id, user_id, vmid, node_id, status, payload_json "
            "FROM sessions WHERE 1=1"
        )
        params: list[Any] = []
        if pool_id is not None:
            query += " AND pool_id = ?"
            params.append(str(pool_id))
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(str(user_id))
        if status is not None:
            query += " AND status = ?"
            params.append(str(status))
        query += " ORDER BY session_id"
        rows = self._db.connect().execute(query, tuple(params)).fetchall()
        return [self._row_to_session(row) for row in rows]

    def save(self, session: dict[str, Any]) -> dict[str, Any]:
        session_id, pool_id, user_id, vmid, node_id, status, payload_json = self._normalize(session)
        with self._db.connect():
            self._db.connect().execute(
                """
                INSERT INTO sessions(session_id, pool_id, user_id, vmid, node_id, status, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    pool_id = excluded.pool_id,
                    user_id = excluded.user_id,
                    vmid = excluded.vmid,
                    node_id = excluded.node_id,
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (session_id, pool_id, user_id, vmid, node_id, status, payload_json),
            )
        stored = self.get(session_id)
        if stored is None:
            raise RuntimeError(f"failed to persist session {session_id}")
        return stored

    def delete(self, session_id: str) -> bool:
        with self._db.connect():
            cursor = self._db.connect().execute("DELETE FROM sessions WHERE session_id = ?", (str(session_id),))
            return int(cursor.rowcount or 0) > 0
