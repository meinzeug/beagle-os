from __future__ import annotations

import json
from typing import Any

from core.persistence.sqlite_db import BeagleDb


class GpuRepository:
    """SQLite repository for GPU device rows."""

    def __init__(self, db: BeagleDb) -> None:
        self._db = db

    @staticmethod
    def _row_to_gpu(row: Any) -> dict[str, Any]:
        payload = json.loads(str(row["payload_json"] or "{}"))
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("gpu_id", str(row["gpu_id"] or ""))
        payload.setdefault("node_id", str(row["node_id"] or ""))
        payload.setdefault("pci_address", str(row["pci_address"] or ""))
        payload.setdefault("status", str(row["status"] or ""))
        # vmid may be None if unassigned
        vmid = row["vmid"]
        payload.setdefault("vmid", int(vmid) if vmid is not None else None)
        return payload

    @staticmethod
    def _normalize(gpu: dict[str, Any]) -> tuple[str, str, str, str, int | None, str]:
        gpu_id = str(gpu.get("gpu_id") or "").strip()
        if not gpu_id:
            raise ValueError("gpu.gpu_id is required")
        pci_address = str(
            gpu.get("pci_address") or gpu.get("pci_addr") or ""
        ).strip()
        if not pci_address:
            # Derive from gpu_id if it has the "node_id:pci_addr" format,
            # otherwise fall back to gpu_id itself (guaranteed unique per row).
            pci_address = gpu_id
        node_id = str(gpu.get("node_id") or "").strip()
        # Derive status from current_assignment if not set directly
        status = str(gpu.get("status") or "").strip()
        if not status:
            assignment = str(gpu.get("current_assignment") or "").strip()
            status = "assigned" if assignment else "available"
        vmid_raw = gpu.get("vmid")
        vmid: int | None
        if vmid_raw in (None, "", 0):
            vmid = None
        else:
            try:
                vmid = int(str(vmid_raw))
            except (TypeError, ValueError):
                vmid = None
        payload_json = json.dumps(gpu, sort_keys=True)
        return gpu_id, pci_address, node_id, status, vmid, payload_json

    def get(self, gpu_id: str) -> dict[str, Any] | None:
        row = self._db.connect().execute(
            """
            SELECT gpu_id, pci_address, node_id, status, vmid, payload_json
            FROM gpus
            WHERE gpu_id = ?
            """,
            (str(gpu_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_gpu(row)

    def list(
        self,
        *,
        node_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT gpu_id, pci_address, node_id, status, vmid, payload_json FROM gpus WHERE 1=1"
        params: list[Any] = []
        if node_id is not None:
            query += " AND node_id = ?"
            params.append(str(node_id))
        if status is not None:
            query += " AND status = ?"
            params.append(str(status))
        query += " ORDER BY gpu_id"
        rows = self._db.connect().execute(query, params).fetchall()
        return [self._row_to_gpu(r) for r in rows]

    def save(self, gpu: dict[str, Any]) -> dict[str, Any]:
        gpu_id, pci_address, node_id, status, vmid, payload_json = self._normalize(gpu)
        with self._db.connect():
            self._db.connect().execute(
                """
                INSERT INTO gpus (gpu_id, pci_address, node_id, status, vmid, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(gpu_id) DO UPDATE SET
                    pci_address  = excluded.pci_address,
                    node_id      = excluded.node_id,
                    status       = excluded.status,
                    vmid         = excluded.vmid,
                    payload_json = excluded.payload_json,
                    updated_at   = CURRENT_TIMESTAMP
                """,
                (gpu_id, pci_address, node_id, status, vmid, payload_json),
            )
        stored = self.get(gpu_id)
        if stored is None:
            raise RuntimeError(f"failed to persist gpu {gpu_id!r}")
        return stored

    def delete(self, gpu_id: str) -> bool:
        with self._db.connect():
            cursor = self._db.connect().execute(
                "DELETE FROM gpus WHERE gpu_id = ?",
                (str(gpu_id),),
            )
            return int(cursor.rowcount or 0) > 0
