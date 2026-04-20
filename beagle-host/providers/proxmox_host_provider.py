from __future__ import annotations

import base64
import subprocess
import time
from typing import Any, Callable, Iterable, Mapping


class ProxmoxHostProvider:
    def __init__(
        self,
        *,
        run_json: Callable[..., Any],
        run_text: Callable[..., str],
        run_checked: Callable[..., str],
        cache_get: Callable[[str, float], Any] | None = None,
        cache_put: Callable[[str, Any], Any] | None = None,
    ) -> None:
        self._run_json = run_json
        self._run_text = run_text
        self._run_checked = run_checked
        self._cache_get = cache_get
        self._cache_put = cache_put

    def _get_cached(self, key: str, ttl_seconds: float) -> Any:
        if not key or ttl_seconds <= 0 or self._cache_get is None:
            return None
        return self._cache_get(key, ttl_seconds)

    def _put_cached(self, key: str, value: Any) -> Any:
        if not key or self._cache_put is None:
            return value
        return self._cache_put(key, value)

    def next_vmid(self) -> int:
        raw = self._run_text(["pvesh", "get", "/cluster/nextid"])
        values = str(raw).strip().splitlines()
        if not values:
            raise RuntimeError("failed to determine next VMID")
        return int(values[-1])

    def list_storage_inventory(self) -> list[dict[str, Any]]:
        payload = self._run_json(["pvesh", "get", "/storage", "--output-format", "json"])
        return payload if isinstance(payload, list) else []

    def list_nodes(self) -> list[dict[str, Any]]:
        payload = self._run_json(["pvesh", "get", "/nodes", "--output-format", "json"])
        nodes: list[dict[str, Any]] = []
        if not isinstance(payload, list):
            return nodes
        for item in payload:
            node_name = str(item.get("node", "")).strip()
            if not node_name:
                continue
            nodes.append(
                {
                    "name": node_name,
                    "status": str(item.get("status", "unknown")).strip() or "unknown",
                    "cpu": float(item.get("cpu", 0) or 0),
                    "mem": int(item.get("mem", 0) or 0),
                    "maxmem": int(item.get("maxmem", 0) or 0),
                    "maxcpu": int(item.get("maxcpu", 0) or 0),
                }
            )
        return nodes

    def list_bridges(self, node: str = "") -> list[dict[str, Any]]:
        nodes = [node] if node else [n["name"] for n in self.list_nodes()]
        bridges: list[dict[str, Any]] = []
        seen: set[str] = set()
        for target_node in nodes:
            payload = self._run_json(
                ["pvesh", "get", f"/nodes/{target_node}/network", "--output-format", "json"]
            )
            if not isinstance(payload, list):
                continue
            for item in payload:
                iface_type = str(item.get("type", "")).strip()
                if iface_type != "bridge":
                    continue
                iface_name = str(item.get("iface", "")).strip()
                if not iface_name or iface_name in seen:
                    continue
                seen.add(iface_name)
                bridges.append(
                    {
                        "name": iface_name,
                        "node": target_node,
                        "type": iface_type,
                        "active": bool(int(item.get("active", 0) or 0)),
                        "address": str(item.get("address", "") or "").strip(),
                        "netmask": str(item.get("netmask", "") or "").strip(),
                        "cidr": str(item.get("cidr", "") or "").strip(),
                        "bridge_ports": str(item.get("bridge_ports", "") or "").strip(),
                        "autostart": bool(int(item.get("autostart", 0) or 0)),
                    }
                )
        return sorted(bridges, key=lambda b: b["name"])

    def get_guest_network_interfaces(
        self,
        vmid: int,
        *,
        timeout_seconds: float | None = None,
    ) -> list[dict[str, Any]]:
        payload = self._run_json(
            ["qm", "guest", "cmd", str(int(vmid)), "network-get-interfaces"],
            timeout=timeout_seconds,
        )
        return payload if isinstance(payload, list) else []

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
        resources = self._run_json(["pvesh", "get", "/cluster/resources", "--type", "vm", "--output-format", "json"])
        vms: list[Any] = []
        if not isinstance(resources, list):
            return vms
        for item in resources:
            if item.get("type") != "qemu" or item.get("vmid") is None or not item.get("node"):
                continue
            if vm_summary_factory is not None:
                vms.append(vm_summary_factory(item))
                continue
            vms.append(item)
        vms = sorted(vms, key=self._vm_sort_key)
        return self._put_cached(cache_key, vms)

    @staticmethod
    def _vm_sort_key(vm: Any) -> int:
        if hasattr(vm, "vmid"):
            try:
                return int(getattr(vm, "vmid"))
            except (TypeError, ValueError):
                return 0
        if isinstance(vm, dict):
            try:
                return int(vm.get("vmid", 0))
            except (TypeError, ValueError):
                return 0
        return 0

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
        payload = self._run_json(["pvesh", "get", f"/nodes/{node}/qemu/{int(vmid)}/config", "--output-format", "json"])
        if isinstance(payload, dict):
            return self._put_cached(cache_key, payload)
        return {}

    @staticmethod
    def _flatten_option_pairs(options: Mapping[str, Any] | Iterable[tuple[str, Any]]) -> list[str]:
        args: list[str] = []
        if isinstance(options, Mapping):
            items: Iterable[tuple[str, Any]] = options.items()
        else:
            items = options
        for key, value in items:
            flag = str(key)
            if not flag.startswith("--"):
                flag = f"--{flag}"
            args.extend([flag, "" if value is None else str(value)])
        return args

    def create_vm(
        self,
        vmid: int,
        options: Mapping[str, Any] | Iterable[tuple[str, Any]],
        *,
        timeout: float | None | object = None,
    ) -> str:
        command = ["qm", "create", str(int(vmid))]
        command.extend(self._flatten_option_pairs(options))
        return self._run_checked(command, timeout=timeout)

    def set_vm_options(
        self,
        vmid: int,
        options: Mapping[str, Any] | Iterable[tuple[str, Any]],
        *,
        timeout: float | None | object = None,
    ) -> str:
        command = ["qm", "set", str(int(vmid))]
        command.extend(self._flatten_option_pairs(options))
        return self._run_checked(command, timeout=timeout)

    def delete_vm_options(
        self,
        vmid: int,
        option_names: Iterable[str],
        *,
        timeout: float | None | object = None,
    ) -> None:
        for name in option_names:
            self._run_checked(
                ["qm", "set", str(int(vmid)), "--delete", str(name)],
                timeout=timeout,
            )

    def delete_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str:
        return self._run_checked(
            ["qm", "destroy", str(int(vmid)), "--purge", "1"],
            timeout=timeout,
        )

    def set_vm_description(
        self,
        vmid: int,
        description: str,
        *,
        timeout: float | None | object = None,
    ) -> str:
        return self._run_checked(
            ["qm", "set", str(int(vmid)), "--description", str(description)],
            timeout=timeout,
        )

    def set_vm_boot_order(
        self,
        vmid: int,
        order: str,
        *,
        timeout: float | None | object = None,
    ) -> str:
        return self._run_checked(
            ["qm", "set", str(int(vmid)), "--boot", str(order)],
            timeout=timeout,
        )

    def start_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str:
        return self._run_checked(["qm", "start", str(int(vmid))], timeout=timeout)

    def reboot_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str:
        return self._run_checked(["qm", "reboot", str(int(vmid))], timeout=timeout)

    def stop_vm(
        self,
        vmid: int,
        *,
        skiplock: bool = False,
        timeout: float | None | object = None,
    ) -> str:
        command = ["qm", "stop", str(int(vmid))]
        if skiplock:
            command.extend(["--skiplock", "1"])
        return self._run_checked(command, timeout=timeout)

    def resume_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str:
        """Resume a paused/suspended VM. Handles the case where QEMU -S flag leaves VMs paused."""
        # In Proxmox, paused VMs can be resumed via 'qm resume' if they exist
        try:
            return self._run_checked(["qm", "resume", str(int(vmid))], timeout=timeout)
        except Exception:
            # VM might not be paused or not exist; ignore gracefully
            return f"resume attempted for proxmox vm {int(vmid)}"

    def guest_exec_bash(
        self,
        vmid: int,
        command: str,
        *,
        timeout_seconds: int | None = None,
        request_timeout: float | None = None,
    ) -> dict[str, Any]:
        guest_command = ["qm", "guest", "exec", str(int(vmid))]
        if timeout_seconds is not None:
            guest_command.extend(["--timeout", str(int(timeout_seconds))])
        guest_command.extend(["--", "bash", "-lc", str(command)])
        payload = self._run_json(guest_command, timeout=request_timeout)
        return payload if isinstance(payload, dict) else {}

    def guest_exec_status(
        self,
        vmid: int,
        pid: int,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        payload = self._run_json(
            ["qm", "guest", "exec-status", str(int(vmid)), str(int(pid))],
            timeout=timeout,
        )
        return payload if isinstance(payload, dict) else {}

    def guest_exec_script_text(
        self,
        vmid: int,
        script: str,
        *,
        poll_attempts: int = 300,
        poll_interval_seconds: float = 2.0,
    ) -> tuple[int, str, str]:
        encoded = base64.b64encode(str(script).encode("utf-8")).decode("ascii")
        runner = (
            "set -euo pipefail\n"
            "tmp_script=$(mktemp /tmp/beagle-guest-XXXXXX.sh)\n"
            "tmp_b64=$(mktemp /tmp/beagle-guest-XXXXXX.b64)\n"
            "cleanup() { rm -f \"$tmp_script\" \"$tmp_b64\"; }\n"
            "trap cleanup EXIT\n"
            "cat > \"$tmp_b64\" <<'__BEAGLE_B64__'\n"
            f"{encoded}\n"
            "__BEAGLE_B64__\n"
            "base64 -d \"$tmp_b64\" > \"$tmp_script\"\n"
            "chmod +x \"$tmp_script\"\n"
            "\"$tmp_script\"\n"
        )
        payload = self.guest_exec_bash(int(vmid), runner)
        if not payload:
            return 1, "", ""

        pid = payload.get("pid")
        if pid is not None:
            for _ in range(max(1, int(poll_attempts))):
                time.sleep(max(0.1, float(poll_interval_seconds)))
                status = self.guest_exec_status(int(vmid), int(pid), timeout=None)
                if not status or not status.get("exited"):
                    continue
                exitcode = int(status.get("exitcode", 0) or 0)
                stdout = str(status.get("out-data", "") or "").strip()
                stderr = str(status.get("err-data", "") or "").strip()
                return exitcode, stdout, stderr
            return 1, "", f"qm guest exec timed out for VM {int(vmid)} (pid {pid})"

        exitcode = int(payload.get("exitcode", 0) or 0)
        stdout = str(payload.get("out-data", "") or "").strip()
        stderr = str(payload.get("err-data", "") or "").strip()
        return exitcode, stdout, stderr

    def schedule_vm_restart_after_stop(
        self,
        vmid: int,
        *,
        wait_timeout_seconds: int,
    ) -> int:
        wait_timeout = max(60, int(wait_timeout_seconds or 60))
        script = "\n".join(
            [
                "trap 'exit 0' TERM INT",
                f"deadline=$((SECONDS + {wait_timeout}))",
                "while (( SECONDS < deadline )); do",
                f"  status=$(qm status {int(vmid)} 2>/dev/null | awk '{{print $2}}')",
                "  if [[ \"$status\" == \"stopped\" ]]; then",
                f"    qm start {int(vmid)} >/dev/null 2>&1 || true",
                "    exit 0",
                "  fi",
                "  sleep 5",
                "done",
                f"qm stop {int(vmid)} --skiplock 1 >/dev/null 2>&1 || true",
                f"qm start {int(vmid)} >/dev/null 2>&1 || true",
            ]
        )
        process = subprocess.Popen(
            ["/bin/bash", "-lc", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return int(process.pid)

    def get_guest_ipv4(
        self,
        vmid: int,
        *,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
        enable_lookup: bool = True,
        timeout_seconds: float | None = None,
    ) -> str:
        if not enable_lookup:
            return ""
        cached = self._get_cached(cache_key, cache_ttl_seconds)
        if isinstance(cached, str):
            return cached
        for iface in self.get_guest_network_interfaces(int(vmid), timeout_seconds=timeout_seconds):
            for address in iface.get("ip-addresses", []):
                ip = str(address.get("ip-address", ""))
                if address.get("ip-address-type") != "ipv4":
                    continue
                if not ip or ip.startswith("127.") or ip.startswith("169.254."):
                    continue
                return str(self._put_cached(cache_key, ip))
        return ""
