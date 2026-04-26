from __future__ import annotations

import os
import sys
from http import HTTPStatus

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "beagle-host", "services"))

from virtualization_read_surface import VirtualizationReadSurfaceService


def _make_surface(**overrides):
    defaults = dict(
        build_cluster_inventory=lambda: {},
        find_vm=lambda vmid: None,
        get_guest_network_interfaces=lambda vmid: [],
        get_ipam_zone_leases=lambda zone_id: [],
        get_ipam_zones=lambda: {},
        get_local_preflight=lambda: {"checks": []},
        get_storage_quota=lambda pool_name: {},
        get_vm_config=lambda node, vmid: {},
        get_vm_firewall_profile=lambda vm_id: None,
        host_provider_kind="beagle",
        list_cluster_members=lambda: [],
        list_bridges_inventory=lambda node="": [],
        list_firewall_profiles=lambda: [],
        list_gpu_inventory=lambda: [],
        list_nodes_inventory=lambda: [{"name": "beagle-local", "status": "online", "cpu": 0.1, "mem": 1, "maxmem": 2, "maxcpu": 4}],
        list_storage_inventory=lambda: [],
        list_vms=lambda: [],
        service_name="beagle-control-plane",
        utcnow=lambda: "2026-04-26T12:00:00Z",
        version="test",
    )
    defaults.update(overrides)
    return VirtualizationReadSurfaceService(**defaults)


def test_virtualization_overview_prefers_cluster_inventory_nodes():
    svc = _make_surface(
        build_cluster_inventory=lambda: {
            "nodes": [
                {"name": "srv1", "label": "srv1", "provider_node_name": "beagle-0", "status": "online", "cpu": 0.2, "mem": 11, "maxmem": 22, "maxcpu": 12},
                {"name": "beagle-1", "status": "online", "cpu": 0.3, "mem": 12, "maxmem": 24, "maxcpu": 8},
            ]
        }
    )

    resp = svc.route_get("/api/v1/virtualization/overview")

    assert resp["status"] == HTTPStatus.OK
    nodes = resp["payload"]["nodes"]
    assert [node["name"] for node in nodes] == ["srv1", "beagle-1"]
    assert nodes[0]["provider_node_name"] == "beagle-0"
    assert nodes[0]["label"] == "srv1"
    assert resp["payload"]["node_count"] == 2


def test_virtualization_overview_falls_back_to_local_nodes_without_cluster_inventory():
    svc = _make_surface(build_cluster_inventory=lambda: {})

    resp = svc.route_get("/api/v1/virtualization/overview")

    assert resp["status"] == HTTPStatus.OK
    nodes = resp["payload"]["nodes"]
    assert [node["name"] for node in nodes] == ["beagle-local"]
    assert resp["payload"]["node_count"] == 1


def test_virtualization_node_detail_includes_local_preflight_and_related_resources():
    svc = _make_surface(
        build_cluster_inventory=lambda: {
            "nodes": [
                {"name": "srv1", "label": "srv1", "provider_node_name": "beagle-0", "status": "online", "cpu": 0.2, "mem": 11, "maxmem": 22, "maxcpu": 12},
            ]
        },
        get_local_preflight=lambda: {
            "checks": [
                {"name": "kvm_device", "status": "pass", "message": "/dev/kvm exists"},
                {"name": "libvirtd", "status": "pass", "message": "libvirtd is active"},
                {"name": "virsh_connection", "status": "pass", "message": "ok"},
                {"name": "control_plane_api", "status": "warn", "message": "control-plane API not reachable on :8006"},
            ]
        },
        list_cluster_members=lambda: [
            {"name": "srv1", "api_url": "https://srv1.example.test/beagle-api/api/v1", "rpc_url": "https://srv1.example.test:9089/rpc", "status": "online", "local": True, "enabled": True},
        ],
        list_storage_inventory=lambda: [
            {"storage": "local", "node": "srv1", "type": "dir", "content": "images", "avail": 10, "used": 5, "total": 15, "active": 1}
        ],
        list_bridges_inventory=lambda node="": [
            {"name": "br0", "node": "srv1", "active": True, "cidr": "192.168.1.1/24", "bridge_ports": "eno1"}
        ],
        list_gpu_inventory=lambda: [
            {"node": "srv1", "pci_address": "0000:01:00.0", "model": "GTX", "driver": "vfio-pci", "iommu_group": "1", "iommu_group_size": 2, "passthrough_ready": False, "status": "not-isolatable"}
        ],
    )

    resp = svc.route_get("/api/v1/virtualization/nodes/srv1/detail")

    assert resp["status"] == HTTPStatus.OK
    payload = resp["payload"]
    assert payload["node"]["local"] is True
    assert payload["node"]["api_url"] == "https://srv1.example.test/beagle-api/api/v1"
    assert payload["services"]["kvm"] == "pass"
    assert payload["services"]["control_plane"] == "warn"
    assert len(payload["storage"]) == 1
    assert len(payload["bridges"]) == 1
    assert len(payload["gpus"]) == 1
    assert any("passthrough-ready" in warning or "passthrough-ready" in warning for warning in payload["warnings"])


def test_virtualization_node_detail_for_remote_member_omits_local_preflight():
    svc = _make_surface(
        build_cluster_inventory=lambda: {
            "nodes": [
                {"name": "srv2", "label": "srv2", "provider_node_name": "beagle-1", "status": "online", "cpu": 0.3, "mem": 12, "maxmem": 24, "maxcpu": 8},
            ]
        },
        list_cluster_members=lambda: [
            {"name": "srv1", "status": "online", "local": True, "enabled": True},
            {"name": "srv2", "api_url": "https://srv2.example.test/beagle-api/api/v1", "rpc_url": "https://srv2.example.test:9089/rpc", "status": "online", "local": False, "enabled": True},
        ],
    )

    resp = svc.route_get("/api/v1/virtualization/nodes/srv2/detail")

    assert resp["status"] == HTTPStatus.OK
    payload = resp["payload"]
    assert payload["node"]["local"] is False
    assert payload["preflight_checks"] == []
    assert payload["services"]["kvm"] == "unknown"
    assert payload["node"]["rpc_url"] == "https://srv2.example.test:9089/rpc"


class _Vm:
    def __init__(self, vmid, node, name="vm", status="running"):
        self.vmid = vmid
        self.node = node
        self.name = name
        self.status = status


class _FirewallProfile:
    def __init__(self, profile_id, name):
        self.profile_id = profile_id
        self.name = name


def test_virtualization_bridge_detail_includes_vm_usage_ipam_and_firewall_profiles():
    svc = _make_surface(
        list_bridges_inventory=lambda node="": [
            {"name": "br0", "node": "srv1", "active": True, "cidr": "192.168.1.1/24", "bridge_ports": "eno1"}
        ],
        list_vms=lambda: [_Vm(101, "srv1", name="app-101")],
        get_vm_config=lambda node, vmid: {"net0": "virtio,bridge=br0,firewall=1"},
        get_vm_firewall_profile=lambda vm_id: _FirewallProfile("web", "Web"),
        get_ipam_zones=lambda: {
            "br0": {
                "zone_id": "br0",
                "subnet": "192.168.1.0/24",
                "dhcp_start": "192.168.1.50",
                "dhcp_end": "192.168.1.99",
                "bridge_name": "br0",
            }
        },
        get_ipam_zone_leases=lambda zone_id: [
            {
                "ip_address": "192.168.1.50",
                "mac_address": "aa:bb:cc:dd:ee:ff",
                "vm_id": "101",
                "zone_id": zone_id,
                "hostname": "app-101",
                "static": False,
            }
        ],
        list_firewall_profiles=lambda: [{"profile_id": "web", "name": "Web", "rule_count": 2}],
    )

    resp = svc.route_get("/api/v1/virtualization/bridges/br0/detail")

    assert resp["status"] == HTTPStatus.OK
    payload = resp["payload"]
    assert payload["bridge"]["vm_count"] == 1
    assert payload["bridge"]["ipam_zone_count"] == 1
    assert payload["bridge"]["lease_count"] == 1
    assert payload["vms"][0]["firewall_profile_id"] == "web"
    assert payload["ipam_zones"][0]["lease_count"] == 1
    assert payload["firewall_profiles"][0]["profile_id"] == "web"
