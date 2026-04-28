from __future__ import annotations

import re
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs


class ControlPlaneReadSurfaceService:
    def __init__(
        self,
        *,
        build_budget_alerts_payload: Callable[[str], list[dict[str, Any]]],
        build_chargeback_payload: Callable[[str, str | None], dict[str, Any]],
        build_cost_model_payload: Callable[[], dict[str, Any]],
        build_energy_csrd_payload: Callable[[int, int], dict[str, Any]],
        build_energy_config_payload: Callable[[], dict[str, Any]],
        build_energy_nodes_payload: Callable[[], list[dict[str, Any]]],
        build_energy_rankings_payload: Callable[[], dict[str, list[dict[str, Any]]]],
        build_energy_trend_payload: Callable[[int], list[dict[str, Any]]],
        build_provisioning_catalog: Callable[[], dict[str, Any]],
        build_scheduler_config_payload: Callable[[], dict[str, Any]],
        build_scheduler_insights_payload: Callable[[], dict[str, Any]],
        execute_cost_model_update: Callable[[dict[str, Any]], dict[str, Any]],
        execute_scheduler_migration: Callable[[int, str, str], dict[str, Any]],
        execute_scheduler_rebalance: Callable[[str], dict[str, Any]],
        execute_energy_config_update: Callable[[dict[str, Any]], dict[str, Any]],
        execute_scheduler_config_update: Callable[[dict[str, Any]], dict[str, Any]],
        find_support_bundle_metadata: Callable[[str], dict[str, Any] | None],
        latest_ubuntu_beagle_state_for_vmid: Callable[..., dict[str, Any] | None],
        list_endpoint_reports: Callable[[], list[dict[str, Any]]],
        list_policies: Callable[[], list[dict[str, Any]]],
        load_policy: Callable[[str], dict[str, Any] | None],
        service_name: str,
        summarize_endpoint_report: Callable[[dict[str, Any]], dict[str, Any]],
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._build_budget_alerts_payload = build_budget_alerts_payload
        self._build_chargeback_payload = build_chargeback_payload
        self._build_cost_model_payload = build_cost_model_payload
        self._build_energy_csrd_payload = build_energy_csrd_payload
        self._build_energy_config_payload = build_energy_config_payload
        self._build_energy_nodes_payload = build_energy_nodes_payload
        self._build_energy_rankings_payload = build_energy_rankings_payload
        self._build_energy_trend_payload = build_energy_trend_payload
        self._build_provisioning_catalog = build_provisioning_catalog
        self._build_scheduler_config_payload = build_scheduler_config_payload
        self._build_scheduler_insights_payload = build_scheduler_insights_payload
        self._execute_cost_model_update = execute_cost_model_update
        self._execute_scheduler_migration = execute_scheduler_migration
        self._execute_scheduler_rebalance = execute_scheduler_rebalance
        self._execute_energy_config_update = execute_energy_config_update
        self._execute_scheduler_config_update = execute_scheduler_config_update
        self._find_support_bundle_metadata = find_support_bundle_metadata
        self._latest_ubuntu_beagle_state_for_vmid = latest_ubuntu_beagle_state_for_vmid
        self._list_endpoint_reports = list_endpoint_reports
        self._list_policies = list_policies
        self._load_policy = load_policy
        self._service_name = str(service_name or "beagle-control-plane")
        self._summarize_endpoint_report = summarize_endpoint_report
        self._utcnow = utcnow
        self._version = str(version or "")

    @staticmethod
    def _json_response(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    @staticmethod
    def _bytes_response(status: HTTPStatus, body: bytes, *, content_type: str, filename: str) -> dict[str, Any]:
        return {
            "kind": "bytes",
            "status": status,
            "body": body,
            "content_type": content_type,
            "filename": filename,
        }

    def _envelope(self, **payload: Any) -> dict[str, Any]:
        return {
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            **payload,
        }

    @staticmethod
    def _query_value(query: dict[str, list[str]] | None, key: str, default: str = "") -> str:
        if not isinstance(query, dict):
            return default
        values = query.get(key)
        if not isinstance(values, list) or not values:
            return default
        return str(values[0] or default)

    @staticmethod
    def _query_int(query: dict[str, list[str]] | None, key: str, default: int) -> int:
        raw = ControlPlaneReadSurfaceService._query_value(query, key, str(default))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_query_from_path(path: str) -> tuple[str, dict[str, list[str]]]:
        if "?" not in path:
            return path, {}
        raw_path, raw_query = path.split("?", 1)
        return raw_path, parse_qs(raw_query, keep_blank_values=False)

    def route_get(self, path: str, *, query: dict[str, list[str]] | None = None) -> dict[str, Any] | None:
        path, parsed_query = self._parse_query_from_path(path)
        if query is None:
            query = parsed_query

        if path == "/api/v1/provisioning/catalog":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(catalog=self._build_provisioning_catalog()),
                },
            )

        match = re.match(r"^/api/v1/provisioning/vms/(?P<vmid>\d+)$", path)
        if match:
            state = self._latest_ubuntu_beagle_state_for_vmid(int(match.group("vmid")), include_credentials=True)
            if state is None:
                return self._json_response(
                    HTTPStatus.NOT_FOUND,
                    {"ok": False, "error": "provisioning state not found"},
                )
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(provisioning=state),
                },
            )

        if path == "/api/v1/endpoints":
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(
                    endpoints=[
                        self._summarize_endpoint_report(item)
                        for item in self._list_endpoint_reports()
                    ]
                ),
            )

        if path == "/api/v1/policies":
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(policies=self._list_policies()),
            )

        if path.startswith("/api/v1/policies/"):
            policy_name = path.rsplit("/", 1)[-1]
            policy = self._load_policy(policy_name)
            if policy is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "policy not found"})
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(policy=policy),
            )

        if path == "/api/v1/scheduler/insights":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(**self._build_scheduler_insights_payload()),
                },
            )

        if path == "/api/v1/scheduler/config":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(config=self._build_scheduler_config_payload()),
                },
            )

        if path == "/api/v1/costs/chargeback":
            month = self._query_value(query, "month")
            department = self._query_value(query, "department") or None
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(**self._build_chargeback_payload(month, department)),
                },
            )

        if path == "/api/v1/costs/model":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(**self._build_cost_model_payload()),
                },
            )

        if path == "/api/v1/costs/chargeback.csv":
            month = self._query_value(query, "month")
            department = self._query_value(query, "department") or None
            payload = self._build_chargeback_payload(month, department)
            filename_suffix = f"{month or 'current'}"
            if department:
                filename_suffix += f"_{department}"
            return self._bytes_response(
                HTTPStatus.OK,
                str(payload.get("csv") or "").encode("utf-8"),
                content_type="text/csv; charset=utf-8",
                filename=f"beagle-chargeback-{filename_suffix}.csv",
            )

        if path == "/api/v1/costs/budget-alerts":
            month = self._query_value(query, "month")
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(alerts=self._build_budget_alerts_payload(month)),
                },
            )

        if path == "/api/v1/energy/nodes":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(nodes=self._build_energy_nodes_payload()),
                },
            )

        if path == "/api/v1/energy/rankings":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(rankings=self._build_energy_rankings_payload()),
                },
            )

        if path == "/api/v1/energy/trend":
            months = max(1, min(24, self._query_int(query, "months", 6)))
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(trend=self._build_energy_trend_payload(months)),
                },
            )

        if path == "/api/v1/energy/csrd":
            year = self._query_int(query, "year", 0)
            quarter = self._query_int(query, "quarter", 0)
            if year <= 0 or quarter not in {1, 2, 3, 4}:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "year and quarter are required"},
                )
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(csrd=self._build_energy_csrd_payload(year, quarter)),
                },
            )

        if path == "/api/v1/energy/config":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(**self._build_energy_config_payload()),
                },
            )

        if path.startswith("/api/v1/support-bundles/") and path.endswith("/download"):
            bundle_id = path.split("/")[-2]
            metadata = self._find_support_bundle_metadata(bundle_id)
            if metadata is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "support bundle not found"})
            archive_path = Path(str(metadata.get("stored_path", "")))
            if not archive_path.is_file():
                return self._json_response(
                    HTTPStatus.NOT_FOUND,
                    {"ok": False, "error": "support bundle payload missing"},
                )
            return self._bytes_response(
                HTTPStatus.OK,
                archive_path.read_bytes(),
                content_type="application/gzip",
                filename=str(metadata.get("stored_filename") or archive_path.name),
            )

        return None

    def route_post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        requester: str = "",
    ) -> dict[str, Any] | None:
        payload = json_payload if isinstance(json_payload, dict) else {}

        if path == "/api/v1/scheduler/migrate":
            try:
                vm_id = int(payload.get("vm_id") or 0)
            except (TypeError, ValueError):
                vm_id = 0
            target_node = str(payload.get("target_node") or "").strip()
            if vm_id <= 0 or not target_node:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "vm_id and target_node are required"},
                )
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        migration=self._execute_scheduler_migration(vm_id, target_node, requester),
                    ),
                },
            )

        if path == "/api/v1/scheduler/rebalance":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        rebalance=self._execute_scheduler_rebalance(requester),
                    ),
                },
            )

        return None

    def route_put(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        payload = json_payload if isinstance(json_payload, dict) else {}

        if path == "/api/v1/scheduler/config":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(config=self._execute_scheduler_config_update(payload)),
                },
            )

        if path == "/api/v1/costs/model":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(**self._execute_cost_model_update(payload)),
                },
            )

        if path == "/api/v1/energy/config":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(**self._execute_energy_config_update(payload)),
                },
            )

        return None
