"""Network (IPAM + Firewall) HTTP Surface — Plan 05 Schritt 3d.

Handles:
  GET  /api/v1/network/ipam/zones
  GET  /api/v1/network/ipam/zones/{zone_id}/leases
  GET  /api/v1/network/firewall/profiles
  GET  /api/v1/network/firewall/profiles/{profile_id}
  POST /api/v1/network/ipam/zones
  POST /api/v1/network/ipam/zones/{zone_id}/allocate
  POST /api/v1/network/ipam/zones/{zone_id}/release
  POST /api/v1/network/firewall/profiles
  POST /api/v1/network/firewall/profiles/{profile_id}/apply

Extracted from beagle-control-plane.py (Plan 05 Schritt 3d).
"""
from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable


class NetworkHttpSurfaceService:
    _IPAM_LEASES = re.compile(r"^/api/v1/network/ipam/zones/(?P<zone_id>[A-Za-z0-9._-]+)/leases$")
    _IPAM_ALLOCATE = re.compile(r"^/api/v1/network/ipam/zones/(?P<zone_id>[A-Za-z0-9._-]+)/allocate$")
    _IPAM_RELEASE = re.compile(r"^/api/v1/network/ipam/zones/(?P<zone_id>[A-Za-z0-9._-]+)/release$")
    _FIREWALL_PROFILE = re.compile(
        r"^/api/v1/network/firewall/profiles/(?P<profile_id>[A-Za-z0-9._-]+)$"
    )
    _FIREWALL_APPLY = re.compile(
        r"^/api/v1/network/firewall/profiles/(?P<profile_id>[A-Za-z0-9._-]+)/apply$"
    )

    def __init__(
        self,
        *,
        ipam_service: Any,
        firewall_service: Any,
        service_name: str = "beagle-control-plane",
        utcnow: Callable[[], str],
        version: str = "",
    ) -> None:
        self._ipam = ipam_service
        self._firewall = firewall_service
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")

    @staticmethod
    def _json(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    # ------------------------------------------------------------------
    # GET routing
    # ------------------------------------------------------------------

    def handles_get(self, path: str) -> bool:
        if path in {"/api/v1/network/ipam/zones", "/api/v1/network/firewall/profiles"}:
            return True
        if self._IPAM_LEASES.match(path):
            return True
        if self._FIREWALL_PROFILE.match(path):
            return True
        return False

    def route_get(self, path: str) -> dict[str, Any] | None:
        if path == "/api/v1/network/ipam/zones":
            state = self._ipam.get_all_zones()
            return self._json(HTTPStatus.OK, {"ok": True, "zones": state})

        m = self._IPAM_LEASES.match(path)
        if m:
            zone_id = m.group("zone_id")
            leases = self._ipam.get_zone_leases(zone_id)
            return self._json(HTTPStatus.OK, {"ok": True, "leases": [l.__dict__ for l in leases]})

        if path == "/api/v1/network/firewall/profiles":
            profiles = self._firewall.list_profiles()
            return self._json(HTTPStatus.OK, {"ok": True, "profiles": profiles})

        m = self._FIREWALL_PROFILE.match(path)
        if m:
            profile_id = m.group("profile_id")
            try:
                profile = self._firewall.get_profile(profile_id)
                return self._json(HTTPStatus.OK, {"ok": True, "profile": profile.__dict__})
            except KeyError:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "profile not found"})

        return None

    # ------------------------------------------------------------------
    # POST routing
    # ------------------------------------------------------------------

    def handles_post(self, path: str) -> bool:
        if path in {"/api/v1/network/ipam/zones", "/api/v1/network/firewall/profiles"}:
            return True
        if self._IPAM_ALLOCATE.match(path):
            return True
        if self._IPAM_RELEASE.match(path):
            return True
        if self._FIREWALL_APPLY.match(path):
            return True
        return False

    def route_post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        p = json_payload or {}

        if path == "/api/v1/network/ipam/zones":
            zone_id = str(p.get("zone_id") or "").strip()
            subnet = str(p.get("subnet") or "").strip()
            dhcp_start = str(p.get("dhcp_start") or "").strip()
            dhcp_end = str(p.get("dhcp_end") or "").strip()
            if not all([zone_id, subnet, dhcp_start, dhcp_end]):
                return self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "zone_id, subnet, dhcp_start, dhcp_end required"},
                )
            try:
                self._ipam.register_zone(zone_id, subnet, dhcp_start, dhcp_end)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.OK, {"ok": True, "zone_id": zone_id})

        m = self._IPAM_ALLOCATE.match(path)
        if m:
            zone_id = m.group("zone_id")
            vm_id = str(p.get("vm_id") or "").strip()
            mac = str(p.get("mac_address") or "").strip()
            hostname = str(p.get("hostname") or vm_id).strip()
            static_ip = str(p.get("static_ip") or "").strip() or None
            if not all([vm_id, mac]):
                return self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "vm_id, mac_address required"},
                )
            try:
                ip = self._ipam.allocate_ip(zone_id, vm_id, mac, hostname, static_ip=static_ip)
            except (ValueError, KeyError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.OK, {"ok": True, "ip_address": ip})

        m = self._IPAM_RELEASE.match(path)
        if m:
            zone_id = m.group("zone_id")
            vm_id = str(p.get("vm_id") or "").strip()
            if not vm_id:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "vm_id required"})
            try:
                self._ipam.release_ip(zone_id, vm_id)
            except (ValueError, KeyError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.OK, {"ok": True})

        if path == "/api/v1/network/firewall/profiles":
            from firewall_service import FirewallProfile, FirewallRule
            profile_id = str(p.get("profile_id") or "").strip()
            name = str(p.get("name") or profile_id).strip()
            rules_data = p.get("rules") or []
            if not profile_id:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "profile_id required"})
            rules = [
                FirewallRule(
                    direction=str(r.get("direction") or "inbound"),
                    protocol=str(r.get("protocol") or "tcp"),
                    port=int(r.get("port") or 0),
                    action=str(r.get("action") or "allow"),
                    source_cidr=str(r.get("source_cidr") or "") or None,
                )
                for r in rules_data
                if isinstance(r, dict)
            ]
            profile = FirewallProfile(profile_id=profile_id, name=name, rules=rules)
            try:
                self._firewall.create_profile(profile)
            except (ValueError, KeyError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.OK, {"ok": True, "profile_id": profile_id})

        m = self._FIREWALL_APPLY.match(path)
        if m:
            profile_id = m.group("profile_id")
            vm_id = str(p.get("vm_id") or "").strip()
            if not vm_id:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "vm_id required"})
            try:
                self._firewall.apply_profile_to_vm(profile_id, vm_id)
            except (ValueError, KeyError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.OK, {"ok": True})

        return None
