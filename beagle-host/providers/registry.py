from __future__ import annotations

from importlib import import_module
from typing import Any, Callable

from host_provider_contract import HostProvider

ProviderFactory = Callable[..., HostProvider]

_PROVIDER_MODULES: dict[str, tuple[str, str]] = {
    "proxmox": ("proxmox_host_provider", "ProxmoxHostProvider"),
}

_PROVIDER_ALIASES: dict[str, str] = {
    "pve": "proxmox",
}

_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {}


def normalize_provider_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower() or "proxmox"
    return _PROVIDER_ALIASES.get(normalized, normalized)


def register_provider(kind: str, factory: ProviderFactory) -> ProviderFactory:
    normalized = normalize_provider_kind(kind)
    _PROVIDER_FACTORIES[normalized] = factory
    return factory


def register_provider_module(kind: str, module_name: str, factory_name: str) -> tuple[str, str]:
    normalized = normalize_provider_kind(kind)
    module_spec = (str(module_name or "").strip(), str(factory_name or "").strip())
    if not all(module_spec):
        raise ValueError("provider module registration requires module_name and factory_name")
    _PROVIDER_MODULES[normalized] = module_spec
    return module_spec


def _load_registered_provider_factory(kind: str) -> ProviderFactory | None:
    normalized = normalize_provider_kind(kind)
    factory = _PROVIDER_FACTORIES.get(normalized)
    if factory is not None:
        return factory
    module_spec = _PROVIDER_MODULES.get(normalized)
    if module_spec is None:
        return None
    module_name, factory_name = module_spec
    module = import_module(module_name)
    candidate = getattr(module, factory_name, None)
    if candidate is None or not callable(candidate):
        raise ValueError(f"provider module '{module_name}' does not export callable '{factory_name}'")
    _PROVIDER_FACTORIES[normalized] = candidate
    return candidate


def create_provider(kind: str, **kwargs: Any) -> HostProvider:
    normalized = normalize_provider_kind(kind)
    factory = _load_registered_provider_factory(normalized)
    if factory is None:
        available = ", ".join(list_providers())
        raise ValueError(f"Unsupported host provider '{kind}'. Available providers: {available}")
    return factory(**kwargs)


def list_providers() -> list[str]:
    return sorted(set(_PROVIDER_MODULES.keys()) | set(_PROVIDER_FACTORIES.keys()))
