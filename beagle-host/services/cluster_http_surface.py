"""Cluster + HA HTTP Surface — Plan 05 Schritt 3c.

Handles:
  GET  /api/v1/cluster/inventory
  GET  /api/v1/cluster/nodes
  GET  /api/v1/cluster/status
  GET  /api/v1/ha/status
  POST /api/v1/cluster/init
  POST /api/v1/cluster/join-token
  POST /api/v1/cluster/apply-join
  POST /api/v1/cluster/join
  POST /api/v1/ha/reconcile-failed-node
  POST /api/v1/ha/maintenance/drain

Extracted from beagle-control-plane.py (Plan 05 Schritt 3c).
"""
from __future__ import annotations

from http import HTTPStatus
from typing import Any, Callable


class ClusterHttpSurfaceService:
    _GET_PATHS = {
        "/api/v1/cluster/inventory",
        "/api/v1/cluster/nodes",
        "/api/v1/cluster/status",
        "/api/v1/ha/status",
    }
    _POST_PATHS = {
        "/api/v1/cluster/init",
        "/api/v1/cluster/join-token",
        "/api/v1/cluster/apply-join",
        "/api/v1/cluster/join",
        "/api/v1/cluster/migrate",
        "/api/v1/ha/reconcile-failed-node",
        "/api/v1/ha/maintenance/drain",
    }

    def __init__(
        self,
        *,
        cluster_membership_service: Any,
        ha_manager_service: Any,
        maintenance_service: Any,
        build_cluster_inventory: Callable[[], dict[str, Any]],
        build_ha_status_payload: Callable[[], dict[str, Any]],
        ensure_cluster_rpc_listener: Callable[[], None],
        audit_event: Callable[..., None],
        requester_identity: Callable[[], str],
        cluster_node_name: str,
        public_manager_url: str,
        public_server_name: str,
        service_name: str = "beagle-control-plane",
        utcnow: Callable[[], str],
        version: str = "",
        enqueue_job: Callable[..., Any] | None = None,
    ) -> None:
        self._cluster_membership = cluster_membership_service
        self._ha_manager = ha_manager_service
        self._maintenance = maintenance_service
        self._build_cluster_inventory = build_cluster_inventory
        self._build_ha_status = build_ha_status_payload
        self._ensure_rpc = ensure_cluster_rpc_listener
        self._audit_event = audit_event
        self._requester_identity = requester_identity
        self._cluster_node_name = str(cluster_node_name or "")
        self._public_manager_url = str(public_manager_url or "")
        self._public_server_name = str(public_server_name or "")
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")
        self._enqueue_job = enqueue_job

    @staticmethod
    def _json(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    # ------------------------------------------------------------------
    # GET routing
    # ------------------------------------------------------------------

    def handles_get(self, path: str) -> bool:
        return path in self._GET_PATHS

    def route_get(self, path: str) -> dict[str, Any] | None:
        if path in {"/api/v1/cluster/inventory", "/api/v1/cluster/nodes"}:
            self._cluster_membership.probe_and_update_member_statuses(timeout=3.0)
            return self._json(HTTPStatus.OK, self._build_cluster_inventory())

        if path == "/api/v1/cluster/status":
            self._cluster_membership.probe_and_update_member_statuses(timeout=3.0)
            return self._json(HTTPStatus.OK, {"ok": True, **self._cluster_membership.status_payload()})

        if path == "/api/v1/ha/status":
            return self._json(HTTPStatus.OK, {"ok": True, **self._build_ha_status()})

        return None

    # ------------------------------------------------------------------
    # POST routing
    # ------------------------------------------------------------------

    def handles_post(self, path: str) -> bool:
        return path in self._POST_PATHS

    def route_post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        p = json_payload or {}
        requester = self._requester_identity()

        if path == "/api/v1/cluster/init":
            try:
                result = self._cluster_membership.initialize_cluster(
                    node_name=str(p.get("node_name") or self._cluster_node_name).strip(),
                    api_url=str(p.get("api_url") or self._public_manager_url).strip(),
                    advertise_host=str(p.get("advertise_host") or self._public_server_name).strip(),
                )
                self._ensure_rpc()
            except Exception as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.CREATED, {"ok": True, **result})

        if path == "/api/v1/cluster/join-token":
            try:
                result = self._cluster_membership.create_join_token(
                    ttl_seconds=int(p.get("ttl_seconds") or 900)
                )
            except Exception as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.CREATED, {"ok": True, **result})

        if path == "/api/v1/cluster/apply-join":
            try:
                result = self._cluster_membership.apply_join_response(
                    node_name=str(p.get("node_name") or self._cluster_node_name).strip(),
                    payload=(
                        p.get("join_response")
                        if isinstance(p.get("join_response"), dict)
                        else {}
                    ),
                )
                self._ensure_rpc()
            except Exception as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.OK, {"ok": True, **result})

        if path == "/api/v1/cluster/join":
            # join is unauthenticated (token-validated internally)
            try:
                join_payload = self._cluster_membership.accept_join_request(
                    join_token=str(p.get("join_token") or "").strip(),
                    node_name=str(p.get("node_name") or "").strip(),
                    api_url=str(p.get("api_url") or "").strip(),
                    advertise_host=str(p.get("advertise_host") or "").strip(),
                    rpc_url=str(p.get("rpc_url") or "").strip(),
                )
            except Exception as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.OK, {"ok": True, **join_payload})

        if path == "/api/v1/ha/reconcile-failed-node":
            try:
                failed_node = str(p.get("failed_node") or "").strip()
                result = self._ha_manager.reconcile_failed_node(
                    failed_node=failed_node,
                    requester_identity=requester,
                )
            except Exception as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event(
                "ha.reconcile_failed_node",
                "success",
                failed_node=str(result.get("failed_node") or ""),
                handled_vm_count=int(result.get("handled_vm_count") or 0),
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **result})

        if path == "/api/v1/ha/maintenance/drain":
            try:
                result = self._maintenance.drain_node(
                    node_name=str(p.get("node_name") or "").strip(),
                    requester_identity=requester,
                )
            except Exception as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event(
                "ha.maintenance.drain",
                "success",
                node_name=str(result.get("node_name") or ""),
                handled_vm_count=int(result.get("handled_vm_count") or 0),
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **result})

        if path == "/api/v1/cluster/migrate":
            source_node = str(p.get("source_node") or "").strip()
            target_node = str(p.get("target_node") or "").strip()
            if not source_node:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "missing source_node"})
            if self._enqueue_job is not None:
                ikey = str(p.get("idempotency_key") or "").strip() or f"cluster.migrate.{source_node}.{target_node}"
                try:
                    job = self._enqueue_job(
                        "cluster.migrate",
                        {
                            "source_node": source_node,
                            "target_node": target_node,
                        },
                        idempotency_key=ikey,
                        owner=requester,
                    )
                except Exception as exc:
                    return self._json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"ok": False, "error": f"failed to enqueue cluster migrate job: {exc}"},
                    )
                self._audit_event(
                    "cluster.migrate.enqueued",
                    "success",
                    source_node=source_node,
                    target_node=target_node,
                    job_id=str(job.job_id),
                    username=requester,
                )
                return self._json(
                    HTTPStatus.ACCEPTED,
                    {
                        "ok": True,
                        "job_id": str(job.job_id),
                        "source_node": source_node,
                        "target_node": target_node,
                    },
                )
            return self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"ok": False, "error": "job queue not available"},
            )

        return None
