import importlib.util
import sys
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT / "beagle-host" / "services"
PROVIDERS_DIR = ROOT / "beagle-host" / "providers"
BIN_DIR = ROOT / "beagle-host" / "bin"
for _directory in (SERVICES_DIR, PROVIDERS_DIR, BIN_DIR, ROOT):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))


def test_vm_mutation_surface_is_wired_to_vm_config_editor() -> None:
    spec = importlib.util.spec_from_file_location(
        "beagle_service_registry_vm_config_editor_wiring",
        SERVICES_DIR / "service_registry.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module

    provider = mock.MagicMock()
    provider.set_vm_options.return_value = "ok"
    provider.delete_vm_options.return_value = None
    provider._run_virsh.return_value = ""
    provider._libvirt_domain_name.side_effect = lambda vmid: f"beagle-{int(vmid)}"

    with mock.patch("registry.create_provider", return_value=provider):
        spec.loader.exec_module(module)

    mutation_service = module.vm_mutation_surface_service()
    editor_service = module.vm_config_editor_service()

    assert mutation_service._update_vm_config is not None
    assert getattr(mutation_service._update_vm_config, "__self__", None) is editor_service
