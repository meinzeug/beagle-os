from __future__ import annotations

from http import HTTPStatus
from typing import Any, Callable

from core.virtualization.streaming_profile import StreamingNetworkMode


class EndpointHttpSurfaceService:
    def __init__(
        self,
        *,
        build_vm_profile: Callable[[Any], dict[str, Any]],
        dequeue_vm_actions: Callable[[str, int], list[dict[str, Any]]],
        device_registry_service: Any,
        mdm_policy_service: Any,
        attestation_service: Any,
        fleet_telemetry_service: Any | None,
        alert_service: Any | None,
        exchange_beagle_stream_client_pairing_token: Callable[[Any, dict[str, Any], str], dict[str, Any]],
        fetch_beagle_stream_server_identity: Callable[[Any, str], dict[str, Any]],
        find_vm: Callable[[int], Any | None],
        issue_beagle_stream_client_pairing_token: Callable[[Any, dict[str, Any], str], dict[str, Any]],
        pool_manager_service: Any,
        register_beagle_stream_client_certificate_on_vm: Callable[[Any, str], dict[str, Any]],
        service_name: str,
        prepare_virtual_display_on_vm: Callable[[Any, str], dict[str, Any]],
        session_manager_service: Any,
        store_action_result: Callable[[str, int, dict[str, Any]], None],
        store_support_bundle: Callable[[str, int, str, str, bytes], dict[str, Any]],
        summarize_action_result: Callable[[dict[str, Any] | None], dict[str, Any]],
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._build_vm_profile = build_vm_profile
        self._dequeue_vm_actions = dequeue_vm_actions
        self._device_registry = device_registry_service
        self._mdm_policy = mdm_policy_service
        self._attestation = attestation_service
        self._fleet_telemetry = fleet_telemetry_service
        self._alert_service = alert_service
        self._exchange_beagle_stream_client_pairing_token = exchange_beagle_stream_client_pairing_token
        self._fetch_beagle_stream_server_identity = fetch_beagle_stream_server_identity
        self._find_vm = find_vm
        self._issue_beagle_stream_client_pairing_token = issue_beagle_stream_client_pairing_token
        self._pool_manager = pool_manager_service
        self._register_beagle_stream_client_certificate_on_vm = register_beagle_stream_client_certificate_on_vm
        self._prepare_virtual_display_on_vm = prepare_virtual_display_on_vm
        self._session_manager = session_manager_service
        self._service_name = str(service_name or "beagle-control-plane")
        self._store_action_result = store_action_result
        self._store_support_bundle = store_support_bundle
        self._summarize_action_result = summarize_action_result
        self._utcnow = utcnow
        self._version = str(version or "")

    @staticmethod
    def _json_response(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    def _envelope(self, **payload: Any) -> dict[str, Any]:
        return {
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            **payload,
        }

    @staticmethod
    def _scope_matches(identity: dict[str, Any], vmid: int, node: str) -> bool:
        if not identity:
            return True
        return int(identity.get("vmid", -1)) == int(vmid) and str(identity.get("node", "")).strip() == str(node).strip()

    @staticmethod
    def handles_path(path: str) -> bool:
        return path in {
            "/api/v1/session/current",
            "/api/v1/endpoints/beagle-stream-client/register",
            "/api/v1/endpoints/beagle-stream-client/prepare-stream",
            "/api/v1/endpoints/beagle-stream-client/pair-token",
            "/api/v1/endpoints/beagle-stream-client/pair-exchange",
            "/api/v1/endpoints/actions/pull",
            "/api/v1/endpoints/actions/result",
            "/api/v1/endpoints/support-bundles/upload",
            "/api/v1/endpoints/device/sync",
            "/api/v1/endpoints/device/confirm-wiped",
        }

    @staticmethod
    def requires_json_body(path: str) -> bool:
        return path in {
            "/api/v1/endpoints/beagle-stream-client/register",
            "/api/v1/endpoints/beagle-stream-client/prepare-stream",
            "/api/v1/endpoints/beagle-stream-client/pair-token",
            "/api/v1/endpoints/beagle-stream-client/pair-exchange",
            "/api/v1/endpoints/actions/pull",
            "/api/v1/endpoints/actions/result",
            "/api/v1/endpoints/device/sync",
            "/api/v1/endpoints/device/confirm-wiped",
        }

    @staticmethod
    def requires_binary_body(path: str) -> bool:
        return path == "/api/v1/endpoints/support-bundles/upload"

    def _resolve_device_record(self, identity: dict[str, Any]) -> Any | None:
        device_id = str(identity.get("endpoint_id") or "").strip()
        hostname = str(identity.get("hostname") or "").strip()
        if device_id:
            device = self._device_registry.get_device(device_id)
            if device is not None:
                return device
        if hostname:
            return self._device_registry.get_device(hostname)
        return None

    def _wireguard_active_for_identity(self, identity: dict[str, Any]) -> bool:
        device = self._resolve_device_record(identity)
        if device is None:
            return False
        if bool(getattr(device, "vpn_active", False)):
            return True
        return bool(str(getattr(device, "wg_assigned_ip", "") or "").strip())

    def _network_mode_for_pool(self, pool_id: str) -> str:
        if not pool_id or self._pool_manager is None:
            return ""
        pool = self._pool_manager.get_pool(pool_id)
        profile = getattr(pool, "streaming_profile", None) if pool is not None else None
        mode = getattr(profile, "network_mode", "") if profile is not None else ""
        if hasattr(mode, "value"):
            return str(mode.value or "").strip().lower()
        return str(mode or "").strip().lower()

    def route_get(
        self,
        path: str,
        *,
        endpoint_identity: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        identity = endpoint_identity or {}

        if path == "/api/v1/session/current":
            session_id = str((query.get("session_id") or [""])[0] or "").strip()
            vmid_text = str((query.get("vmid") or [""])[0] or "").strip()
            try:
                vmid = int(vmid_text or identity.get("vmid") or 0)
            except (TypeError, ValueError):
                vmid = 0
            if not session_id and vmid <= 0:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "session_id or vmid is required"})

            session = self._session_manager.find_active_session(session_id=session_id, vm_id=vmid)
            if session is None and vmid > 0:
                vm = self._find_vm(vmid)
                if vm is None:
                    return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "session not found"})
                session = {
                    "session_id": session_id or f"vm:{vmid}",
                    "pool_id": "",
                    "vm_id": vmid,
                    "user_id": str(identity.get("hostname", "") or ""),
                    "current_node": str(vm.node or ""),
                    "status": "active",
                }
            elif session is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "session not found"})

            session_vmid = int(session.get("vm_id") or vmid or 0)
            vm = self._find_vm(session_vmid) if session_vmid > 0 else None
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})

            profile = self._build_vm_profile(vm) if callable(self._build_vm_profile) else {}
            stream_host = str(profile.get("stream_host", "") or "").strip()
            beagle_stream_client_port = str(profile.get("beagle_stream_client_port", "") or "").strip()
            pool_id = str(session.get("pool_id") or "").strip()
            network_mode = self._network_mode_for_pool(pool_id)
            wireguard_active = self._wireguard_active_for_identity(identity)
            if network_mode == StreamingNetworkMode.VPN_REQUIRED.value and not wireguard_active:
                return self._json_response(
                    HTTPStatus.FORBIDDEN,
                    {
                        "ok": False,
                        "error": "vpn_required: WireGuard tunnel not active",
                        **self._envelope(
                            session_id=str(session.get("session_id") or session_id or ""),
                            pool_id=pool_id,
                            vmid=session_vmid,
                            network_mode=network_mode,
                        ),
                    },
                )
            current_node = str(session.get("current_node") or vm.node or "").strip()
            reconnect_required = bool(current_node and str(identity.get("node", "")).strip() and current_node != str(identity.get("node", "")).strip())
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        session_id=str(session.get("session_id") or session_id or ""),
                        pool_id=pool_id,
                        vmid=session_vmid,
                        current_node=current_node,
                        stream_host=stream_host,
                        beagle_stream_client_port=beagle_stream_client_port,
                        reconnect_required=reconnect_required,
                        network_mode=network_mode,
                        wireguard_active=wireguard_active,
                    ),
                },
            )

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def route_post(
        self,
        path: str,
        *,
        endpoint_identity: dict[str, Any] | None,
        query: dict[str, list[str]],
        json_payload: dict[str, Any] | None = None,
        binary_payload: bytes | None = None,
    ) -> dict[str, Any]:
        identity = endpoint_identity or {}

        if path == "/api/v1/endpoints/device/confirm-wiped":
            payload = json_payload if isinstance(json_payload, dict) else {}
            device_id = str(payload.get("device_id") or identity.get("endpoint_id") or identity.get("hostname") or "").strip()
            if not device_id:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing device_id"})
            device = self._device_registry.get_device(device_id)
            if device is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
            device = self._device_registry.confirm_wiped(device_id)
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        device={
                            "device_id": str(device.device_id),
                            "hostname": str(device.hostname),
                            "status": str(device.status),
                            "last_seen": str(device.last_seen),
                        }
                    ),
                },
            )

        if path == "/api/v1/endpoints/device/sync":
            payload = json_payload if isinstance(json_payload, dict) else {}
            device_id = str(payload.get("device_id") or identity.get("endpoint_id") or identity.get("hostname") or "").strip()
            hostname = str(payload.get("hostname") or identity.get("hostname") or device_id).strip()
            if not device_id or not hostname:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing device_id or hostname"})

            hardware = payload.get("hardware") if isinstance(payload.get("hardware"), dict) else {}
            os_version = str(payload.get("os_version") or "").strip()
            vpn = payload.get("vpn") if isinstance(payload.get("vpn"), dict) else {}
            reports = payload.get("reports") if isinstance(payload.get("reports"), dict) else {}
            wipe_report = reports.get("wipe") if isinstance(reports.get("wipe"), dict) else {}
            runtime_report = reports.get("runtime") if isinstance(reports.get("runtime"), dict) else {}
            metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}

            device = self._device_registry.register_or_update_device(
                device_id,
                hostname,
                hardware,
                os_version=os_version,
                vpn_active=bool(vpn.get("active")),
                vpn_interface=str(vpn.get("interface") or "").strip(),
                wg_public_key=str(vpn.get("public_key") or "").strip(),
                wg_assigned_ip=str(vpn.get("assigned_ip") or "").strip(),
            )
            device = self._device_registry.update_heartbeat(device_id, metrics=metrics)
            if wipe_report:
                device = self._device_registry.update_wipe_report(device_id, wipe_report)
            if runtime_report:
                device = self._device_registry.update_runtime_report(device_id, runtime_report)

            anomaly_reports = []
            fired_alerts = []
            if self._fleet_telemetry is not None:
                from fleet_telemetry_service import DeviceTelemetry

                telemetry = DeviceTelemetry(
                    device_id=device_id,
                    timestamp=self._utcnow(),
                    device_type="thin_client",
                    disk_smart_ok=bool(metrics.get("disk_smart_ok", True)),
                    disk_reallocated_sectors=int(metrics.get("disk_reallocated_sectors", 0) or 0),
                    disk_pending_sectors=int(metrics.get("disk_pending_sectors", 0) or 0),
                    cpu_temp_c=float(metrics.get("cpu_temp_c", 0.0) or 0.0),
                    gpu_temp_c=float(metrics.get("gpu_temp_c", 0.0) or 0.0),
                    ram_ecc_errors=int(metrics.get("ram_ecc_errors", 0) or 0),
                    network_errors=int(metrics.get("network_errors", 0) or 0),
                    reboot_count_7d=int(metrics.get("reboot_count_7d", 0) or 0),
                    uptime_hours=float(metrics.get("uptime_hours", 0.0) or 0.0),
                )
                self._fleet_telemetry.ingest(telemetry)
                anomaly_reports = list(self._fleet_telemetry.detect_anomalies(device_id) or [])
                if self._alert_service is not None and anomaly_reports:
                    fired_alerts = list(self._alert_service.check_anomalies(device_id, anomaly_reports) or [])

            attestation_record = self._attestation.get_record(device_id)
            allowed, reason = self._attestation.is_session_allowed(device_id)
            policy = self._mdm_policy.resolve_policy(device_id, group=str(getattr(device, "group", "") or ""))

            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        device={
                            "device_id": str(device.device_id),
                            "hostname": str(device.hostname),
                            "status": str(device.status),
                            "last_seen": str(device.last_seen),
                            "location": str(device.location),
                            "group": str(device.group),
                            "last_wipe_report": dict(getattr(device, "last_wipe_report", {}) or {}),
                            "last_runtime_report": dict(getattr(device, "last_runtime_report", {}) or {}),
                        },
                        policy={
                            "policy_id": str(getattr(policy, "policy_id", "__default__") or "__default__"),
                            "name": str(getattr(policy, "name", "Default") or "Default"),
                            "allowed_networks": list(getattr(policy, "allowed_networks", []) or []),
                            "allowed_pools": list(getattr(policy, "allowed_pools", []) or []),
                            "max_resolution": str(getattr(policy, "max_resolution", "") or ""),
                            "allowed_codecs": list(getattr(policy, "allowed_codecs", []) or []),
                            "auto_update": bool(getattr(policy, "auto_update", True)),
                            "update_window_start_hour": int(getattr(policy, "update_window_start_hour", 2) or 2),
                            "update_window_end_hour": int(getattr(policy, "update_window_end_hour", 4) or 4),
                            "screen_lock_timeout_seconds": int(getattr(policy, "screen_lock_timeout_seconds", 0) or 0),
                        },
                        attestation={
                            "allowed": bool(allowed),
                            "reason": str(reason or ""),
                            "status": str(getattr(attestation_record, "status", "unknown") or "unknown"),
                            "last_checked": str(getattr(attestation_record, "last_checked", "") or ""),
                        },
                        commands={
                            "lock_screen": str(device.status) == "locked",
                            "wipe_pending": str(device.status) == "wipe_pending",
                            "device_status": str(device.status),
                        },
                        vpn={
                            "active": bool(vpn.get("active")),
                            "interface": str(vpn.get("interface") or ""),
                            "assigned_ip": str(vpn.get("assigned_ip") or ""),
                        },
                        health={
                            "anomaly_count": len(anomaly_reports),
                            "alert_count": len(self._alert_service.get_open_alerts(device_id) if self._alert_service is not None else []),
                            "new_alert_count": len(fired_alerts),
                        },
                    ),
                },
            )

        if path == "/api/v1/endpoints/beagle-stream-client/register":
            vmid = int(identity.get("vmid", 0) or 0)
            vm = self._find_vm(vmid)
            if vm is None or str(identity.get("node", "")).strip() != vm.node:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            payload = json_payload if isinstance(json_payload, dict) else {}
            client_cert_pem = str(payload.get("client_cert_pem", "")).strip()
            device_name = (
                str(payload.get("device_name", "")).strip()
                or str(identity.get("hostname", "")).strip()
                or f"beagle-vm{vmid}-client"
            )
            if not client_cert_pem or "BEGIN CERTIFICATE" not in client_cert_pem:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing client certificate"})
            result = self._register_beagle_stream_client_certificate_on_vm(vm, client_cert_pem, device_name=device_name)
            guest_user = str(result.get("guest_user", "") or "").strip()
            beagle_stream_server: dict[str, Any] = {
                "ok": False,
                "uniqueid": "",
                "server_cert_pem": "",
                "beagle_stream_server_name": "",
                "stream_port": "",
                "stdout": "",
                "stderr": "",
            }
            if bool(result.get("ok")) and guest_user:
                beagle_stream_server = self._fetch_beagle_stream_server_identity(vm, guest_user)
            overall_ok = bool(result.get("ok")) and bool(beagle_stream_server.get("ok")) and bool(
                beagle_stream_server.get("uniqueid")
            ) and bool(beagle_stream_server.get("server_cert_pem"))
            return self._json_response(
                HTTPStatus.CREATED if overall_ok else HTTPStatus.BAD_GATEWAY,
                {
                    "ok": overall_ok,
                    **self._envelope(
                        vmid=vm.vmid,
                        node=vm.node,
                        device_name=device_name,
                        guest_user=result.get("guest_user", ""),
                        stdout=result.get("stdout", ""),
                        stderr=result.get("stderr", ""),
                        beagle_stream_server={
                            "ok": bool(beagle_stream_server.get("ok")),
                            "uniqueid": beagle_stream_server.get("uniqueid", ""),
                            "server_cert_pem": beagle_stream_server.get("server_cert_pem", ""),
                            "beagle_stream_server_name": beagle_stream_server.get("beagle_stream_server_name", ""),
                            "stream_port": beagle_stream_server.get("stream_port", ""),
                            "stdout": beagle_stream_server.get("stdout", ""),
                            "stderr": beagle_stream_server.get("stderr", ""),
                        },
                    ),
                },
            )

        if path == "/api/v1/endpoints/beagle-stream-client/prepare-stream":
            vmid = int(identity.get("vmid", 0) or 0)
            vm = self._find_vm(vmid)
            if vm is None or str(identity.get("node", "")).strip() != vm.node:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})

            payload = json_payload if isinstance(json_payload, dict) else {}
            resolution = str(payload.get("resolution", "")).strip()
            if not resolution:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing resolution"})

            result = self._prepare_virtual_display_on_vm(vm, resolution)
            return self._json_response(
                HTTPStatus.OK if bool(result.get("ok")) else HTTPStatus.BAD_GATEWAY,
                {
                    "ok": bool(result.get("ok")),
                    **self._envelope(
                        vmid=vm.vmid,
                        node=vm.node,
                        resolution=resolution,
                        result=result,
                    ),
                },
            )

        if path == "/api/v1/endpoints/beagle-stream-client/pair-token":
            vmid = int(identity.get("vmid", 0) or 0)
            vm = self._find_vm(vmid)
            if vm is None or str(identity.get("node", "")).strip() != vm.node:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})

            payload = json_payload if isinstance(json_payload, dict) else {}
            device_name = (
                str(payload.get("device_name", "")).strip()
                or str(identity.get("hostname", "")).strip()
                or f"beagle-vm{vmid}-client"
            )
            try:
                issued = self._issue_beagle_stream_client_pairing_token(vm, identity, device_name)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": f"pair token issue failed: {exc}",
                        **self._envelope(vmid=vm.vmid, node=vm.node, device_name=device_name),
                    },
                )
            if not bool(issued.get("ok")):
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": str(issued.get("error", "pair token issue failed") or "pair token issue failed"),
                        **self._envelope(vmid=vm.vmid, node=vm.node, device_name=device_name),
                    },
                )
            return self._json_response(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    **self._envelope(
                        vmid=vm.vmid,
                        node=vm.node,
                        device_name=device_name,
                        pairing={
                            "token": str(issued.get("token", "") or ""),
                            "pin": str(issued.get("pin", "") or ""),
                            "expires_at": str(issued.get("expires_at", "") or ""),
                        },
                    ),
                },
            )

        if path == "/api/v1/endpoints/beagle-stream-client/pair-exchange":
            vmid = int(identity.get("vmid", 0) or 0)
            vm = self._find_vm(vmid)
            if vm is None or str(identity.get("node", "")).strip() != vm.node:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})

            payload = json_payload if isinstance(json_payload, dict) else {}
            token = str(payload.get("pairing_token", "")).strip()
            if not token:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing pairing_token"})

            try:
                exchanged = self._exchange_beagle_stream_client_pairing_token(vm, identity, token)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": f"pair exchange failed: {exc}",
                        **self._envelope(vmid=vm.vmid, node=vm.node),
                    },
                )
            if not bool(exchanged.get("ok")):
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": str(exchanged.get("error", "pair exchange failed") or "pair exchange failed"),
                        **self._envelope(vmid=vm.vmid, node=vm.node),
                    },
                )
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(vmid=vm.vmid, node=vm.node, paired=True),
                },
            )

        if path == "/api/v1/endpoints/actions/pull":
            payload = json_payload if isinstance(json_payload, dict) else {}
            try:
                vmid = int(payload.get("vmid"))
                node = str(payload.get("node", "")).strip()
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
            if not node:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing node"})
            if not self._scope_matches(identity, vmid, node):
                return self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(actions=self._dequeue_vm_actions(node, vmid)),
                },
            )

        if path == "/api/v1/endpoints/actions/result":
            payload = dict(json_payload) if isinstance(json_payload, dict) else {}
            try:
                vmid = int(payload.get("vmid"))
                node = str(payload.get("node", "")).strip()
                action_name = str(payload.get("action", "")).strip()
                action_id = str(payload.get("action_id", "")).strip()
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
            if not node or not action_name or not action_id:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "invalid payload: missing action result fields"},
                )
            if not self._scope_matches(identity, vmid, node):
                return self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
            payload["vmid"] = vmid
            payload["node"] = node
            payload["received_at"] = self._utcnow()
            self._store_action_result(node, vmid, payload)
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(last_action=self._summarize_action_result(payload)),
                },
            )

        if path == "/api/v1/endpoints/support-bundles/upload":
            try:
                vmid = int((query.get("vmid") or [""])[0])
                node = str((query.get("node") or [""])[0]).strip()
                action_id = str((query.get("action_id") or [""])[0]).strip()
                filename = str((query.get("filename") or [""])[0]).strip() or "support-bundle.tar.gz"
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid upload: {exc}"})
            if not node or not action_id:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid upload: missing upload fields"})
            if binary_payload is None:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid upload: missing payload"})
            if not self._scope_matches(identity, vmid, node):
                return self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
            bundle = self._store_support_bundle(node, vmid, action_id, filename, binary_payload)
            return self._json_response(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    **self._envelope(support_bundle=bundle),
                },
            )

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
