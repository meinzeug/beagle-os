from __future__ import annotations

import os
import re
import socket
import subprocess
from pathlib import Path
from typing import Any, Callable

_GPU_CLASS_CODES = {"0300", "0302"}
_VENDOR_NAMES = {
    "10de": "nvidia",
    "1002": "amd",
    "1022": "amd",
    "8086": "intel",
}


class GpuInventoryService:
    def __init__(
        self,
        *,
        run_text: Callable[[list[str]], str] | None = None,
        sys_bus_pci_root: Path | None = None,
        sys_iommu_root: Path | None = None,
        hostname_provider: Callable[[], str] | None = None,
    ) -> None:
        self._run_text = run_text or self._default_run_text
        self._sys_bus_pci_root = Path(sys_bus_pci_root or "/sys/bus/pci/devices")
        self._sys_iommu_root = Path(sys_iommu_root or "/sys/kernel/iommu_groups")
        self._hostname_provider = hostname_provider or socket.gethostname

    @staticmethod
    def _default_run_text(command: list[str]) -> str:
        return subprocess.check_output(command, stderr=subprocess.DEVNULL, text=True)

    @staticmethod
    def _class_code_from_line(line: str) -> str:
        # lspci line example: "0000:01:00.0 VGA compatible controller [0300]: NVIDIA ... [10de:1eb8]"
        class_match = re.search(r"\[([0-9A-Fa-f]{4})\]", line)
        return str(class_match.group(1) if class_match else "").lower()

    @staticmethod
    def _ids_from_line(line: str) -> tuple[str, str]:
        id_matches = re.findall(r"\[([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\]", line)
        if not id_matches:
            return "", ""
        vendor_id, device_id = id_matches[-1]
        return vendor_id.lower(), device_id.lower()

    @staticmethod
    def _normalize_model(line: str) -> str:
        text = str(line or "").strip()
        if ":" in text:
            text = text.split(":", 1)[1].strip()
        # Remove trailing [vendor:device] annotation for readability.
        text = re.sub(r"\s*\[[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\]\s*$", "", text)
        return text.strip()

    @staticmethod
    def _driver_name(device_path: Path) -> str:
        driver_link = device_path / "driver"
        if not (driver_link.exists() or driver_link.is_symlink()):
            return ""
        try:
            target = os.readlink(driver_link)
            return Path(target).name
        except OSError:
            return ""

    def _iommu_group(self, device_path: Path) -> tuple[str, int]:
        group_link = device_path / "iommu_group"
        if not group_link.exists():
            return "", 0
        try:
            group_name = group_link.resolve().name
        except OSError:
            return "", 0
        if not group_name:
            return "", 0
        group_path = self._sys_iommu_root / group_name / "devices"
        if not group_path.exists():
            return group_name, 0
        try:
            group_size = len([child for child in group_path.iterdir()])
        except OSError:
            group_size = 0
        return group_name, group_size

    @staticmethod
    def _passthrough_status(group_id: str, group_size: int, driver: str) -> tuple[str, bool]:
        if not group_id:
            return "no-iommu-group", False
        if group_size > 1:
            return "not-isolatable", False
        if driver == "vfio-pci":
            return "assigned", True
        return "available-for-passthrough", True

    def list_gpus(self) -> list[dict[str, Any]]:
        try:
            raw = self._run_text(["lspci", "-Dnn"]) or ""
        except Exception:
            return []

        node = str(self._hostname_provider() or "").strip()
        items: list[dict[str, Any]] = []
        for raw_line in raw.splitlines():
            line = str(raw_line or "").strip()
            if not line:
                continue
            slot = line.split(" ", 1)[0].strip()
            if not slot or ":" not in slot:
                continue
            class_code = self._class_code_from_line(line)
            if class_code not in _GPU_CLASS_CODES:
                continue

            vendor_id, device_id = self._ids_from_line(line)
            vendor = _VENDOR_NAMES.get(vendor_id, vendor_id or "unknown")
            device_path = self._sys_bus_pci_root / slot
            driver = self._driver_name(device_path)
            iommu_group, iommu_group_size = self._iommu_group(device_path)
            status, passthrough_ready = self._passthrough_status(iommu_group, iommu_group_size, driver)

            items.append(
                {
                    "node": node,
                    "pci_address": slot,
                    "class_code": class_code,
                    "vendor": vendor,
                    "vendor_id": vendor_id,
                    "device_id": device_id,
                    "model": self._normalize_model(line),
                    "driver": driver,
                    "iommu_group": iommu_group,
                    "iommu_group_size": iommu_group_size,
                    "passthrough_ready": passthrough_ready,
                    "status": status,
                }
            )

        return items
