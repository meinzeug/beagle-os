from __future__ import annotations

import re
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable


class ControlPlaneReadSurfaceService:
    def __init__(
        self,
        *,
        build_provisioning_catalog: Callable[[], dict[str, Any]],
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
        self._build_provisioning_catalog = build_provisioning_catalog
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

    def route_get(self, path: str) -> dict[str, Any] | None:
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
