from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


class BeagleHostProvider:
    def __init__(
        self,
        *,
        run_json: Callable[..., Any] | None = None,
        run_text: Callable[..., str] | None = None,
        run_checked: Callable[..., str] | None = None,
        cache_get: Callable[[str, float], Any] | None = None,
        cache_put: Callable[[str, Any], Any] | None = None,
        state_dir: str | os.PathLike[str] | None = None,
    ) -> None:
        del run_json, run_text, run_checked
        self._cache_get = cache_get
        self._cache_put = cache_put
        configured_state_dir = state_dir or os.environ.get("BEAGLE_BEAGLE_PROVIDER_STATE_DIR", "")
        self._state_dir = Path(
            str(configured_state_dir).strip() or "/var/lib/beagle/providers/beagle"
        ).expanduser()
        self._default_node_name = str(os.environ.get("BEAGLE_BEAGLE_PROVIDER_DEFAULT_NODE", "beagle-0")).strip() or "beagle-0"
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        for path in (
            self._vm_configs_dir(),
            self._guest_interfaces_dir(),
            self._guest_exec_dir(),
            self._scheduled_restart_dir(),
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _get_cached(self, key: str, ttl_seconds: float) -> Any:
        if not key or ttl_seconds <= 0 or self._cache_get is None:
            return None
        return self._cache_get(key, ttl_seconds)

    def _put_cached(self, key: str, value: Any) -> Any:
        if not key or self._cache_put is None:
            return value
        return self._cache_put(key, value)

    def _nodes_path(self) -> Path:
        return self._state_dir / "nodes.json"

    def _storage_path(self) -> Path:
        return self._state_dir / "storage.json"

    def _vms_path(self) -> Path:
        return self._state_dir / "vms.json"

    def _counters_path(self) -> Path:
        return self._state_dir / "counters.json"

    def _vm_configs_dir(self) -> Path:
        return self._state_dir / "vm-configs"

    def _guest_interfaces_dir(self) -> Path:
        return self._state_dir / "guest-interfaces"

    def _guest_exec_dir(self) -> Path:
        return self._state_dir / "guest-exec-status"

    def _scheduled_restart_dir(self) -> Path:
        return self._state_dir / "scheduled-restarts"

    def _vm_config_path(self, node: str, vmid: int) -> Path:
        return self._vm_configs_dir() / str(node).strip() / f"{int(vmid)}.json"

    def _guest_interfaces_path(self, vmid: int) -> Path:
        return self._guest_interfaces_dir() / f"{int(vmid)}.json"

    def _guest_exec_status_path(self, vmid: int, pid: int) -> Path:
        return self._guest_exec_dir() / str(int(vmid)) / f"{int(pid)}.json"

    def _scheduled_restart_path(self, vmid: int) -> Path:
        return self._scheduled_restart_dir() / f"{int(vmid)}.json"

    @staticmethod
    def _read_json_file(path: Path, fallback: Any) -> Any:
        if not path.is_file():
            return fallback
        try:
            return __import__("json").loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return fallback

    @staticmethod
    def _write_json_file(path: Path, payload: Any) -> Any:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(__import__("json").dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload

    def _default_nodes(self) -> list[dict[str, Any]]:
        return [
            {
                "name": self._default_node_name,
                "status": "online",
                "cpu": 0.0,
                "mem": 0,
                "maxmem": 0,
                "maxcpu": 0,
            }
        ]

    def _default_storage(self) -> list[dict[str, Any]]:
        return [
            {
                "storage": "beagle-local",
                "node": self._default_node_name,
                "type": "dir",
                "content": "images,iso,backup",
                "shared": 0,
                "active": 1,
                "avail": 0,
                "used": 0,
                "total": 0,
            }
        ]

    def _load_nodes(self) -> list[dict[str, Any]]:
        payload = self._read_json_file(self._nodes_path(), self._default_nodes())
        if not isinstance(payload, list):
            return self._default_nodes()
        nodes: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("node") or "").strip()
            if not name:
                continue
            nodes.append(
                {
                    "name": name,
                    "status": str(item.get("status", "unknown")).strip() or "unknown",
                    "cpu": float(item.get("cpu", 0) or 0),
                    "mem": int(item.get("mem", 0) or 0),
                    "maxmem": int(item.get("maxmem", 0) or 0),
                    "maxcpu": int(item.get("maxcpu", 0) or 0),
                }
            )
        return nodes or self._default_nodes()

    def _load_storage(self) -> list[dict[str, Any]]:
        payload = self._read_json_file(self._storage_path(), self._default_storage())
        if not isinstance(payload, list):
            return self._default_storage()
        storage: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = str(item.get("storage") or item.get("name") or "").strip()
            if not name:
                continue
            storage.append(
                {
                    "storage": name,
                    "node": str(item.get("node") or self._default_node_name).strip() or self._default_node_name,
                    "type": str(item.get("type", "dir")).strip() or "dir",
                    "content": str(item.get("content", "images,iso")).strip() or "images,iso",
                    "shared": int(item.get("shared", 0) or 0),
                    "active": int(item.get("active", 1) or 0),
                    "avail": int(item.get("avail", 0) or 0),
                    "used": int(item.get("used", 0) or 0),
                    "total": int(item.get("total", 0) or 0),
                }
            )
        return storage or self._default_storage()

    @staticmethod
    def _normalize_vm_record(item: Mapping[str, Any]) -> dict[str, Any]:
        vmid = int(item.get("vmid", 0) or 0)
        node = str(item.get("node") or item.get("host") or "").strip()
        name = str(item.get("name") or f"vm-{vmid}").strip() or f"vm-{vmid}"
        return {
            "vmid": vmid,
            "node": node,
            "name": name,
            "status": str(item.get("status") or "stopped").strip() or "stopped",
            "tags": str(item.get("tags") or "").strip(),
            "type": "qemu",
        }

    def _load_vms(self) -> list[dict[str, Any]]:
        payload = self._read_json_file(self._vms_path(), [])
        if not isinstance(payload, list):
            return []
        vms: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_vm_record(item)
            if normalized["vmid"] <= 0 or not normalized["node"]:
                continue
            vms.append(normalized)
        return sorted(vms, key=lambda item: int(item.get("vmid", 0) or 0))

    def _write_vms(self, vms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = [self._normalize_vm_record(item) for item in vms if isinstance(item, dict)]
        return self._write_json_file(self._vms_path(), sorted(normalized, key=lambda item: item["vmid"]))

    @staticmethod
    def _option_dict(options: Mapping[str, Any] | Iterable[tuple[str, Any]]) -> dict[str, Any]:
        items = options.items() if isinstance(options, Mapping) else options
        normalized: dict[str, Any] = {}
        for key, value in items:
            option_name = str(key or "").strip()
            if not option_name:
                continue
            if option_name.startswith("--"):
                option_name = option_name[2:]
            normalized[option_name.replace("-", "_")] = value
        return normalized

    def _find_vm(self, vmid: int) -> dict[str, Any] | None:
        for item in self._load_vms():
            if int(item.get("vmid", 0) or 0) == int(vmid):
                return item
        return None

    def _replace_vm(self, record: dict[str, Any]) -> dict[str, Any]:
        target_vmid = int(record["vmid"])
        vms = [item for item in self._load_vms() if int(item.get("vmid", 0) or 0) != target_vmid]
        vms.append(self._normalize_vm_record(record))
        self._write_vms(vms)
        return self._normalize_vm_record(record)

    def _read_vm_config(self, node: str, vmid: int) -> dict[str, Any]:
        payload = self._read_json_file(self._vm_config_path(node, vmid), {})
        return payload if isinstance(payload, dict) else {}

    def _write_vm_config(self, node: str, vmid: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._write_json_file(self._vm_config_path(node, vmid), payload)

    def _read_guest_interfaces(self, vmid: int) -> list[dict[str, Any]]:
        payload = self._read_json_file(self._guest_interfaces_path(vmid), [])
        return payload if isinstance(payload, list) else []

    def _write_guest_interfaces(self, vmid: int, payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._write_json_file(self._guest_interfaces_path(vmid), payload)

    def _next_counter(self, name: str) -> int:
        counters = self._read_json_file(self._counters_path(), {})
        if not isinstance(counters, dict):
            counters = {}
        current_value = int(counters.get(name, 0) or 0) + 1
        counters[name] = current_value
        self._write_json_file(self._counters_path(), counters)
        return current_value

    @staticmethod
    def _first_guest_ipv4_from_interfaces(interfaces: list[dict[str, Any]]) -> str:
        for interface in interfaces:
            if not isinstance(interface, dict):
                continue
            addresses = interface.get("ip-addresses")
            if not isinstance(addresses, list):
                continue
            for address in addresses:
                if not isinstance(address, dict):
                    continue
                if str(address.get("ip-address-type") or "").strip().lower() != "ipv4":
                    continue
                candidate = str(address.get("ip-address") or "").strip()
                if not candidate or candidate.startswith("127.") or candidate.startswith("169.254."):
                    continue
                return candidate
        return ""

    def next_vmid(self) -> int:
        existing = [int(item.get("vmid", 0) or 0) for item in self._load_vms()]
        return max([99, *existing]) + 1

    def list_storage_inventory(self) -> list[dict[str, Any]]:
        return self._load_storage()

    def list_nodes(self) -> list[dict[str, Any]]:
        return self._load_nodes()

    def get_guest_network_interfaces(
        self,
        vmid: int,
        *,
        timeout_seconds: float | None = None,
    ) -> list[dict[str, Any]]:
        del timeout_seconds
        return self._read_guest_interfaces(vmid)

    def list_vms(
        self,
        *,
        refresh: bool = False,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
        vm_summary_factory: Callable[[dict[str, Any]], Any] | None = None,
    ) -> list[Any]:
        cached = None if refresh else self._get_cached(cache_key, cache_ttl_seconds)
        if isinstance(cached, list):
            return cached
        payload: list[Any] = []
        for item in self._load_vms():
            payload.append(vm_summary_factory(item) if vm_summary_factory is not None else item)
        return self._put_cached(cache_key, payload)

    def get_vm_config(
        self,
        node: str,
        vmid: int,
        *,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
    ) -> dict[str, Any]:
        cached = self._get_cached(cache_key, cache_ttl_seconds)
        if isinstance(cached, dict):
            return cached
        target_node = str(node or "").strip()
        record = self._find_vm(vmid)
        if not target_node and record is not None:
            target_node = str(record.get("node") or "").strip()
        payload = self._read_vm_config(target_node, vmid) if target_node else {}
        if not isinstance(payload, dict):
            payload = {}
        if record is not None:
            payload.setdefault("name", record.get("name") or f"vm-{int(vmid)}")
            payload.setdefault("tags", record.get("tags") or "")
            payload.setdefault("description", "")
            payload.setdefault("vmid", int(vmid))
            payload.setdefault("node", record.get("node") or target_node)
            payload.setdefault("ostype", "l26")
        return self._put_cached(cache_key, payload)

    def create_vm(
        self,
        vmid: int,
        options: Mapping[str, Any] | Iterable[tuple[str, Any]],
        *,
        timeout: float | None | object = None,
    ) -> str:
        del timeout
        normalized = self._option_dict(options)
        if self._find_vm(vmid) is not None:
            raise RuntimeError(f"VM {int(vmid)} already exists in beagle provider state")
        node = str(normalized.get("node") or self._default_node_name).strip() or self._default_node_name
        name = str(normalized.get("name") or f"vm-{int(vmid)}").strip() or f"vm-{int(vmid)}"
        tags = str(normalized.get("tags") or "").strip()
        status = str(normalized.get("status") or "stopped").strip() or "stopped"
        config = {
            **normalized,
            "vmid": int(vmid),
            "node": node,
            "name": name,
            "tags": tags,
            "description": str(normalized.get("description") or ""),
        }
        self._write_vm_config(node, vmid, config)
        guest_interfaces = normalized.get("guest_interfaces")
        if isinstance(guest_interfaces, list):
            self._write_guest_interfaces(vmid, guest_interfaces)
        self._replace_vm(
            {
                "vmid": int(vmid),
                "node": node,
                "name": name,
                "status": status,
                "tags": tags,
            }
        )
        return f"created beagle skeleton vm {int(vmid)} on {node}"

    def set_vm_options(
        self,
        vmid: int,
        options: Mapping[str, Any] | Iterable[tuple[str, Any]],
        *,
        timeout: float | None | object = None,
    ) -> str:
        del timeout
        record = self._find_vm(vmid)
        if record is None:
            raise RuntimeError(f"VM {int(vmid)} not found in beagle provider state")
        normalized = self._option_dict(options)
        node = str(record.get("node") or self._default_node_name).strip() or self._default_node_name
        config = self.get_vm_config(node, vmid)
        config.update(normalized)
        if "name" in normalized:
            record["name"] = str(normalized.get("name") or record["name"]).strip() or record["name"]
            config["name"] = record["name"]
        if "tags" in normalized:
            record["tags"] = str(normalized.get("tags") or "").strip()
        if "status" in normalized:
            record["status"] = str(normalized.get("status") or record["status"]).strip() or record["status"]
        if "guest_interfaces" in normalized and isinstance(normalized["guest_interfaces"], list):
            self._write_guest_interfaces(vmid, normalized["guest_interfaces"])
        self._write_vm_config(node, vmid, config)
        self._replace_vm(record)
        return f"updated beagle skeleton vm {int(vmid)} options"

    def delete_vm_options(
        self,
        vmid: int,
        option_names: Iterable[str],
        *,
        timeout: float | None | object = None,
    ) -> None:
        del timeout
        record = self._find_vm(vmid)
        if record is None:
            raise RuntimeError(f"VM {int(vmid)} not found in beagle provider state")
        node = str(record.get("node") or self._default_node_name).strip() or self._default_node_name
        config = self.get_vm_config(node, vmid)
        for name in option_names:
            normalized_name = str(name or "").strip()
            if not normalized_name:
                continue
            config.pop(normalized_name.replace("-", "_"), None)
        self._write_vm_config(node, vmid, config)

    def set_vm_description(
        self,
        vmid: int,
        description: str,
        *,
        timeout: float | None | object = None,
    ) -> str:
        del timeout
        record = self._find_vm(vmid)
        if record is None:
            raise RuntimeError(f"VM {int(vmid)} not found in beagle provider state")
        node = str(record.get("node") or self._default_node_name).strip() or self._default_node_name
        config = self.get_vm_config(node, vmid)
        config["description"] = str(description or "")
        self._write_vm_config(node, vmid, config)
        return f"updated beagle skeleton vm {int(vmid)} description"

    def set_vm_boot_order(
        self,
        vmid: int,
        order: str,
        *,
        timeout: float | None | object = None,
    ) -> str:
        del timeout
        return self.set_vm_options(vmid, {"boot": str(order or "")})

    def start_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str:
        del timeout
        record = self._find_vm(vmid)
        if record is None:
            raise RuntimeError(f"VM {int(vmid)} not found in beagle provider state")
        record["status"] = "running"
        self._replace_vm(record)
        return f"started beagle skeleton vm {int(vmid)}"

    def reboot_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str:
        del timeout
        record = self._find_vm(vmid)
        if record is None:
            raise RuntimeError(f"VM {int(vmid)} not found in beagle provider state")
        record["status"] = "running"
        self._replace_vm(record)
        node = str(record.get("node") or self._default_node_name).strip() or self._default_node_name
        config = self.get_vm_config(node, vmid)
        config["last_reboot_at"] = int(time.time())
        self._write_vm_config(node, vmid, config)
        return f"rebooted beagle skeleton vm {int(vmid)}"

    def stop_vm(
        self,
        vmid: int,
        *,
        skiplock: bool = False,
        timeout: float | None | object = None,
    ) -> str:
        del skiplock, timeout
        record = self._find_vm(vmid)
        if record is None:
            raise RuntimeError(f"VM {int(vmid)} not found in beagle provider state")
        record["status"] = "stopped"
        self._replace_vm(record)
        return f"stopped beagle skeleton vm {int(vmid)}"

    def guest_exec_bash(
        self,
        vmid: int,
        command: str,
        *,
        timeout_seconds: int | None = None,
        request_timeout: float | None = None,
    ) -> dict[str, Any]:
        del timeout_seconds, request_timeout
        if self._find_vm(vmid) is None:
            raise RuntimeError(f"VM {int(vmid)} not found in beagle provider state")
        pid = self._next_counter(f"guest-exec-{int(vmid)}")
        status_payload = {
            "exited": True,
            "exitcode": 0,
            "out-data": "",
            "err-data": "",
            "provider": "beagle",
            "command": str(command or ""),
            "pid": pid,
            "vmid": int(vmid),
        }
        self._write_json_file(self._guest_exec_status_path(vmid, pid), status_payload)
        return {"pid": pid}

    def guest_exec_status(
        self,
        vmid: int,
        pid: int,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        del timeout
        payload = self._read_json_file(self._guest_exec_status_path(vmid, pid), {})
        return payload if isinstance(payload, dict) else {}

    def guest_exec_script_text(
        self,
        vmid: int,
        script: str,
        *,
        poll_attempts: int = 300,
        poll_interval_seconds: float = 2.0,
    ) -> tuple[int, str, str]:
        del poll_attempts, poll_interval_seconds
        self.guest_exec_bash(vmid, script)
        return 0, "", ""

    def schedule_vm_restart_after_stop(
        self,
        vmid: int,
        *,
        wait_timeout_seconds: int,
    ) -> int:
        if self._find_vm(vmid) is None:
            raise RuntimeError(f"VM {int(vmid)} not found in beagle provider state")
        pid = self._next_counter(f"scheduled-restart-{int(vmid)}")
        self._write_json_file(
            self._scheduled_restart_path(vmid),
            {
                "pid": pid,
                "vmid": int(vmid),
                "provider": "beagle",
                "wait_timeout_seconds": int(wait_timeout_seconds),
                "scheduled_at": int(time.time()),
            },
        )
        return pid

    def get_guest_ipv4(
        self,
        vmid: int,
        *,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
        enable_lookup: bool = True,
        timeout_seconds: float | None = None,
    ) -> str:
        del enable_lookup, timeout_seconds
        cached = self._get_cached(cache_key, cache_ttl_seconds)
        if isinstance(cached, str):
            return cached
        ipv4 = self._first_guest_ipv4_from_interfaces(self.get_guest_network_interfaces(vmid))
        return str(self._put_cached(cache_key, ipv4))
