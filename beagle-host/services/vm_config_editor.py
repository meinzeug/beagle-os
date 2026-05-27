from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from http import HTTPStatus
from typing import Any, Callable


_EDITABLE_SCHEMA: list[dict[str, Any]] = [
    {
        "section": "General",
        "fields": ["name", "description", "tags", "protection", "template"],
    },
    {
        "section": "CPU",
        "fields": ["sockets", "cores", "vcpus", "cpu", "cpulimit", "cpuunits", "numa", "affinity", "allow-ksm"],
    },
    {
        "section": "Memory",
        "fields": ["memory", "balloon", "shares", "hugepages", "keephugepages"],
    },
    {
        "section": "System",
        "fields": [
            "ostype",
            "arch",
            "machine",
            "bios",
            "scsihw",
            "agent",
            "tablet",
            "acpi",
            "kvm",
            "localtime",
            "startdate",
            "reboot",
            "freeze",
            "tdf",
        ],
    },
    {
        "section": "Boot",
        "fields": ["boot", "bootdisk", "onboot", "startup", "order", "up", "down", "autostart"],
    },
    {
        "section": "DisplayAudio",
        "fields": ["vga", "audio0", "spice_enhancements", "keyboard"],
    },
    {
        "section": "CloudInit",
        "fields": ["ciuser", "cipassword", "sshkeys", "ipconfig0", "ipconfig1", "nameserver", "searchdomain", "citype", "ciupgrade", "cicustom"],
        "patterns": [r"^ipconfig\d+$"],
    },
    {
        "section": "Devices",
        "fields": ["smbios1"],
        "patterns": [
            r"^(virtio|ide|sata|scsi)\d+$",
            r"^net\d+$",
            r"^usb\d+$",
            r"^hostpci\d+$",
            r"^serial\d+$",
            r"^parallel\d+$",
            r"^rng\d+$",
            r"^tpmstate\d+$",
            r"^efidisk\d+$",
            r"^virtiofs\d+$",
            r"^unused\d+$",
            r"^numa\d+$",
        ],
    },
    {
        "section": "Advanced",
        "fields": [
            "args",
            "hookscript",
            "vmgenid",
            "vmstatestorage",
            "watchdog",
            "ivshmem",
            "amd-sev",
            "intel-tdx",
            "hotplug",
            "migrate_downtime",
            "migrate_speed",
            "lock",
        ],
    },
    {
        "section": "Beagle",
        "fields": [
            "beagle-update-enabled-override",
            "beagle-update-behavior-override",
            "beagle-update-channel-override",
        ],
    },
]

_ALLOWED_KEYS = {
    field
    for section in _EDITABLE_SCHEMA
    for field in section.get("fields", [])
}
_ALLOWED_PATTERNS = [re.compile(pattern) for section in _EDITABLE_SCHEMA for pattern in section.get("patterns", [])]
_SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SAFE_TEXT_RE = re.compile(r"^[^\x00]{0,8192}$")
_INT_RANGES = {
    "memory": (16, 1048576),
    "balloon": (0, 1048576),
    "sockets": (1, 256),
    "cores": (1, 512),
    "vcpus": (0, 512),
    "cpuunits": (1, 262144),
    "shares": (0, 50000),
    "order": (0, 100000),
    "up": (0, 86400),
    "down": (0, 86400),
}
_BOOL_KEYS = {
    "allow-ksm",
    "autostart",
    "ciupgrade",
    "freeze",
    "keephugepages",
    "kvm",
    "localtime",
    "numa",
    "onboot",
    "protection",
    "reboot",
    "tablet",
    "tdf",
    "template",
    "acpi",
}


class VmConfigEditorService:
    def __init__(
        self,
        *,
        get_vm_config: Callable[[str, int], dict[str, Any]],
        set_vm_options: Callable[[int, dict[str, Any]], str],
        invalidate_vm_cache: Callable[[int | None, str], None],
        delete_vm_options: Callable[[int, list[str]], Any] | None = None,
        run_virsh: Callable[[list[str]], str] | None = None,
        define_domain_xml: Callable[[str], Any] | None = None,
        libvirt_domain_name: Callable[[int], str] | None = None,
    ) -> None:
        self._get_vm_config = get_vm_config
        self._set_vm_options = set_vm_options
        self._delete_vm_options = delete_vm_options
        self._invalidate_vm_cache = invalidate_vm_cache
        self._run_virsh = run_virsh
        self._define_domain_xml = define_domain_xml
        self._libvirt_domain_name = libvirt_domain_name or (lambda vmid: f"beagle-{int(vmid)}")

    @staticmethod
    def schema() -> list[dict[str, Any]]:
        return list(_EDITABLE_SCHEMA)

    @staticmethod
    def is_editable_key(key: str) -> bool:
        name = str(key or "").strip()
        return name in _ALLOWED_KEYS or any(pattern.match(name) for pattern in _ALLOWED_PATTERNS)

    def update_vm_config(self, vm: Any, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"ok": False, "status": HTTPStatus.BAD_REQUEST, "error": "invalid payload"}
        updates_raw = payload.get("set") if isinstance(payload.get("set"), dict) else payload.get("updates")
        deletes_raw = payload.get("delete") if isinstance(payload.get("delete"), list) else []
        updates = updates_raw if isinstance(updates_raw, dict) else {}
        cleaned: dict[str, Any] = {}
        errors: list[str] = []
        for key, value in updates.items():
            name = str(key or "").strip()
            if not _SAFE_KEY_RE.match(name) or not self.is_editable_key(name):
                errors.append(f"unsupported option: {name}")
                continue
            try:
                cleaned[name] = self._normalize_value(name, value)
            except ValueError as exc:
                errors.append(str(exc))
        delete_keys: list[str] = []
        for key in deletes_raw:
            name = str(key or "").strip()
            if name and self.is_editable_key(name):
                delete_keys.append(name)
            elif name:
                errors.append(f"unsupported delete option: {name}")
        if errors:
            return {"ok": False, "status": HTTPStatus.BAD_REQUEST, "error": "; ".join(errors), "errors": errors}

        node = str(getattr(vm, "node", "") or "").strip()
        vmid = int(getattr(vm, "vmid"))
        current = self._get_vm_config(node, vmid)
        next_config = dict(current if isinstance(current, dict) else {})
        for key in delete_keys:
            next_config.pop(key, None)
        for key in cleaned:
            if key.startswith("beagle-"):
                next_config.pop(key.replace("-", "_"), None)
        next_config.update(cleaned)

        provider_result = self._set_vm_options(vmid, {key: value for key, value in next_config.items() if key not in {"vmid", "node", "status"}})
        if delete_keys and self._delete_vm_options is not None:
            self._delete_vm_options(vmid, delete_keys)
        libvirt_result = self._apply_libvirt_common(vmid, cleaned)
        self._invalidate_vm_cache(vmid, node)
        return {
            "ok": True,
            "vmid": vmid,
            "node": node,
            "config": next_config,
            "schema": self.schema(),
            "provider_result": provider_result,
            "libvirt_result": libvirt_result,
            "changed": sorted(cleaned.keys()),
            "deleted": delete_keys,
        }

    @staticmethod
    def _normalize_value(key: str, value: Any) -> Any:
        if key in _INT_RANGES:
            try:
                numeric = int(value)
            except (TypeError, ValueError):
                raise ValueError(f"{key} must be an integer")
            low, high = _INT_RANGES[key]
            if numeric < low or numeric > high:
                raise ValueError(f"{key} must be between {low} and {high}")
            return numeric
        if key in _BOOL_KEYS:
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "on", "ja"}
        text = str(value if value is not None else "").strip()
        if not _SAFE_TEXT_RE.match(text):
            raise ValueError(f"{key} contains invalid characters")
        return text

    def _apply_libvirt_common(self, vmid: int, updates: dict[str, Any]) -> dict[str, Any]:
        if self._run_virsh is None or self._define_domain_xml is None:
            return {"ok": True, "applied": [], "mode": "state-only"}
        common_keys = {"name", "description", "memory", "vcpus", "cores", "sockets"}
        if not common_keys.intersection(updates):
            return {"ok": True, "applied": [], "mode": "unchanged"}
        domain = self._libvirt_domain_name(vmid)
        try:
            xml_text = self._run_virsh(["dumpxml", domain])
            root = ET.fromstring(xml_text)
            applied: list[str] = []
            if "name" in updates:
                self._set_text(root, "name", str(updates["name"]))
                applied.append("name")
            if "description" in updates:
                self._set_text(root, "description", str(updates["description"]))
                applied.append("description")
            if "memory" in updates:
                memory_kib = int(updates["memory"]) * 1024
                self._set_text(root, "memory", str(memory_kib), {"unit": "KiB"})
                self._set_text(root, "currentMemory", str(memory_kib), {"unit": "KiB"})
                applied.append("memory")
            if any(key in updates for key in ("vcpus", "cores", "sockets")):
                total = int(updates.get("vcpus") or (int(updates.get("cores") or 1) * int(updates.get("sockets") or 1)))
                self._set_text(root, "vcpu", str(max(1, total)))
                applied.append("vcpu")
            self._define_domain_xml(ET.tostring(root, encoding="unicode"))
            return {"ok": True, "applied": applied, "mode": "libvirt-define"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:400], "mode": "libvirt-define"}

    @staticmethod
    def _set_text(root: ET.Element, tag: str, value: str, attrs: dict[str, str] | None = None) -> None:
        node = root.find(tag)
        if node is None:
            node = ET.SubElement(root, tag)
        node.text = value
        if attrs:
            node.attrib.update(attrs)
