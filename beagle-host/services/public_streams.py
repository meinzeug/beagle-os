"""Public stream port-state and allocation helpers.

This service owns the persistent public-stream port mapping file plus the
allocation/synchronization logic used by VM profile synthesis and
ubuntu-beagle provisioning. The control plane keeps thin wrappers so existing
helper signatures stay stable while the non-HTTP state/orchestration block
leaves the entrypoint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class PublicStreamService:
    def __init__(
        self,
        *,
        current_public_stream_host: Callable[[], str],
        data_dir: Callable[[], Path],
        get_vm_config: Callable[[str, int], dict[str, Any]],
        list_vms: Callable[[], list[Any]],
        load_json_file: Callable[[Path, Any], Any],
        parse_description_meta: Callable[[str], dict[str, str]],
        public_stream_base_port: int,
        public_stream_port_count: int,
        public_stream_port_step: int,
        safe_slug: Callable[..., str],
        write_json_file: Callable[..., None],
    ) -> None:
        self._current_public_stream_host = current_public_stream_host
        self._data_dir = data_dir
        self._get_vm_config = get_vm_config
        self._list_vms = list_vms
        self._load_json_file = load_json_file
        self._parse_description_meta = parse_description_meta
        self._public_stream_base_port = int(public_stream_base_port)
        self._public_stream_port_count = int(public_stream_port_count)
        self._public_stream_port_step = int(public_stream_port_step)
        self._safe_slug = safe_slug
        self._write_json_file = write_json_file

    def public_streams_file(self) -> Path:
        return self._data_dir() / "public-streams.json"

    def load_public_streams(self) -> dict[str, int]:
        payload = self._load_json_file(self.public_streams_file(), {})
        if not isinstance(payload, dict):
            return {}
        streams: dict[str, int] = {}
        for key, value in payload.items():
            try:
                streams[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
        return streams

    def save_public_streams(self, payload: dict[str, int]) -> None:
        self._write_json_file(self.public_streams_file(), payload, mode=0o600)

    def public_stream_key(self, node: str, vmid: int) -> str:
        return f"{self._safe_slug(node, 'node')}:{int(vmid)}"

    def explicit_public_stream_base_port(self, config: dict[str, Any] | None) -> int | None:
        vm_config = config if isinstance(config, dict) else {}
        meta = self._parse_description_meta(vm_config.get("description", ""))
        explicit_port = str(meta.get("beagle-public-moonlight-port", "")).strip()
        if explicit_port.isdigit():
            return int(explicit_port)
        return None

    def used_public_stream_base_ports(
        self,
        mappings: dict[str, int],
        *,
        exclude_key: str = "",
        sync_mappings: bool = False,
    ) -> tuple[set[int], bool]:
        used = {int(value) for key, value in mappings.items() if key != exclude_key}
        changed = False
        known_keys: set[str] = set()
        for vm in self._list_vms():
            key = self.public_stream_key(vm.node, vm.vmid)
            known_keys.add(key)
            if key == exclude_key:
                continue
            explicit_port = self.explicit_public_stream_base_port(self._get_vm_config(vm.node, vm.vmid))
            if explicit_port is not None:
                used.add(explicit_port)
                if sync_mappings and mappings.get(key) != explicit_port:
                    mappings[key] = explicit_port
                    changed = True
                    continue
            if key in mappings:
                used.add(int(mappings[key]))
        if sync_mappings:
            stale_keys = [key for key in mappings if key != exclude_key and key not in known_keys]
            for key in stale_keys:
                mappings.pop(key, None)
                changed = True
        return used, changed

    def allocate_public_stream_base_port(self, node: str, vmid: int) -> int | None:
        if not self._current_public_stream_host():
            return None
        mappings = self.load_public_streams()
        key = self.public_stream_key(node, vmid)
        explicit_port = self.explicit_public_stream_base_port(self._get_vm_config(node, vmid))
        changed = False
        if explicit_port is not None and mappings.get(key) != explicit_port:
            mappings[key] = explicit_port
            changed = True
        existing = explicit_port if explicit_port is not None else mappings.get(key)
        if existing is not None:
            _, sync_changed = self.used_public_stream_base_ports(
                mappings,
                exclude_key=key,
                sync_mappings=True,
            )
            if changed or sync_changed:
                self.save_public_streams(mappings)
            return int(existing)
        used, sync_changed = self.used_public_stream_base_ports(
            mappings,
            exclude_key=key,
            sync_mappings=True,
        )
        changed = changed or sync_changed
        upper_bound = self._public_stream_base_port + (
            self._public_stream_port_step * self._public_stream_port_count
        )
        for candidate in range(
            self._public_stream_base_port,
            upper_bound,
            self._public_stream_port_step,
        ):
            if candidate in used:
                continue
            mappings[key] = candidate
            self.save_public_streams(mappings)
            return candidate
        if changed:
            self.save_public_streams(mappings)
        return None
