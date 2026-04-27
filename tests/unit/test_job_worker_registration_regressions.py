from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE_REGISTRY = ROOT / "beagle-host" / "services" / "service_registry.py"


def test_runtime_registers_three_long_operation_handlers() -> None:
    source = SERVICE_REGISTRY.read_text(encoding="utf-8")

    assert 'worker.register("vm.snapshot"' in source
    assert 'worker.register("vm.migrate"' in source
    assert 'worker.register("backup.run"' in source
    assert 'snapshot-create-as' in source
    assert 'backup_service().run_backup_now' in source
    assert 'migration_service().migrate_vm' in source
