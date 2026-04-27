"""Seed Config Parser — Zero-Touch Installer-Konfiguration (YAML-Format).

GoEnterprise Plan 08, Schritt 2
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class NetworkConfig:
    interface: str = "eth0"
    mode: str = "dhcp"      # "dhcp" | "static"
    ip: str = ""            # CIDR, e.g. "192.168.1.10/24"
    gateway: str = ""
    dns: list[str] = field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])


@dataclass
class ClusterConfig:
    join: str = ""          # IP of existing cluster controller; empty = new cluster
    token: str = ""         # enrollment token (one-time, 24h)


@dataclass
class SeedConfig:
    hostname: str
    disk: str               # e.g. "/dev/sda"
    raid: int               # 0, 1, 5, 10 (0 = no RAID / single disk)
    network: NetworkConfig
    cluster: ClusterConfig
    admin_username: str = "beagle"
    admin_password: str = ""
    locale: str = "en_US.UTF-8"
    timezone: str = "UTC"
    admin_password_hash: str = ""   # bcrypt hash; empty = random generated at install
    # Raw config for forward-compatibility
    extra: dict[str, Any] = field(default_factory=dict)


class SeedConfigParser:
    """
    Parses and validates Beagle Installer Seed Config (YAML subset).

    We use a minimal YAML parser (no external dependencies) that supports:
    - Key: value (string, int, bool)
    - Nested sections (2-space indent)
    - Lists (- item)
    """

    VALID_RAID_LEVELS = {0, 1, 5, 10}
    DISK_PATTERN = re.compile(r"^/dev/[a-zA-Z0-9]+$")
    CIDR_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$")
    HOSTNAME_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")

    def parse_file(self, path: Path) -> SeedConfig:
        content = path.read_text(encoding="utf-8")
        return self.parse(content)

    def parse(self, yaml_text: str) -> SeedConfig:
        """Parse minimal YAML seed config and return SeedConfig."""
        d = self._parse_yaml(yaml_text)
        return self._build(d)

    def validate(self, config: SeedConfig) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        errors = []

        if not self.HOSTNAME_PATTERN.match(config.hostname):
            errors.append(f"hostname invalid: {config.hostname!r}")

        if not self.DISK_PATTERN.match(config.disk):
            errors.append(f"disk must be a /dev/... path, got: {config.disk!r}")

        if config.raid not in self.VALID_RAID_LEVELS:
            errors.append(f"raid must be one of {self.VALID_RAID_LEVELS}, got: {config.raid}")

        admin_username = str(config.admin_username or "").strip()
        if not re.fullmatch(r"^[a-z_][a-z0-9_-]{0,31}$", admin_username):
            errors.append(f"admin_username invalid: {config.admin_username!r}")

        if not str(config.admin_password or "").strip() and not str(config.admin_password_hash or "").strip():
            errors.append("admin_password or admin_password_hash is required")

        net = config.network
        if net.mode not in ("dhcp", "static"):
            errors.append(f"network.mode must be 'dhcp' or 'static', got: {net.mode!r}")
        if net.mode == "static":
            if not self.CIDR_PATTERN.match(net.ip):
                errors.append(f"network.ip must be CIDR notation (e.g. 192.168.1.1/24), got: {net.ip!r}")
            if not net.gateway:
                errors.append("network.gateway required for static mode")

        return errors

    # ------------------------------------------------------------------
    # Minimal YAML parser (supports the subset used in seed configs)
    # ------------------------------------------------------------------

    def _parse_yaml(self, text: str) -> dict[str, Any]:
        """
        Parse indented key:value YAML into a nested dict.
        Supports: strings, ints, bools, nested dicts (2-space indent), simple lists.
        """
        result: dict[str, Any] = {}
        # Each frame: (indent_level, dict_at_this_level)
        # When we process a key with no value, we create a child dict and push it.
        # When we see a list item (- ), we assign to the LAST KEY in the parent.
        stack: list[tuple[int, dict[str, Any]]] = [(0, result)]
        # Track the last key set at each stack level for list attachment
        last_keys: list[str] = [""]

        for raw in self._iter_lines(text):
            indent = len(raw) - len(raw.lstrip())
            stripped = raw.strip()

            if stripped.startswith("- "):
                # List item: find the parent that has the last key pointing to this child
                val = self._coerce(stripped[2:].strip())
                # Walk up the stack to find a level whose last_key is set
                for lvl in range(len(stack) - 1, -1, -1):
                    k = last_keys[lvl]
                    if k:
                        top_dict = stack[lvl][1]
                        existing = top_dict.get(k)
                        if isinstance(existing, list):
                            existing.append(val)
                        else:
                            # Replace the nested dict placeholder with a list
                            top_dict[k] = [val]
                        break
                continue

            if ":" not in stripped:
                continue

            key, _, raw_val = stripped.partition(":")
            key = key.strip()
            raw_val = raw_val.strip()

            # Pop stack to the level where this key belongs (indent level)
            while len(stack) > 1 and stack[-1][0] > indent:
                stack.pop()
                last_keys.pop()

            current = stack[-1][1]

            if raw_val:
                current[key] = self._coerce(raw_val)
                last_keys[-1] = key
            else:
                # Nested section or upcoming list
                # Peek ahead: if next data line is a list item, init as []
                # We can't easily peek, so init as {} and convert on first list item
                # Actually: just init as {} but list items will convert it
                nested: dict[str, Any] = {}
                current[key] = nested
                last_keys[-1] = key
                stack.append((indent + 2, nested))
                last_keys.append("")

        return result

    def _iter_lines(self, text: str):
        for line in text.splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            yield line

    @staticmethod
    def _coerce(val: str) -> Any:
        """Convert string to int/bool/str."""
        if val.lower() == "true":
            return True
        if val.lower() == "false":
            return False
        try:
            return int(val)
        except ValueError:
            pass
        # Strip surrounding quotes
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            return val[1:-1]
        return val

    def _build(self, d: dict[str, Any]) -> SeedConfig:
        net_d = d.get("network", {})
        net = NetworkConfig(
            interface=str(net_d.get("interface", "eth0")),
            mode=str(net_d.get("mode", "dhcp")),
            ip=str(net_d.get("ip", "")),
            gateway=str(net_d.get("gateway", "")),
            dns=net_d.get("dns", ["1.1.1.1"]) if isinstance(net_d.get("dns"), list)
                else [str(net_d.get("dns", "1.1.1.1"))],
        )
        cluster_d = d.get("cluster", {})
        cluster = ClusterConfig(
            join=str(cluster_d.get("join", "")),
            token=str(cluster_d.get("token", "")),
        )
        extra = {k: v for k, v in d.items() if k not in (
            "hostname", "disk", "raid", "network", "cluster",
            "locale", "timezone", "admin_username", "admin_password", "admin_password_hash",
        )}
        return SeedConfig(
            hostname=str(d.get("hostname", "")),
            disk=str(d.get("disk", "")),
            raid=int(d.get("raid", 1)),
            network=net,
            cluster=cluster,
            admin_username=str(d.get("admin_username", "beagle")),
            admin_password=str(d.get("admin_password", "")),
            locale=str(d.get("locale", "en_US.UTF-8")),
            timezone=str(d.get("timezone", "UTC")),
            admin_password_hash=str(d.get("admin_password_hash", "")),
            extra=extra,
        )
