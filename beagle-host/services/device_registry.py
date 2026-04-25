"""Device Registry: Zentrale Datenbank aller enrolled Thin-Clients.

GoEnterprise Plan 02, Schritte 1 + 4 + 5:
- Hardware Inventory
- Remote-Wipe / Remote-Lock
- Standort- und Gruppen-Management
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from core.persistence.json_state_store import JsonStateStore

DeviceStatus = Literal["online", "offline", "locked", "wipe_pending", "wiped"]


@dataclass
class DeviceHardware:
    cpu_model: str = ""
    cpu_cores: int = 0
    ram_gb: int = 0
    gpu_model: str = ""
    network_interfaces: list[str] = field(default_factory=list)
    disk_gb: int = 0


@dataclass
class Device:
    device_id: str          # TPM-bound stable ID
    hostname: str
    hardware: DeviceHardware
    os_version: str
    enrolled_at: str        # ISO-8601
    last_seen: str          # ISO-8601
    location: str = ""
    group: str = ""
    status: DeviceStatus = "offline"
    wg_public_key: str = ""
    wg_assigned_ip: str = ""
    notes: str = ""


def device_hardware_from_dict(d: dict[str, Any]) -> DeviceHardware:
    return DeviceHardware(
        cpu_model=d.get("cpu_model", ""),
        cpu_cores=int(d.get("cpu_cores", 0)),
        ram_gb=int(d.get("ram_gb", 0)),
        gpu_model=d.get("gpu_model", ""),
        network_interfaces=d.get("network_interfaces", []),
        disk_gb=int(d.get("disk_gb", 0)),
    )


def device_from_dict(d: dict[str, Any]) -> Device:
    return Device(
        device_id=d["device_id"],
        hostname=d.get("hostname", ""),
        hardware=device_hardware_from_dict(d.get("hardware", {})),
        os_version=d.get("os_version", ""),
        enrolled_at=d.get("enrolled_at", ""),
        last_seen=d.get("last_seen", ""),
        location=d.get("location", ""),
        group=d.get("group", ""),
        status=d.get("status", "offline"),
        wg_public_key=d.get("wg_public_key", ""),
        wg_assigned_ip=d.get("wg_assigned_ip", ""),
        notes=d.get("notes", ""),
    )


class DeviceRegistryService:
    """Persistent registry for enrolled Beagle thin-clients."""

    STATE_FILE = Path("/var/lib/beagle/beagle-manager/device-registry.json")

    def __init__(self, state_file: Path | None = None, utcnow: Any = None) -> None:
        self._store = JsonStateStore(
            state_file or self.STATE_FILE,
            default_factory=lambda: {"devices": {}},
        )
        self._utcnow = utcnow or self._default_utcnow
        self._state = self._store.load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register_device(
        self,
        device_id: str,
        hostname: str,
        hardware_info: dict[str, Any],
        os_version: str = "",
        wg_public_key: str = "",
        wg_assigned_ip: str = "",
    ) -> Device:
        now = self._utcnow()
        hw = device_hardware_from_dict(hardware_info)
        dev = Device(
            device_id=device_id,
            hostname=hostname,
            hardware=hw,
            os_version=os_version,
            enrolled_at=now,
            last_seen=now,
            status="offline",
            wg_public_key=wg_public_key,
            wg_assigned_ip=wg_assigned_ip,
        )
        self._state["devices"][device_id] = asdict(dev)
        self._save()
        return dev

    def update_heartbeat(self, device_id: str, metrics: dict[str, Any] | None = None) -> Device:
        if device_id not in self._state["devices"]:
            raise KeyError(f"Device {device_id!r} not found")
        self._state["devices"][device_id]["last_seen"] = self._utcnow()
        self._state["devices"][device_id]["status"] = "online"
        self._save()
        return device_from_dict(self._state["devices"][device_id])

    def get_device(self, device_id: str) -> Device | None:
        d = self._state["devices"].get(device_id)
        return device_from_dict(d) if d else None

    def list_devices(
        self,
        *,
        location: str | None = None,
        group: str | None = None,
        status: DeviceStatus | None = None,
    ) -> list[Device]:
        devices = [device_from_dict(d) for d in self._state["devices"].values()]
        if location:
            devices = [d for d in devices if d.location == location]
        if group:
            devices = [d for d in devices if d.group == group]
        if status:
            devices = [d for d in devices if d.status == status]
        return devices

    def set_location(self, device_id: str, location: str) -> Device:
        dev = self._require(device_id)
        dev["location"] = location
        self._save()
        return device_from_dict(dev)

    def set_group(self, device_id: str, group: str) -> Device:
        dev = self._require(device_id)
        dev["group"] = group
        self._save()
        return device_from_dict(dev)

    # ------------------------------------------------------------------
    # Remote-Wipe + Remote-Lock (Plan 02, Schritt 4)
    # ------------------------------------------------------------------

    def wipe_device(self, device_id: str) -> Device:
        """Mark device for wipe — thin-client will act on next heartbeat."""
        dev = self._require(device_id)
        dev["status"] = "wipe_pending"
        self._save()
        return device_from_dict(dev)

    def confirm_wiped(self, device_id: str) -> Device:
        """Called by thin-client after successful wipe."""
        dev = self._require(device_id)
        dev["status"] = "wiped"
        dev["wg_public_key"] = ""
        dev["wg_assigned_ip"] = ""
        self._save()
        return device_from_dict(dev)

    def lock_device(self, device_id: str) -> Device:
        dev = self._require(device_id)
        dev["status"] = "locked"
        self._save()
        return device_from_dict(dev)

    def unlock_device(self, device_id: str) -> Device:
        dev = self._require(device_id)
        dev["status"] = "offline"
        self._save()
        return device_from_dict(dev)

    # ------------------------------------------------------------------
    # Group Bulk Operations (Plan 02, Schritt 5)
    # ------------------------------------------------------------------

    def assign_group(self, group: str, device_ids: list[str]) -> list[str]:
        """Assign multiple devices to a group. Returns list of updated IDs."""
        updated = []
        for did in device_ids:
            if did in self._state["devices"]:
                self._state["devices"][did]["group"] = group
                updated.append(did)
        self._save()
        return updated

    def list_groups(self) -> list[str]:
        return sorted({d.get("group", "") for d in self._state["devices"].values() if d.get("group")})

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require(self, device_id: str) -> dict[str, Any]:
        if device_id not in self._state["devices"]:
            raise KeyError(f"Device {device_id!r} not found")
        return self._state["devices"][device_id]

    def _save(self) -> None:
        self._store.save(self._state)

    @staticmethod
    def _default_utcnow() -> str:
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
