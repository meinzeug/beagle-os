from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Protocol


class HostProvider(Protocol):
    def next_vmid(self) -> int: ...

    def list_storage_inventory(self) -> list[dict[str, Any]]: ...

    def list_nodes(self) -> list[dict[str, Any]]: ...

    def get_guest_network_interfaces(
        self,
        vmid: int,
        *,
        timeout_seconds: float | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_vms(
        self,
        *,
        refresh: bool = False,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
        vm_summary_factory: Callable[[dict[str, Any]], Any] | None = None,
    ) -> list[Any]: ...

    def get_vm_config(
        self,
        node: str,
        vmid: int,
        *,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
    ) -> dict[str, Any]: ...

    def create_vm(
        self,
        vmid: int,
        options: Mapping[str, Any] | Iterable[tuple[str, Any]],
        *,
        timeout: float | None | object = None,
    ) -> str: ...

    def set_vm_options(
        self,
        vmid: int,
        options: Mapping[str, Any] | Iterable[tuple[str, Any]],
        *,
        timeout: float | None | object = None,
    ) -> str: ...

    def delete_vm_options(
        self,
        vmid: int,
        option_names: Iterable[str],
        *,
        timeout: float | None | object = None,
    ) -> None: ...

    def delete_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str: ...

    def set_vm_description(
        self,
        vmid: int,
        description: str,
        *,
        timeout: float | None | object = None,
    ) -> str: ...

    def set_vm_boot_order(
        self,
        vmid: int,
        order: str,
        *,
        timeout: float | None | object = None,
    ) -> str: ...

    def start_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str: ...

    def reboot_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str: ...

    def stop_vm(
        self,
        vmid: int,
        *,
        skiplock: bool = False,
        timeout: float | None | object = None,
    ) -> str: ...

    def resume_vm(
        self,
        vmid: int,
        *,
        timeout: float | None | object = None,
    ) -> str: ...

    def guest_exec_bash(
        self,
        vmid: int,
        command: str,
        *,
        timeout_seconds: int | None = None,
        request_timeout: float | None = None,
    ) -> dict[str, Any]: ...

    def guest_exec_status(
        self,
        vmid: int,
        pid: int,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]: ...

    def guest_exec_script_text(
        self,
        vmid: int,
        script: str,
        *,
        poll_attempts: int = 300,
        poll_interval_seconds: float = 2.0,
    ) -> tuple[int, str, str]: ...

    def schedule_vm_restart_after_stop(
        self,
        vmid: int,
        *,
        wait_timeout_seconds: int,
    ) -> int: ...

    def snapshot_vm(
        self,
        vmid: int,
        snapshot_name: str,
        *,
        description: str = "",
        timeout: float | None | object = None,
    ) -> str: ...

    def reset_vm_to_snapshot(
        self,
        vmid: int,
        snapshot_name: str,
        *,
        timeout: float | None | object = None,
    ) -> str: ...

    def clone_vm(
        self,
        source_vmid: int,
        target_vmid: int,
        *,
        name: str = "",
        timeout: float | None | object = None,
    ) -> str: ...

    def get_console_proxy(
        self,
        vmid: int,
        *,
        token: str = "",
        timeout: float | None | object = None,
    ) -> dict[str, Any]: ...

    def list_bridges(self, node: str = "") -> list[dict[str, Any]]: ...

    def get_guest_ipv4(
        self,
        vmid: int,
        *,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
        enable_lookup: bool = True,
        timeout_seconds: float | None = None,
    ) -> str: ...
