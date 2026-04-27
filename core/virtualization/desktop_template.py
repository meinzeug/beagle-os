from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class DesktopTemplateBuildSpec:
    template_id: str
    source_vmid: int
    template_name: str
    os_family: str
    storage_pool: str
    snapshot_name: str
    backing_image: str
    cpu_cores: int
    memory_mib: int
    software_packages: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""


@dataclass(frozen=True)
class DesktopTemplateInfo:
    template_id: str
    template_name: str
    source_vmid: int
    os_family: str
    storage_pool: str
    snapshot_name: str
    backing_image: str
    cpu_cores: int
    memory_mib: int
    software_packages: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = ""
    sealed: bool = False
    health: str = "unknown"


class DesktopTemplate(Protocol):
    """Provider-neutral desktop template lifecycle contract for VDI pools."""

    def build_template(self, spec: DesktopTemplateBuildSpec) -> DesktopTemplateInfo: ...

    def get_template(self, template_id: str) -> DesktopTemplateInfo | None: ...

    def list_templates(self, storage_pool: str = "") -> list[DesktopTemplateInfo]: ...

    def delete_template(self, template_id: str) -> bool: ...
