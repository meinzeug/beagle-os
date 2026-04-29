from __future__ import annotations

import json
from typing import Any

from core.persistence.sqlite_db import BeagleDb


class VmRepository:
    """SQLite repository for VM state rows."""

    def __init__(self, db: BeagleDb) -> None:
        self._db = db

    @staticmethod
    def _row_to_vm(row: Any) -> dict[str, Any]:
        payload = json.loads(str(row["payload_json"] or "{}"))
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("vmid", int(row["vmid"]))
        payload.setdefault("node", str(row["node_id"] or ""))
        payload.setdefault("name", str(row["name"] or ""))
        payload.setdefault("status", str(row["status"] or ""))
        payload.setdefault("pool_id", str(row["pool_id"] or ""))
        return payload

    @staticmethod
    def _normalize(vm: dict[str, Any]) -> tuple[int, str, str, str, str | None, str]:
        vmid = int(vm.get("vmid") or 0)
        if vmid <= 0:
            raise ValueError("vm.vmid must be a positive integer")
        node_id = str(vm.get("node") or vm.get("node_id") or "").strip()
        status = str(vm.get("status") or "").strip()
        name = str(vm.get("name") or vm.get("hostname") or f"vm-{vmid}").strip()
        pool_id_value = str(vm.get("pool_id") or "").strip()
        pool_id = pool_id_value or None
        payload_json = json.dumps(vm, sort_keys=True)
        return vmid, node_id, name, status, pool_id, payload_json

    def get(self, vmid: int) -> dict[str, Any] | None:
        row = self._db.connect().execute(
            """
            SELECT vmid, node_id, name, status, pool_id, payload_json
            FROM vms
            WHERE vmid = ?
            """,
            (int(vmid),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_vm(row)

    def list(self, node_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        query = (
            "SELECT vmid, node_id, name, status, pool_id, payload_json "
            "FROM vms WHERE 1=1"
        )
        params: list[Any] = []
        if node_id is not None:
            query += " AND node_id = ?"
            params.append(str(node_id))
        if status is not None:
            query += " AND status = ?"
            params.append(str(status))
        query += " ORDER BY vmid"
        rows = self._db.connect().execute(query, tuple(params)).fetchall()
        return [self._row_to_vm(row) for row in rows]

    def save(self, vm: dict[str, Any]) -> dict[str, Any]:
        vmid, node_id, name, status, pool_id, payload_json = self._normalize(vm)
        with self._db.connect():
            self._db.connect().execute(
                """
                INSERT INTO vms(vmid, node_id, name, status, pool_id, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(vmid) DO UPDATE SET
                    node_id = excluded.node_id,
                    name = excluded.name,
                    status = excluded.status,
                    pool_id = excluded.pool_id,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (vmid, node_id, name, status, pool_id, payload_json),
            )
        stored = self.get(vmid)
        if stored is None:
            raise RuntimeError(f"failed to persist vm {vmid}")
        return stored

    def delete(self, vmid: int) -> bool:
        with self._db.connect():
            cursor = self._db.connect().execute("DELETE FROM vms WHERE vmid = ?", (int(vmid),))
            return int(cursor.rowcount or 0) > 0
