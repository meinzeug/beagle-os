from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from core.repository.vm_repository import VmRepository


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
        vm_repository: VmRepository | None = None,
    ) -> None:
        del run_json, run_text, run_checked
        self._cache_get = cache_get
        self._cache_put = cache_put
        configured_state_dir = state_dir or os.environ.get("BEAGLE_BEAGLE_PROVIDER_STATE_DIR", "")
        self._state_dir = Path(
            str(configured_state_dir).strip() or "/var/lib/beagle/providers/beagle"
        ).expanduser()
        configured_images_dir = os.environ.get("BEAGLE_LIBVIRT_IMAGES_DIR", "")
        self._libvirt_images_dir = Path(
            str(configured_images_dir).strip() or "/var/lib/libvirt/images"
        ).expanduser()
        self._default_node_name = str(os.environ.get("BEAGLE_BEAGLE_PROVIDER_DEFAULT_NODE", "beagle-0")).strip() or "beagle-0"
        self._cpu_stat_prev: tuple[float, float] | None = None  # (idle_time, total_time)
        self._vm_repo: VmRepository | None = vm_repository
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

    def _bridges_path(self) -> Path:
        return self._state_dir / "bridges.json"

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
                "storage": "local",
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

    def _default_bridges(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "beagle",
                "node": self._default_node_name,
                "type": "bridge",
                "active": True,
                "address": "",
                "netmask": "",
                "cidr": "",
                "bridge_ports": "",
                "autostart": True,
            }
        ]

    def _read_proc_stat_cpu_fields(self) -> list[int] | None:
        """Return the first aggregate cpu line from /proc/stat as a list of ints."""
        try:
            with open("/proc/stat", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("cpu "):
                        return [int(x) for x in line.split()[1:]]
        except Exception:
            pass
        return None

    def _compute_cpu_utilization(self) -> float:
        """Instantaneous CPU utilization as a fraction 0.0–1.0 using /proc/stat delta."""
        fields = self._read_proc_stat_cpu_fields()
        if fields is None or len(fields) < 4:
            return 0.0
        # /proc/stat columns: user nice system idle iowait irq softirq steal ...
        idle = float(fields[3] + (fields[4] if len(fields) > 4 else 0))  # idle + iowait
        total = float(sum(fields))
        prev = self._cpu_stat_prev
        self._cpu_stat_prev = (idle, total)
        if prev is None or total == 0.0:
            return 0.0
        delta_total = total - prev[1]
        delta_idle = idle - prev[0]
        if delta_total <= 0.0:
            return 0.0
        return max(0.0, min(1.0, (delta_total - delta_idle) / delta_total))

    def _read_mem_bytes(self) -> tuple[int, int]:
        """Return (mem_total_bytes, mem_used_bytes) from /proc/meminfo."""
        try:
            info: dict[str, int] = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        try:
                            info[key] = int(parts[1])
                        except ValueError:
                            pass
            mem_total_kb = info.get("MemTotal", 0)
            mem_free_kb = info.get("MemFree", 0)
            mem_buffers_kb = info.get("Buffers", 0)
            mem_cached_kb = info.get("Cached", 0)
            mem_sreclaimable_kb = info.get("SReclaimable", 0)
            # used = total - free - buffers - page-cache - reclaimable slab
            mem_used_kb = mem_total_kb - mem_free_kb - mem_buffers_kb - mem_cached_kb - mem_sreclaimable_kb
            return (mem_total_kb * 1024, max(0, mem_used_kb) * 1024)
        except Exception:
            return (0, 0)

    def _discover_live_node_metrics(self) -> list[dict[str, Any]]:
        """Read real CPU and RAM metrics for the local node from /proc."""
        try:
            cpu_count = os.cpu_count() or 1
            cpu_usage = self._compute_cpu_utilization()
            mem_total, mem_used = self._read_mem_bytes()
            if mem_total == 0:
                return []
            return [
                {
                    "name": self._default_node_name,
                    "status": "online",
                    "cpu": round(cpu_usage, 4),
                    "mem": mem_used,
                    "maxmem": mem_total,
                    "maxcpu": cpu_count,
                }
            ]
        except Exception:
            return []

    def _load_nodes(self) -> list[dict[str, Any]]:
        live_nodes = self._discover_live_node_metrics()
        if live_nodes:
            return live_nodes
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
        live_storage = self._discover_libvirt_storage()
        if live_storage:
            return live_storage
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
            avail = int(item.get("avail", 0) or 0)
            used = int(item.get("used", 0) or 0)
            total = int(item.get("total", 0) or 0)
            # When no size data is present, read from the state dir filesystem.
            if total == 0:
                try:
                    st = os.statvfs(str(self._state_dir))
                    total = st.f_frsize * st.f_blocks
                    avail = st.f_frsize * st.f_bavail
                    used = total - avail
                except Exception:
                    pass
            storage.append(
                {
                    "storage": name,
                    "node": str(item.get("node") or self._default_node_name).strip() or self._default_node_name,
                    "type": str(item.get("type", "dir")).strip() or "dir",
                    "content": str(item.get("content", "images,iso")).strip() or "images,iso",
                    "shared": int(item.get("shared", 0) or 0),
                    "active": int(item.get("active", 1) or 0),
                    "avail": avail,
                    "used": used,
                    "total": total,
                }
            )
        return storage or self._default_storage()

    def _load_bridges(self) -> list[dict[str, Any]]:
        live_bridges = self._discover_libvirt_networks()
        if live_bridges:
            return live_bridges
        payload = self._read_json_file(self._bridges_path(), self._default_bridges())
        if not isinstance(payload, list):
            return self._default_bridges()
        bridges: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("iface") or "").strip()
            if not name:
                continue
            bridges.append(
                {
                    "name": name,
                    "node": str(item.get("node") or self._default_node_name).strip() or self._default_node_name,
                    "type": "bridge",
                    "active": bool(item.get("active", True)),
                    "address": str(item.get("address", "") or "").strip(),
                    "netmask": str(item.get("netmask", "") or "").strip(),
                    "cidr": str(item.get("cidr", "") or "").strip(),
                    "bridge_ports": str(item.get("bridge_ports", "") or "").strip(),
                    "autostart": bool(item.get("autostart", True)),
                }
            )
        return bridges or self._default_bridges()

    def _discover_libvirt_storage(self) -> list[dict[str, Any]]:
        if not self._libvirt_enabled():
            return []
        try:
            names = [name.strip() for name in self._run_virsh("pool-list", "--all", "--name").splitlines() if name.strip()]
        except Exception:
            return []
        storage: list[dict[str, Any]] = []
        for name in names:
            pool_type = "dir"
            pool_path = ""
            active = 0
            autostart = 0
            available = 0
            allocation = 0
            capacity = 0
            try:
                xml = self._run_virsh("pool-dumpxml", name)
                type_match = re.search(r"<pool[^>]*type=['\"]([^'\"]+)['\"]", xml)
                path_match = re.search(r"<path>([^<]+)</path>", xml)
                if type_match:
                    pool_type = type_match.group(1).strip() or "dir"
                if path_match:
                    pool_path = path_match.group(1).strip()
            except Exception:
                pass
            try:
                info = self._run_virsh("pool-info", name)
                if re.search(r"State:\s+running", info, re.IGNORECASE):
                    active = 1
                if re.search(r"Autostart:\s+yes", info, re.IGNORECASE):
                    autostart = 1
                cap_match = re.search(r"Capacity:\s+([0-9.]+)\s+([A-Za-z]+)", info)
                alloc_match = re.search(r"Allocation:\s+([0-9.]+)\s+([A-Za-z]+)", info)
                avail_match = re.search(r"Available:\s+([0-9.]+)\s+([A-Za-z]+)", info)
                if cap_match:
                    capacity = self._size_to_bytes(cap_match.group(1), cap_match.group(2))
                if alloc_match:
                    allocation = self._size_to_bytes(alloc_match.group(1), alloc_match.group(2))
                if avail_match:
                    available = self._size_to_bytes(avail_match.group(1), avail_match.group(2))
            except Exception:
                pass
            # Use os.statvfs for dir-type pools to get accurate disk usage.
            # virsh pool-info sizes are rounded and can report avail > total.
            if pool_path:
                try:
                    st = os.statvfs(pool_path)
                    capacity = st.f_frsize * st.f_blocks
                    available = st.f_frsize * st.f_bavail
                except Exception:
                    pass
            # Compute real used space from total - available.
            real_used = max(0, capacity - available) if capacity > 0 else allocation
            storage.append(
                {
                    "storage": name,
                    "node": self._default_node_name,
                    "type": pool_type,
                    "content": "images,iso,backup",
                    "shared": 0,
                    "active": active,
                    "avail": available,
                    "used": real_used,
                    "total": capacity,
                    "path": pool_path,
                    "autostart": autostart,
                }
            )
        return storage

    def _discover_libvirt_networks(self) -> list[dict[str, Any]]:
        if not self._libvirt_enabled():
            return []
        try:
            names = [name.strip() for name in self._run_virsh("net-list", "--all", "--name").splitlines() if name.strip()]
        except Exception:
            return []
        bridges: list[dict[str, Any]] = []
        for name in names:
            active = False
            autostart = False
            try:
                info = self._run_virsh("net-info", name)
                active = bool(re.search(r"Active:\s+yes", info, re.IGNORECASE))
                autostart = bool(re.search(r"Autostart:\s+yes", info, re.IGNORECASE))
            except Exception:
                pass
            bridges.append(
                {
                    "name": name,
                    "node": self._default_node_name,
                    "type": "bridge",
                    "active": active,
                    "address": "",
                    "netmask": "",
                    "cidr": "",
                    "bridge_ports": "",
                    "autostart": autostart,
                }
            )
        return bridges

    @staticmethod
    def _size_to_bytes(value: str, unit: str) -> int:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0
        normalized = str(unit or "").strip().lower()
        factors = {
            "b": 1,
            "bytes": 1,
            "kib": 1024,
            "mib": 1024 ** 2,
            "gib": 1024 ** 3,
            "tib": 1024 ** 4,
            "kb": 1000,
            "mb": 1000 ** 2,
            "gb": 1000 ** 3,
            "tb": 1000 ** 4,
        }
        factor = factors.get(normalized)
        if factor is None:
            return 0
        return int(numeric * factor)

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

    def _libvirt_domain_running(self, vmid: int) -> bool | None:
        """Return True if domain is running, False if stopped/shut-off, None if domain doesn't exist."""
        try:
            state = self._run_virsh("domstate", self._libvirt_domain_name(vmid)).strip().lower()
            if state == "running":
                return True
            return False
        except Exception:
            return None

    def _load_vms(self) -> list[dict[str, Any]]:
        payload = self._read_json_file(self._vms_path(), [])
        if not isinstance(payload, list):
            payload = []
        # Overlay with SQLite repository when available
        if self._vm_repo is not None:
            repo_vms = {v["vmid"]: v for v in self._vm_repo.list() if isinstance(v.get("vmid"), int)}
            for item in payload:
                if isinstance(item, dict) and int(item.get("vmid") or 0) > 0:
                    repo_vms[int(item["vmid"])] = item
            payload = list(repo_vms.values())
        vms: list[dict[str, Any]] = []
        needs_write = False
        for item in payload:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_vm_record(item)
            if normalized["vmid"] <= 0 or not normalized["node"]:
                continue
            # Reconcile stored status with actual libvirt domain state so that VMs
            # shut down by autoinstall (poweroff) are not stuck at "running" indefinitely.
            if normalized.get("status") == "running":
                libvirt_running = self._libvirt_domain_running(normalized["vmid"])
                if libvirt_running is False:
                    normalized["status"] = "stopped"
                    item["status"] = "stopped"
                    needs_write = True
            vms.append(normalized)
        if needs_write:
            try:
                self._write_vms(vms)
            except Exception:
                pass
        return sorted(vms, key=lambda item: int(item.get("vmid", 0) or 0))

    def _write_vms(self, vms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = [self._normalize_vm_record(item) for item in vms if isinstance(item, dict)]
        normalized = sorted(normalized, key=lambda item: item["vmid"])
        if self._vm_repo is not None:
            for vm_dict in normalized:
                try:
                    self._vm_repo.save(vm_dict)
                except Exception:  # pragma: no cover
                    pass
        return self._write_json_file(self._vms_path(), normalized)

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

    # ------------------------------------------------------------------
    # libvirt / KVM backend helpers
    # ------------------------------------------------------------------

    def _run_virsh(self, *args: str, input_data: str | None = None) -> str:
        cmd = ["virsh", "--connect", "qemu:///system"] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=input_data,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"virsh {' '.join(args)} failed (rc={result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout.strip()

    def _libvirt_enabled(self) -> bool:
        if not shutil.which("virsh"):
            return False
        try:
            self._run_virsh("list", "--all")
            return True
        except Exception:
            return False

    def _libvirt_domain_name(self, vmid: int) -> str:
        return f"beagle-{int(vmid)}"

    def _libvirt_domain_uuid(self, vmid: int) -> str:
        try:
            return self._run_virsh("domuuid", self._libvirt_domain_name(vmid)).strip()
        except Exception:
            return ""

    def _libvirt_domain_exists(self, vmid: int) -> bool:
        try:
            self._run_virsh("domstate", self._libvirt_domain_name(vmid))
            return True
        except Exception:
            return False

    def _libvirt_pool_exists(self, pool_name: str) -> bool:
        target = str(pool_name or "").strip()
        if not target:
            return False
        try:
            names = [name.strip() for name in self._run_virsh("pool-list", "--all", "--name").splitlines() if name.strip()]
        except Exception:
            return False
        return target in names

    def _ensure_local_pool(self) -> bool:
        if self._libvirt_pool_exists("local"):
            return True
        local_path = self._libvirt_images_dir
        local_path.mkdir(parents=True, exist_ok=True)
        try:
            self._run_virsh("pool-define-as", "local", "dir", "--target", str(local_path))
        except Exception:
            # Pool may already exist in partially-defined state.
            pass
        try:
            self._run_virsh("pool-build", "local")
        except Exception:
            pass
        try:
            self._run_virsh("pool-start", "local")
        except Exception:
            pass
        try:
            self._run_virsh("pool-autostart", "local")
        except Exception:
            pass
        return self._libvirt_pool_exists("local")

    def _resolve_disk_pool_name(self, preferred_pool: str) -> str:
        requested = str(preferred_pool or "local").strip() or "local"
        if self._libvirt_pool_exists(requested):
            return requested
        if requested == "local" and self._ensure_local_pool():
            return "local"
        if self._libvirt_pool_exists("local"):
            return "local"
        available = [
            str(item.get("storage") or "").strip()
            for item in self._discover_libvirt_storage()
            if str(item.get("storage") or "").strip()
        ]
        if available:
            return available[0]
        raise RuntimeError(
            f"no usable libvirt storage pool found (requested '{requested}')"
        )

    def _libvirt_network_exists(self, network_name: str) -> bool:
        target = str(network_name or "").strip()
        if not target:
            return False
        try:
            names = [name.strip() for name in self._run_virsh("net-list", "--all", "--name").splitlines() if name.strip()]
        except Exception:
            return False
        return target in names

    def _ensure_beagle_network(self) -> bool:
        if self._libvirt_network_exists("beagle"):
            return True
        xml = "".join(
            [
                "<network>",
                "<name>beagle</name>",
                "<forward mode='nat'/>",
                "<bridge name='virbr10' stp='on' delay='0'/>",
                "<ip address='192.168.123.1' netmask='255.255.255.0'>",
                "<dhcp><range start='192.168.123.100' end='192.168.123.254'/></dhcp>",
                "</ip>",
                "</network>",
            ]
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
            f.write(xml)
            tmp_path = f.name
        try:
            try:
                self._run_virsh("net-define", tmp_path)
            except Exception:
                pass
        finally:
            os.unlink(tmp_path)
        try:
            self._run_virsh("net-start", "beagle")
        except Exception:
            pass
        try:
            self._run_virsh("net-autostart", "beagle")
        except Exception:
            pass
        return self._libvirt_network_exists("beagle")

    def _resolve_network_name(self, preferred_network: str) -> str:
        requested = str(preferred_network or "default").strip() or "default"
        if self._libvirt_network_exists(requested):
            return requested
        if requested == "beagle" and self._ensure_beagle_network():
            return "beagle"
        if self._libvirt_network_exists("default"):
            return "default"
        available = [
            str(item.get("name") or "").strip()
            for item in self._discover_libvirt_networks()
            if str(item.get("name") or "").strip()
        ]
        if available:
            return available[0]
        raise RuntimeError(
            f"no usable libvirt network found (requested '{requested}')"
        )

    def _libvirt_pool_path(self, pool: str) -> str:
        try:
            out = self._run_virsh("pool-dumpxml", pool)
            m = re.search(r"<path>([^<]+)</path>", out)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
        return str(self._libvirt_images_dir)

    @staticmethod
    def _parse_storage_spec(spec: str) -> tuple[str, str]:
        """Parse 'local:40' or 'local:iso/file.iso,media=cdrom' -> (pool, path_or_size)."""
        if ":" in spec:
            pool, rest = spec.split(":", 1)
            path_part = rest.split(",")[0]
            return pool.strip(), path_part.strip()
        return "local", spec.strip()

    def _generate_domain_xml(self, vmid: int, config: dict[str, Any], *, domain_uuid: str = "") -> str:
        domain_name = self._libvirt_domain_name(vmid)
        memory_mib = int(config.get("memory", 2048) or 2048)
        cores = int(config.get("cores", 2) or 2)

        # Network interface
        net0 = str(config.get("net0", "") or "")
        network_name = "default"
        net_model = "virtio"
        if "bridge=" in net0:
            bm = re.search(r"bridge=([^\s,]+)", net0)
            if bm:
                network_name = bm.group(1)
        network_name = self._resolve_network_name(network_name)
        if net0.startswith("e1000"):
            net_model = "e1000"
        mac_address = ""
        mac_match = re.search(r"macaddr=([0-9A-Fa-f:]{17})", net0)
        if mac_match:
            mac_address = mac_match.group(1).lower()

        # Main disk
        scsi0 = str(config.get("scsi0", "") or "")
        if scsi0:
            pool_name, _ = self._parse_storage_spec(scsi0)
        else:
            pool_name = "local"
        pool_path = self._libvirt_pool_path(pool_name)
        disk_path = f"{pool_path}/{domain_name}-disk.qcow2"

        # CDROM helper
        def _iso_path(ide_spec: str) -> str:
            if not ide_spec:
                return ""
            p_name, path_part = self._parse_storage_spec(ide_spec)
            try:
                p_root = self._libvirt_pool_path(p_name)
            except Exception:
                p_root = pool_path
            filename = path_part.split("/")[-1]
            return f"{p_root}/{filename}"

        ubuntu_iso = _iso_path(str(config.get("ide2", "") or ""))
        seed_iso = _iso_path(str(config.get("ide3", "") or ""))

        # Kernel/initrd args
        args_str = str(config.get("args", "") or "")
        kernel_path = ""
        initrd_path = ""
        append_str = ""
        if args_str:
            km = re.search(r"-kernel\s+(\S+)", args_str)
            im = re.search(r"-initrd\s+(\S+)", args_str)
            am = re.search(r"-append\s+'([^']+)'", args_str) or re.search(r'-append\s+"([^"]+)"', args_str)
            if km:
                kernel_path = km.group(1)
            if im:
                initrd_path = im.group(1)
            if am:
                append_str = am.group(1)

        nvram_dir = "/var/lib/libvirt/qemu/nvram"
        nvram_path = f"{nvram_dir}/{domain_name}_VARS.fd"

        lines = [
            "<domain type='kvm' xmlns:qemu='http://libvirt.org/schemas/domain/qemu/1.0'>",
            f"  <name>{domain_name}</name>",
        ]
        if str(domain_uuid or "").strip():
            lines.append(f"  <uuid>{str(domain_uuid).strip()}</uuid>")
        lines += [
            f"  <memory unit='MiB'>{memory_mib}</memory>",
            f"  <currentMemory unit='MiB'>{memory_mib}</currentMemory>",
            f"  <vcpu placement='static'>{cores}</vcpu>",
            "  <os>",
            "    <type arch='x86_64' machine='q35'>hvm</type>",
            "    <loader readonly='yes' type='pflash'>/usr/share/OVMF/OVMF_CODE_4M.fd</loader>",
            f"    <nvram template='/usr/share/OVMF/OVMF_VARS_4M.fd'>{nvram_path}</nvram>",
            "  </os>",
            "  <features><acpi/><apic/></features>",
            "  <cpu mode='host-passthrough' check='none' migratable='on'/>",
            "  <clock offset='utc'>",
            "    <timer name='rtc' tickpolicy='catchup'/>",
            "    <timer name='pit' tickpolicy='delay'/>",
            "    <timer name='hpet' present='no'/>",
            "  </clock>",
            "  <on_poweroff>destroy</on_poweroff>",
            "  <on_reboot>restart</on_reboot>",
            "  <on_crash>destroy</on_crash>",
            "  <devices>",
            "    <emulator>/usr/bin/qemu-system-x86_64</emulator>",
            "    <disk type='file' device='disk'>",
            "      <driver name='qemu' type='qcow2' cache='none' discard='unmap'/>",
            f"      <source file='{disk_path}'/>",
            "      <target dev='vda' bus='virtio'/>",
            "      <boot order='1'/>",
            "    </disk>",
        ]

        if ubuntu_iso:
            lines += [
                "    <disk type='file' device='cdrom'>",
                "      <driver name='qemu' type='raw'/>",
                f"      <source file='{ubuntu_iso}'/>",
                "      <target dev='sda' bus='sata'/>",
                "      <readonly/>",
                "      <boot order='2'/>",
                "    </disk>",
            ]

        if seed_iso:
            lines += [
                "    <disk type='file' device='cdrom'>",
                "      <driver name='qemu' type='raw'/>",
                f"      <source file='{seed_iso}'/>",
                "      <target dev='sdb' bus='sata'/>",
                "      <readonly/>",
                "    </disk>",
            ]

        lines += [
            f"    <interface type='network'>",
            f"      <source network='{network_name}'/>",
        ]
        if mac_address:
            lines += [
                f"      <mac address='{mac_address}'/>",
            ]
        lines += [
            f"      <model type='{net_model}'/>",
            "    </interface>",
            "    <serial type='pty'><target type='isa-serial' port='0'/></serial>",
            "    <console type='pty'><target type='serial' port='0'/></console>",
            "    <channel type='unix'>",
            "      <target type='virtio' name='org.qemu.guest_agent.0'/>",
            "    </channel>",
            "    <graphics type='vnc' port='-1' autoport='yes' listen='127.0.0.1'>",
            "      <listen type='address' address='127.0.0.1'/>",
            "    </graphics>",
            "    <video><model type='vga' vram='16384'/></video>",
            "    <rng model='virtio'><backend model='random'>/dev/urandom</backend></rng>",
            "    <memballoon model='virtio'/>",
            "  </devices>",
        ]

        if kernel_path and initrd_path:
            lines += [
                "  <qemu:commandline>",
                f"    <qemu:arg value='-kernel'/>",
                f"    <qemu:arg value='{kernel_path}'/>",
                f"    <qemu:arg value='-initrd'/>",
                f"    <qemu:arg value='{initrd_path}'/>",
                f"    <qemu:arg value='-append'/>",
                f"    <qemu:arg value='{append_str}'/>",
                "  </qemu:commandline>",
            ]

        # libvirt AppArmor profiles do not include qemu:commandline kernel/initrd
        # paths; disable LSM labeling for this transient install domain only.
        lines.append("  <seclabel type='none'/>")
        lines.append("</domain>")
        return "\n".join(lines)

    def _ensure_libvirt_disk(self, vmid: int, config: dict[str, Any]) -> None:
        scsi0 = str(config.get("scsi0", "") or "")
        pool_name = "local"
        size_gb = 32
        if scsi0:
            pool_name, size_or_path = self._parse_storage_spec(scsi0)
            try:
                size_gb = int(size_or_path)
            except (ValueError, TypeError):
                size_gb = 32
        pool_name = self._resolve_disk_pool_name(pool_name)
        domain_name = self._libvirt_domain_name(vmid)
        vol_name = f"{domain_name}-disk.qcow2"
        try:
            self._run_virsh("vol-info", "--pool", pool_name, vol_name)
            return
        except Exception:
            pass
        self._run_virsh("vol-create-as", pool_name, vol_name, f"{size_gb}G", "--format", "qcow2")

    def _provision_libvirt_vm(self, vmid: int) -> None:
        record = self._find_vm(vmid)
        if record is None:
            raise RuntimeError(f"VM {int(vmid)} not found in beagle provider state")
        node = str(record.get("node") or self._default_node_name).strip() or self._default_node_name
        config = self.get_vm_config(node, vmid)
        self._ensure_libvirt_disk(vmid, config)
        existing_uuid = self._libvirt_domain_uuid(vmid) if self._libvirt_domain_exists(vmid) else ""
        xml = self._generate_domain_xml(vmid, config, domain_uuid=existing_uuid)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
            f.write(xml)
            tmp_path = f.name
        try:
            self._run_virsh("define", tmp_path)
        finally:
            os.unlink(tmp_path)

    def _libvirt_guest_ipv4(self, vmid: int) -> str:
        domain_name = self._libvirt_domain_name(vmid)
        try:
            out = self._run_virsh("domifaddr", domain_name, "--source", "agent")
        except Exception:
            try:
                out = self._run_virsh("domifaddr", domain_name, "--source", "lease")
            except Exception:
                return ""
        for line in out.splitlines():
            m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/", line)
            if m:
                ip = m.group(1)
                if not ip.startswith("127.") and not ip.startswith("169.254."):
                    return ip
        return ""

    # ------------------------------------------------------------------

    def next_vmid(self) -> int:
        existing = [int(item.get("vmid", 0) or 0) for item in self._load_vms()]
        return max([99, *existing]) + 1

    def list_storage_inventory(self) -> list[dict[str, Any]]:
        return self._load_storage()

    def list_nodes(self) -> list[dict[str, Any]]:
        return self._load_nodes()

    def list_bridges(self, node: str = "") -> list[dict[str, Any]]:
        bridges = self._load_bridges()
        if node:
            bridges = [b for b in bridges if b.get("node") == node]
        return bridges

    def get_guest_network_interfaces(
        self,
        vmid: int,
        *,
        timeout_seconds: float | None = None,
    ) -> list[dict[str, Any]]:
        del timeout_seconds
        if self._libvirt_enabled() and self._libvirt_domain_exists(vmid):
            ip = self._libvirt_guest_ipv4(vmid)
            if ip:
                ifaces = [
                    {
                        "name": "eth0",
                        "ip-addresses": [
                            {"ip-address-type": "ipv4", "ip-address": ip, "prefix": 24}
                        ],
                    }
                ]
                self._write_guest_interfaces(vmid, ifaces)
                return ifaces
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

    def delete_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str:
        del timeout
        target_vmid = int(vmid)
        record = self._find_vm(target_vmid)
        if record is None:
            raise RuntimeError(f"VM {target_vmid} not found in beagle provider state")
        if self._libvirt_enabled():
            domain_name = self._libvirt_domain_name(target_vmid)
            try:
                self._run_virsh("destroy", domain_name)
            except Exception:
                pass
            try:
                self._run_virsh("undefine", domain_name, "--nvram", "--remove-all-storage")
            except Exception:
                self._run_virsh("undefine", domain_name)

        remaining = [
            item
            for item in self._load_vms()
            if int(item.get("vmid", 0) or 0) != target_vmid
        ]
        self._write_vms(remaining)

        node = str(record.get("node") or self._default_node_name).strip() or self._default_node_name
        self._vm_config_path(node, target_vmid).unlink(missing_ok=True)
        self._guest_interfaces_path(target_vmid).unlink(missing_ok=True)
        self._scheduled_restart_path(target_vmid).unlink(missing_ok=True)
        shutil.rmtree(self._guest_exec_dir() / str(target_vmid), ignore_errors=True)

        return f"deleted beagle vm {target_vmid}"

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
        if self._libvirt_enabled():
            # Keep libvirt XML aligned with the latest provider config (boot order,
            # installer media cleanup, qemu args) before every start.
            self._provision_libvirt_vm(vmid)
            self._run_virsh("start", self._libvirt_domain_name(vmid))
        record["status"] = "running"
        self._replace_vm(record)
        return f"started beagle vm {int(vmid)}"

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
        if self._libvirt_enabled() and self._libvirt_domain_exists(vmid):
            self._run_virsh("reboot", self._libvirt_domain_name(vmid))
        record["status"] = "running"
        self._replace_vm(record)
        node = str(record.get("node") or self._default_node_name).strip() or self._default_node_name
        config = self.get_vm_config(node, vmid)
        config["last_reboot_at"] = int(time.time())
        self._write_vm_config(node, vmid, config)
        return f"rebooted beagle vm {int(vmid)}"

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
        if self._libvirt_enabled() and self._libvirt_domain_exists(vmid):
            try:
                self._run_virsh("destroy", self._libvirt_domain_name(vmid))
            except Exception:
                pass
        record["status"] = "stopped"
        self._replace_vm(record)
        return f"stopped beagle vm {int(vmid)}"

    def resume_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str:
        """Resume a paused/suspended VM. Handles the case where QEMU -S flag leaves VMs paused."""
        del timeout
        record = self._find_vm(vmid)
        if record is None:
            raise RuntimeError(f"VM {int(vmid)} not found in beagle provider state")
        if self._libvirt_enabled() and self._libvirt_domain_exists(vmid):
            domain_name = self._libvirt_domain_name(vmid)
            try:
                # Check domain state; if paused, resume it
                state = self._run_virsh("domstate", domain_name).strip().lower()
                if "paused" in state or "suspended" in state:
                    self._run_virsh("resume", domain_name)
            except Exception:
                # Ignore if VM is not paused or doesn't exist
                pass
        return f"resumed beagle vm {int(vmid)}"

    def guest_exec_bash(
        self,
        vmid: int,
        command: str,
        *,
        timeout_seconds: int | None = None,
        request_timeout: float | None = None,
    ) -> dict[str, Any]:
        del request_timeout
        target_vmid = int(vmid)
        if self._find_vm(target_vmid) is None:
            raise RuntimeError(f"VM {target_vmid} not found in beagle provider state")

        if self._libvirt_enabled():
            request = {
                "execute": "guest-exec",
                "arguments": {
                    "path": "/bin/bash",
                    "arg": ["-lc", str(command or "")],
                    "capture-output": True,
                },
            }
            try:
                response = self._run_virsh(
                    "qemu-agent-command",
                    self._libvirt_domain_name(target_vmid),
                    json.dumps(request),
                    input_data=None,
                )
                payload = json.loads(response or "{}")
                result = payload.get("return") if isinstance(payload, dict) else None
                if isinstance(result, dict) and result.get("pid") is not None:
                    return {"pid": int(result.get("pid") or 0)}
            except Exception:
                pass

        del timeout_seconds
        pid = self._next_counter(f"guest-exec-{target_vmid}")
        status_payload = {
            "exited": True,
            "exitcode": 0,
            "out-data": "",
            "err-data": "",
            "provider": "beagle",
            "command": str(command or ""),
            "pid": pid,
            "vmid": target_vmid,
        }
        self._write_json_file(self._guest_exec_status_path(target_vmid, pid), status_payload)
        return {"pid": pid}

    def guest_exec_status(
        self,
        vmid: int,
        pid: int,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        target_vmid = int(vmid)
        if self._libvirt_enabled() and self._libvirt_domain_exists(target_vmid):
            request = {
                "execute": "guest-exec-status",
                "arguments": {"pid": int(pid)},
            }
            try:
                response = self._run_virsh(
                    "qemu-agent-command",
                    self._libvirt_domain_name(target_vmid),
                    json.dumps(request),
                    input_data=None,
                )
                payload = json.loads(response or "{}")
                result = payload.get("return") if isinstance(payload, dict) else None
                if isinstance(result, dict):
                    return result
            except Exception:
                pass

        del timeout
        payload = self._read_json_file(self._guest_exec_status_path(target_vmid, pid), {})
        return payload if isinstance(payload, dict) else {}

    def guest_exec_script_text(
        self,
        vmid: int,
        script: str,
        *,
        poll_attempts: int = 300,
        poll_interval_seconds: float = 2.0,
    ) -> tuple[int, str, str]:
        payload = self.guest_exec_bash(vmid, script)
        pid = int(payload.get("pid") or 0)
        if pid <= 0:
            return 1, "", "guest exec did not return a pid"

        last_status: dict[str, Any] = {}
        attempts = max(int(poll_attempts or 0), 1)
        interval = max(float(poll_interval_seconds or 0), 0.0)
        for _attempt in range(attempts):
            last_status = self.guest_exec_status(vmid, pid)
            if bool(last_status.get("exited")):
                break
            if interval > 0:
                time.sleep(interval)
        else:
            return 124, "", "guest exec timed out"

        exitcode = int(last_status.get("exitcode") or 0)

        def _decode(value: Any) -> str:
            text = str(value or "")
            if not text:
                return ""
            try:
                return base64.b64decode(text.encode("ascii"), validate=True).decode("utf-8", errors="replace")
            except Exception:
                return text

        return exitcode, _decode(last_status.get("out-data")), _decode(last_status.get("err-data"))

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

    def snapshot_vm(
        self,
        vmid: int,
        snapshot_name: str,
        *,
        description: str = "",
        timeout: float | None | object = None,
    ) -> str:
        del timeout
        target_vmid = int(vmid)
        record = self._find_vm(target_vmid)
        if record is None:
            raise RuntimeError(f"VM {target_vmid} not found in beagle provider state")
        snap_name = str(snapshot_name or "").strip() or f"snap-{int(time.time())}"
        node = str(record.get("node") or self._default_node_name).strip() or self._default_node_name
        config = self.get_vm_config(node, target_vmid)
        snapshots = config.get("_snapshots")
        if not isinstance(snapshots, list):
            snapshots = []
        snapshots.append(
            {
                "name": snap_name,
                "description": str(description or ""),
                "created_at": int(time.time()),
                "provider": "beagle",
            }
        )
        config["_snapshots"] = snapshots
        self._write_vm_config(node, target_vmid, config)

        if self._libvirt_enabled() and self._libvirt_domain_exists(target_vmid):
            args = ["snapshot-create-as", self._libvirt_domain_name(target_vmid), snap_name]
            desc = str(description or "").strip()
            if desc:
                args.extend(["--description", desc])
            args.append("--atomic")
            self._run_virsh(*args)

        return f"created snapshot {snap_name} for beagle vm {target_vmid}"

    def delete_vm_snapshot(
        self,
        vmid: int,
        snapshot_name: str,
        *,
        timeout: float | None | object = None,
    ) -> str:
        del timeout
        target_vmid = int(vmid)
        record = self._find_vm(target_vmid)
        if record is None:
            raise RuntimeError(f"VM {target_vmid} not found in beagle provider state")

        snap_name = str(snapshot_name or "").strip()
        if not snap_name:
            raise RuntimeError("snapshot_name is required")

        node = str(record.get("node") or self._default_node_name).strip() or self._default_node_name
        config = self.get_vm_config(node, target_vmid)
        snapshots = config.get("_snapshots")
        updated_snapshots: list[dict[str, Any]] = []
        found = False
        if isinstance(snapshots, list):
            for item in snapshots:
                if not isinstance(item, dict):
                    continue
                if str(item.get("name") or "").strip() == snap_name:
                    found = True
                    continue
                updated_snapshots.append(dict(item))

        if self._libvirt_enabled() and self._libvirt_domain_exists(target_vmid):
            try:
                self._run_virsh("snapshot-delete", self._libvirt_domain_name(target_vmid), snap_name, "--metadata")
            except Exception:
                try:
                    self._run_virsh("snapshot-delete", self._libvirt_domain_name(target_vmid), snap_name)
                except Exception:
                    if not found:
                        raise RuntimeError(f"snapshot {snap_name!r} not found for VM {target_vmid}")
        elif not found:
            raise RuntimeError(f"snapshot {snap_name!r} not found for VM {target_vmid}")

        config["_snapshots"] = updated_snapshots
        self._write_vm_config(node, target_vmid, config)
        return f"deleted snapshot {snap_name} for beagle vm {target_vmid}"

    def reset_vm_to_snapshot(
        self,
        vmid: int,
        snapshot_name: str,
        *,
        timeout: float | None | object = None,
    ) -> str:
        del timeout
        target_vmid = int(vmid)
        record = self._find_vm(target_vmid)
        if record is None:
            raise RuntimeError(f"VM {target_vmid} not found in beagle provider state")

        snap_name = str(snapshot_name or "").strip()
        if not snap_name:
            raise RuntimeError("snapshot_name is required")

        node = str(record.get("node") or self._default_node_name).strip() or self._default_node_name
        config = self.get_vm_config(node, target_vmid)
        snapshots = config.get("_snapshots")
        known_snapshots = {
            str(item.get("name") or "").strip()
            for item in (snapshots or [])
            if isinstance(item, dict)
        }

        if self._libvirt_enabled() and self._libvirt_domain_exists(target_vmid):
            if str(record.get("status") or "").strip().lower() == "running":
                try:
                    self._run_virsh("destroy", self._libvirt_domain_name(target_vmid))
                except Exception:
                    pass
            self._run_virsh(
                "snapshot-revert",
                self._libvirt_domain_name(target_vmid),
                snap_name,
                "--force",
            )
        elif snap_name not in known_snapshots:
            raise RuntimeError(f"snapshot {snap_name!r} not found for VM {target_vmid}")

        record["status"] = "stopped"
        self._replace_vm(record)
        return f"reset beagle vm {target_vmid} to snapshot {snap_name}"

    def clone_vm(
        self,
        source_vmid: int,
        target_vmid: int,
        *,
        name: str = "",
        timeout: float | None | object = None,
    ) -> str:
        del timeout
        src_vmid = int(source_vmid)
        dst_vmid = int(target_vmid)
        source_record = self._find_vm(src_vmid)
        if source_record is None:
            raise RuntimeError(f"VM {src_vmid} not found in beagle provider state")
        if self._find_vm(dst_vmid) is not None:
            raise RuntimeError(f"VM {dst_vmid} already exists in beagle provider state")

        node = str(source_record.get("node") or self._default_node_name).strip() or self._default_node_name
        source_config = self.get_vm_config(node, src_vmid)
        clone_config = dict(source_config)
        clone_config["vmid"] = dst_vmid
        clone_config["node"] = node
        clone_config["name"] = str(name or f"{source_record.get('name', f'vm-{src_vmid}')}-clone").strip()
        clone_config["status"] = "stopped"
        clone_config.pop("last_reboot_at", None)

        self.create_vm(dst_vmid, clone_config)
        interfaces = self._read_guest_interfaces(src_vmid)
        if isinstance(interfaces, list) and interfaces:
            self._write_guest_interfaces(dst_vmid, interfaces)

        if self._libvirt_enabled() and self._libvirt_domain_exists(src_vmid):
            source_scsi = str(source_config.get("scsi0") or "")
            preferred_pool, _ = self._parse_storage_spec(source_scsi) if source_scsi else ("local", "")
            pool_name = self._resolve_disk_pool_name(preferred_pool)
            src_vol = f"{self._libvirt_domain_name(src_vmid)}-disk.qcow2"
            dst_vol = f"{self._libvirt_domain_name(dst_vmid)}-disk.qcow2"
            try:
                self._run_virsh("vol-clone", "--pool", pool_name, src_vol, dst_vol)
            except Exception:
                self._ensure_libvirt_disk(dst_vmid, clone_config)
            self._provision_libvirt_vm(dst_vmid)

        return f"cloned beagle vm {src_vmid} to {dst_vmid}"

    def get_console_proxy(
        self,
        vmid: int,
        *,
        token: str = "",
        timeout: float | None | object = None,
    ) -> dict[str, Any]:
        del timeout
        target_vmid = int(vmid)
        if self._find_vm(target_vmid) is None:
            raise RuntimeError(f"VM {target_vmid} not found in beagle provider state")

        response: dict[str, Any] = {
            "provider": "beagle",
            "vmid": target_vmid,
            "available": False,
            "scheme": "vnc",
            "host": "127.0.0.1",
            "port": 0,
            "token": str(token or f"vm-{target_vmid}"),
        }

        if not self._libvirt_enabled() or not self._libvirt_domain_exists(target_vmid):
            return response

        display = self._run_virsh("vncdisplay", self._libvirt_domain_name(target_vmid)).strip()
        port = 0
        if display.startswith(":") and display[1:].isdigit():
            port = 5900 + int(display[1:])
        elif ":" in display:
            tail = display.rsplit(":", 1)[-1]
            if tail.isdigit():
                port = 5900 + int(tail)

        if port > 0:
            response["available"] = True
            response["port"] = int(port)
        return response

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
