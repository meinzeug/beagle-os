from __future__ import annotations

from typing import Any, Callable


class MigrationService:
    def __init__(
        self,
        *,
        build_migration_uri: Callable[[str, str, int], str],
        find_vm: Callable[[int], Any | None],
        invalidate_vm_cache: Callable[[int | None, str], None],
        libvirt_domain_exists: Callable[[int], bool],
        libvirt_domain_name: Callable[[int], str],
        libvirt_enabled: Callable[[], bool],
        list_nodes: Callable[[], list[dict[str, Any]]],
        persist_vm_node: Callable[[int, str, str], None],
        run_virsh_command: Callable[[list[str]], str],
        service_name: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._build_migration_uri = build_migration_uri
        self._find_vm = find_vm
        self._invalidate_vm_cache = invalidate_vm_cache
        self._libvirt_domain_exists = libvirt_domain_exists
        self._libvirt_domain_name = libvirt_domain_name
        self._libvirt_enabled = libvirt_enabled
        self._list_nodes = list_nodes
        self._persist_vm_node = persist_vm_node
        self._run_virsh_command = run_virsh_command
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")

    def _envelope(self, **payload: Any) -> dict[str, Any]:
        return {
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            **payload,
        }

    @staticmethod
    def _normalize_node(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": str(item.get("name") or item.get("node") or "").strip(),
            "status": str(item.get("status") or "unknown").strip().lower() or "unknown",
        }

    @staticmethod
    def _supports_incremental_storage_copy_error(message: str) -> bool:
        text = str(message or "").lower()
        return (
            "unknown option" in text
            or "unsupported" in text
            or "copy-storage-inc" in text and "invalid" in text
        )

    def list_target_nodes(self, vmid: int) -> list[dict[str, Any]]:
        vm = self._find_vm(int(vmid))
        if vm is None:
            raise RuntimeError(f"VM {int(vmid)} not found")
        source_node = str(getattr(vm, "node", "") or "").strip()
        targets = []
        for item in self._list_nodes():
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_node(item)
            if not normalized["name"] or normalized["name"] == source_node:
                continue
            if normalized["status"] != "online":
                continue
            targets.append(normalized)
        return sorted(targets, key=lambda item: item["name"])

    def migrate_vm(
        self,
        vmid: int,
        *,
        target_node: str,
        live: bool = True,
        copy_storage: bool = False,
        requester_identity: str = "",
    ) -> dict[str, Any]:
        vm = self._find_vm(int(vmid))
        if vm is None:
            raise RuntimeError(f"VM {int(vmid)} not found")
        if not self._libvirt_enabled():
            raise RuntimeError("libvirt migration is not available on this host")
        if not self._libvirt_domain_exists(int(vmid)):
            raise RuntimeError(f"libvirt domain for VM {int(vmid)} does not exist")

        source_node = str(getattr(vm, "node", "") or "").strip()
        if not source_node:
            raise RuntimeError(f"VM {int(vmid)} has no source node")

        normalized_target = str(target_node or "").strip()
        if not normalized_target:
            raise RuntimeError("target_node is required")
        if normalized_target == source_node:
            raise RuntimeError("target_node must differ from source node")

        target_names = {item["name"] for item in self.list_target_nodes(int(vmid))}
        if normalized_target not in target_names:
            raise RuntimeError(f"target node {normalized_target} is not an online migration target")

        status = str(getattr(vm, "status", "") or "").strip().lower()
        if live and status != "running":
            raise RuntimeError("live migration requires a running VM")

        domain_name = self._libvirt_domain_name(int(vmid))
        destination_uri = self._build_migration_uri(source_node, normalized_target, int(vmid))
        command = ["migrate", "--persistent", "--undefinesource", "--verbose"]
        if live:
            command.append("--live")
        storage_copy_mode = "none"
        if copy_storage:
            # Prefer incremental storage-copy so sparse qcow2 images do not force
            # full preallocation on the destination host.
            incremental_command = list(command)
            incremental_command.append("--copy-storage-inc")
            incremental_command.extend([domain_name, destination_uri])
            try:
                provider_result = self._run_virsh_command(incremental_command)
                storage_copy_mode = "incremental"
            except RuntimeError as exc:
                if not self._supports_incremental_storage_copy_error(str(exc)):
                    raise
                fallback_command = list(command)
                fallback_command.append("--copy-storage-all")
                fallback_command.extend([domain_name, destination_uri])
                provider_result = self._run_virsh_command(fallback_command)
                storage_copy_mode = "all"
        else:
            command.extend([domain_name, destination_uri])
            provider_result = self._run_virsh_command(command)
        self._persist_vm_node(int(vmid), source_node, normalized_target)
        self._invalidate_vm_cache(int(vmid), source_node)
        self._invalidate_vm_cache(int(vmid), normalized_target)

        return self._envelope(
            migration={
                "vmid": int(vmid),
                "source_node": source_node,
                "target_node": normalized_target,
                "live": bool(live),
                "copy_storage": bool(copy_storage),
                "copy_storage_mode": storage_copy_mode,
                "domain_name": domain_name,
                "destination_uri": destination_uri,
                "requested_by": str(requester_identity or ""),
                "provider_result": str(provider_result or ""),
            }
        )