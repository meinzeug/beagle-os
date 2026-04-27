from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from ha_manager import HaManagerService  # noqa: E402
from ha_watchdog import HaWatchdogService  # noqa: E402


@dataclass
class VmRecord:
    vmid: int
    node: str
    name: str
    status: str


def _make_watchdog(state_file: Path):
    now_box = {"value": 1_000.0}
    sent: list[tuple[str, dict]] = []
    fenced: list[tuple[str, str]] = []

    def run_fencing(node: str, method: str) -> bool:
        fenced.append((node, method))
        return method == "vm_forcestop"

    service = HaWatchdogService(
        state_file=state_file,
        node_name="node-a",
        list_nodes=lambda: [{"name": "node-a"}, {"name": "node-b"}],
        send_heartbeat=lambda target, payload: sent.append((target, payload)),
        run_fencing_action=run_fencing,
        utcnow=lambda: "2026-04-27T10:50:00Z",
        now=lambda: float(now_box["value"]),
        heartbeat_interval_seconds=2.0,
        missed_heartbeats_before_fencing=3,
    )
    return service, now_box, sent, fenced


def _make_ha_manager(vms: list[VmRecord], vm_configs: dict[int, dict]):
    migrations: list[dict] = []
    restarts: list[dict] = []

    def migrate_vm(vmid: int, target: str, live: bool, _copy_storage: bool, requester_identity: str) -> dict:
        migrations.append(
            {
                "vmid": vmid,
                "target": target,
                "live": live,
                "requester_identity": requester_identity,
            }
        )
        return {"ok": True, "vmid": vmid, "target": target, "live": live}

    def cold_restart_vm(vmid: int, source: str, target: str) -> dict:
        restarts.append({"vmid": vmid, "source": source, "target": target})
        return {"ok": True, "vmid": vmid, "target": target}

    service = HaManagerService(
        list_nodes=lambda: [
            {"name": "node-a", "status": "online"},
            {"name": "node-b", "status": "fenced"},
        ],
        list_vms=lambda: list(vms),
        get_vm_config=lambda node, vmid: dict(vm_configs.get(vmid, {})),
        migrate_vm=migrate_vm,
        cold_restart_vm=cold_restart_vm,
        service_name="test-cp",
        utcnow=lambda: "2026-04-27T10:50:00Z",
        version="test",
    )
    return service, migrations, restarts


def test_watchdog_detects_timeout_and_fences_node(temp_state_dir: Path) -> None:
    state_file = temp_state_dir / "ha-watchdog.json"
    watchdog, now_box, sent, fenced = _make_watchdog(state_file)

    heartbeat = watchdog.send_heartbeats()
    assert heartbeat["target_count"] == 1
    assert sent[0][0] == "node-b"

    watchdog.record_heartbeat("node-b", received_at=1_000.0)
    now_box["value"] = 1_007.0

    result = watchdog.evaluate_timeouts()

    assert result["timeout_seconds"] == 6.0
    assert result["fenced_nodes"] == [
        {
            "node": "node-b",
            "fenced": True,
            "method": "vm_forcestop",
            "heartbeat_age_seconds": 7.0,
        }
    ]
    assert fenced == [
        ("node-b", "ipmi_reset"),
        ("node-b", "watchdog_timer"),
        ("node-b", "vm_forcestop"),
    ]
    assert watchdog.list_node_health()[0]["status"] == "fenced"


def test_reconcile_failed_node_handles_failover_and_restart(temp_state_dir: Path) -> None:
    state_file = temp_state_dir / "ha-watchdog.json"
    watchdog, now_box, _sent, _fenced = _make_watchdog(state_file)
    watchdog.record_heartbeat("node-b", received_at=1_000.0)
    now_box["value"] = 1_007.0
    fence_result = watchdog.evaluate_timeouts()
    assert fence_result["fenced_nodes"][0]["node"] == "node-b"

    vms = [
        VmRecord(vmid=401, node="node-b", name="vm-401", status="running"),
        VmRecord(vmid=402, node="node-b", name="vm-402", status="stopped"),
        VmRecord(vmid=403, node="node-a", name="vm-403", status="running"),
        VmRecord(vmid=404, node="node-b", name="vm-404", status="running"),
    ]
    vm_configs = {
        401: {"ha_policy": "fail_over"},
        402: {"ha_policy": "restart"},
        403: {"ha_policy": "fail_over"},
        404: {"ha_policy": "disabled"},
    }
    ha_manager, migrations, restarts = _make_ha_manager(vms, vm_configs)

    payload = ha_manager.reconcile_failed_node(failed_node="node-b", requester_identity="integration-test")

    assert payload["evaluated_vm_count"] == 3
    assert payload["handled_vm_count"] == 2
    assert migrations == [
        {
            "vmid": 401,
            "target": "node-a",
            "live": True,
            "requester_identity": "integration-test",
        }
    ]
    assert restarts == [{"vmid": 402, "source": "node-b", "target": "node-a"}]
    disabled = next(item for item in payload["actions"] if item["vmid"] == 404)
    assert disabled["result"] == "skipped"


def test_reconcile_uses_cold_restart_fallback_when_migration_fails(temp_state_dir: Path) -> None:
    restarts: list[dict] = []

    service = HaManagerService(
        list_nodes=lambda: [
            {"name": "node-a", "status": "online"},
            {"name": "node-b", "status": "fenced"},
        ],
        list_vms=lambda: [VmRecord(vmid=501, node="node-b", name="vm-501", status="running")],
        get_vm_config=lambda node, vmid: {"ha_policy": "fail_over"},
        migrate_vm=lambda vmid, target, live, _copy_storage, requester_identity: (_ for _ in ()).throw(RuntimeError("migration failed")),
        cold_restart_vm=lambda vmid, source, target: restarts.append({"vmid": vmid, "source": source, "target": target}) or {"ok": True},
        service_name="test-cp",
        utcnow=lambda: "2026-04-27T10:50:00Z",
        version="test",
    )

    payload = service.reconcile_failed_node(failed_node="node-b", requester_identity="integration-test")

    assert payload["handled_vm_count"] == 1
    assert restarts == [{"vmid": 501, "source": "node-b", "target": "node-a"}]
    assert payload["actions"][0]["result"] == "cold_restart_fallback"
    assert payload["actions"][0]["fallback_reason"] == "migration failed"


def test_failover_pipeline_stays_within_tmax_budget(temp_state_dir: Path) -> None:
    state_file = temp_state_dir / "ha-watchdog.json"
    watchdog, now_box, _sent, _fenced = _make_watchdog(state_file)
    watchdog.record_heartbeat("node-b", received_at=1_000.0)
    now_box["value"] = 1_007.0

    vms = [VmRecord(vmid=601, node="node-b", name="vm-601", status="running")]
    vm_configs = {601: {"ha_policy": "fail_over"}}
    ha_manager, migrations, _restarts = _make_ha_manager(vms, vm_configs)

    started_at = time.monotonic()
    fence_result = watchdog.evaluate_timeouts()
    failed_node = fence_result["fenced_nodes"][0]["node"]
    reconcile = ha_manager.reconcile_failed_node(failed_node=failed_node, requester_identity="integration-test")
    elapsed = time.monotonic() - started_at

    assert elapsed < 1.0
    assert 7.0 + elapsed < 60.0
    assert reconcile["handled_vm_count"] == 1
    assert migrations[0]["vmid"] == 601
    assert migrations[0]["target"] == "node-a"
