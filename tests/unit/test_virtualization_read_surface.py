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
        get_storage_quota=lambda pool_name: {},
        get_vm_config=lambda node, vmid: {},
        host_provider_kind="beagle",
        list_bridges_inventory=lambda node="": [],
        list_gpu_inventory=lambda: [],
        list_nodes_inventory=lambda: [{"name": "beagle-local", "status": "online", "cpu": 0.1, "mem": 1, "maxmem": 2, "maxcpu": 4}],
        list_storage_inventory=lambda: [],
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
