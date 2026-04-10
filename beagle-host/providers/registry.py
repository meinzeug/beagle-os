from __future__ import annotations

from typing import Any, Callable

from host_provider_contract import HostProvider
from proxmox_host_provider import ProxmoxHostProvider

ProviderFactory = Callable[..., HostProvider]

_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "proxmox": ProxmoxHostProvider,
}

_PROVIDER_ALIASES: dict[str, str] = {
    "pve": "proxmox",
}


def normalize_provider_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower() or "proxmox"
    return _PROVIDER_ALIASES.get(normalized, normalized)


def register_provider(kind: str, factory: ProviderFactory) -> ProviderFactory:
    normalized = normalize_provider_kind(kind)
    _PROVIDER_FACTORIES[normalized] = factory
    return factory


def create_provider(kind: str, **kwargs: Any) -> HostProvider:
    normalized = normalize_provider_kind(kind)
    factory = _PROVIDER_FACTORIES.get(normalized)
    if factory is None:
        available = ", ".join(sorted(_PROVIDER_FACTORIES.keys()))
        raise ValueError(f"Unsupported host provider '{kind}'. Available providers: {available}")
    return factory(**kwargs)


def list_providers() -> list[str]:
    return sorted(_PROVIDER_FACTORIES.keys())
