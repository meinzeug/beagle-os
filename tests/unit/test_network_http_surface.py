"""Unit tests for NetworkHttpSurfaceService."""
from __future__ import annotations

import sys
import os
from http import HTTPStatus
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "beagle-host", "services"))

from network_http_surface import NetworkHttpSurfaceService


class _FakeLease:
    def __init__(self, ip, vm_id):
        self.ip_address = ip
        self.vm_id = vm_id

    @property
    def __dict__(self):
        return {"ip_address": self.ip_address, "vm_id": self.vm_id}


class _FakeFirewallProfileObj:
    def __init__(self):
        self.profile_id = "p1"
        self.name = "Web"
        self.rules = []


def _make_svc(**overrides):
    ipam = MagicMock()
    ipam.get_all_zones.return_value = [{"zone_id": "z1", "subnet": "10.0.0.0/24"}]
    ipam.get_zone_leases.return_value = [_FakeLease("10.0.0.2", "vm1")]
    ipam.allocate_ip.return_value = "10.0.0.5"

    fw = MagicMock()
    fw_profile = _FakeFirewallProfileObj()
    fw.list_profiles.return_value = [{"profile_id": "p1"}]
    fw.get_profile.return_value = fw_profile

    defaults = dict(
        ipam_service=ipam,
        firewall_service=fw,
        utcnow=lambda: "2024-01-01T00:00:00Z",
        version="test",
    )
    defaults.update(overrides)
    return NetworkHttpSurfaceService(**defaults), ipam, fw


class TestNetworkGetRouting:
    def test_list_ipam_zones(self):
        svc, ipam, _ = _make_svc()
        resp = svc.route_get("/api/v1/network/ipam/zones")
        assert resp["status"] == HTTPStatus.OK
        assert "zones" in resp["payload"]

    def test_get_ipam_leases(self):
        svc, ipam, _ = _make_svc()
        resp = svc.route_get("/api/v1/network/ipam/zones/z1/leases")
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["leases"][0]["ip_address"] == "10.0.0.2"
        ipam.get_zone_leases.assert_called_once_with("z1")

    def test_list_firewall_profiles(self):
        svc, _, fw = _make_svc()
        resp = svc.route_get("/api/v1/network/firewall/profiles")
        assert resp["status"] == HTTPStatus.OK
        assert "profiles" in resp["payload"]

    def test_get_firewall_profile(self):
        svc, _, fw = _make_svc()
        resp = svc.route_get("/api/v1/network/firewall/profiles/p1")
        assert resp["status"] == HTTPStatus.OK
        fw.get_profile.assert_called_once_with("p1")

    def test_firewall_profile_not_found(self):
        svc, _, fw = _make_svc()
        fw.get_profile.side_effect = KeyError
        resp = svc.route_get("/api/v1/network/firewall/profiles/missing")
        assert resp["status"] == HTTPStatus.NOT_FOUND

    def test_unknown_get_returns_none(self):
        svc, _, _ = _make_svc()
        assert svc.route_get("/api/v1/unknown") is None

    def test_handles_get(self):
        svc, _, _ = _make_svc()
        assert svc.handles_get("/api/v1/network/ipam/zones")
        assert svc.handles_get("/api/v1/network/firewall/profiles")
        assert not svc.handles_get("/api/v1/vms")


class TestNetworkPostRouting:
    def test_register_zone(self):
        svc, ipam, _ = _make_svc()
        resp = svc.route_post(
            "/api/v1/network/ipam/zones",
            json_payload={
                "zone_id": "z2",
                "subnet": "10.1.0.0/24",
                "dhcp_start": "10.1.0.10",
                "dhcp_end": "10.1.0.200",
            },
        )
        assert resp["status"] == HTTPStatus.OK
        ipam.register_zone.assert_called_once()

    def test_register_zone_missing_fields(self):
        svc, _, _ = _make_svc()
        resp = svc.route_post("/api/v1/network/ipam/zones", json_payload={"zone_id": "z2"})
        assert resp["status"] == HTTPStatus.BAD_REQUEST

    def test_allocate_ip(self):
        svc, ipam, _ = _make_svc()
        resp = svc.route_post(
            "/api/v1/network/ipam/zones/z1/allocate",
            json_payload={"vm_id": "vm2", "mac_address": "aa:bb:cc:dd:ee:ff"},
        )
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ip_address"] == "10.0.0.5"

    def test_allocate_ip_missing_fields(self):
        svc, _, _ = _make_svc()
        resp = svc.route_post(
            "/api/v1/network/ipam/zones/z1/allocate",
            json_payload={"vm_id": "vm2"},
        )
        assert resp["status"] == HTTPStatus.BAD_REQUEST

    def test_release_ip(self):
        svc, ipam, _ = _make_svc()
        resp = svc.route_post(
            "/api/v1/network/ipam/zones/z1/release",
            json_payload={"vm_id": "vm1"},
        )
        assert resp["status"] == HTTPStatus.OK
        ipam.release_ip.assert_called_once_with("z1", "vm1")

    def test_release_ip_no_vm_id(self):
        svc, _, _ = _make_svc()
        resp = svc.route_post("/api/v1/network/ipam/zones/z1/release", json_payload={})
        assert resp["status"] == HTTPStatus.BAD_REQUEST

    def test_create_firewall_profile(self):
        svc, _, fw = _make_svc()

        class _FakeFirewallProfile:
            def __init__(self, **kw):
                pass

        class _FakeFirewallRule:
            def __init__(self, **kw):
                pass

        # Patch the imports inside the method
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "firewall_service":
                m = MagicMock()
                m.FirewallProfile = _FakeFirewallProfile
                m.FirewallRule = _FakeFirewallRule
                return m
            return real_import(name, *args, **kwargs)

        import builtins
        original = builtins.__import__
        builtins.__import__ = mock_import
        try:
            resp = svc.route_post(
                "/api/v1/network/firewall/profiles",
                json_payload={
                    "profile_id": "p2",
                    "name": "App",
                    "rules": [{"direction": "inbound", "protocol": "tcp", "port": 443, "action": "allow"}],
                },
            )
        finally:
            builtins.__import__ = original

        assert resp["status"] == HTTPStatus.OK
        fw.create_profile.assert_called_once()

    def test_apply_firewall_profile(self):
        svc, _, fw = _make_svc()
        resp = svc.route_post(
            "/api/v1/network/firewall/profiles/p1/apply",
            json_payload={"vm_id": "vm3"},
        )
        assert resp["status"] == HTTPStatus.OK
        fw.apply_profile_to_vm.assert_called_once_with("p1", "vm3")

    def test_apply_profile_no_vm_id(self):
        svc, _, _ = _make_svc()
        resp = svc.route_post(
            "/api/v1/network/firewall/profiles/p1/apply",
            json_payload={},
        )
        assert resp["status"] == HTTPStatus.BAD_REQUEST

    def test_unknown_post_returns_none(self):
        svc, _, _ = _make_svc()
        assert svc.route_post("/api/v1/unknown") is None
