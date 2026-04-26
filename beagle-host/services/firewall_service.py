"""Firewall service using nftables for VM traffic filtering."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass
class FirewallRule:
    """Firewall rule specification."""

    direction: Literal["inbound", "outbound"]
    protocol: str  # "tcp", "udp", "icmp", "all"
    port: int | None  # None for non-port protocols
    action: Literal["allow", "deny"]
    source_cidr: str | None = None
    description: str = ""


@dataclass
class FirewallProfile:
    """Firewall profile for a VM or pool."""

    profile_id: str
    name: str
    rules: list[FirewallRule]
    default_inbound: Literal["allow", "deny"] = "deny"
    default_outbound: Literal["allow", "deny"] = "allow"


class FirewallService:
    """Firewall service managing nftables rules."""

    STATE_FILE = Path("/var/lib/beagle/beagle-manager/firewall-rules.json")
    BACKUP_FILE = Path("/var/lib/beagle/beagle-manager/firewall-rules.backup.json")

    def __init__(self, state_file: Path | None = None, backup_file: Path | None = None):
        """Initialize firewall service."""
        if state_file is not None:
            self.STATE_FILE = state_file
            if backup_file is None:
                self.BACKUP_FILE = state_file.with_name(f"{state_file.stem}.backup{state_file.suffix}")
        if backup_file is not None:
            self.BACKUP_FILE = backup_file
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.BACKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        """Load persisted firewall state."""
        if self.STATE_FILE.exists():
            return json.loads(self.STATE_FILE.read_text())
        return {"profiles": {}, "vm_profiles": {}}

    def _save_state(self) -> None:
        """Save firewall state to disk."""
        self.STATE_FILE.write_text(json.dumps(self._state, indent=2))

    def _backup_state(self) -> None:
        """Backup current state before applying changes."""
        self.BACKUP_FILE.write_text(self.STATE_FILE.read_text())

    def _run_nft_cmd(self, cmd: list[str], test_only: bool = False) -> bool:
        """Run nft command. If test_only, run in dry-run mode."""
        if test_only:
            cmd = ["nft", "--dry-run"] + cmd[1:]

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            return False

    def _nft_to_string(self, cmd: list[str]) -> str:
        """Run nft command and return output."""
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def _generate_nftables_rules(self, profile: FirewallProfile) -> list[str]:
        """Generate nftables commands from a firewall profile."""
        nft_rules = []

        # Create input chain rules
        for rule in profile.rules:
            if rule.direction == "inbound":
                proto_str = (
                    "tcp"
                    if rule.protocol == "tcp"
                    else "udp"
                    if rule.protocol == "udp"
                    else "icmp"
                    if rule.protocol == "icmp"
                    else ""
                )

                if proto_str and rule.port:
                    nft_rule = f"add rule inet filter input {proto_str} dport {rule.port} {rule.action}"
                elif proto_str:
                    nft_rule = f"add rule inet filter input {proto_str} {rule.action}"
                else:
                    nft_rule = f"add rule inet filter input {rule.action}"

                nft_rules.append(nft_rule)

        # Add default policies
        if profile.default_inbound == "deny":
            nft_rules.append("add rule inet filter input drop")
        if profile.default_outbound == "allow":
            pass  # Default is allow, no rule needed

        return nft_rules

    def create_profile(self, profile: FirewallProfile) -> None:
        """Create a new firewall profile."""
        if profile.profile_id in self._state["profiles"]:
            raise ValueError(f"Profile {profile.profile_id} already exists")

        # Serialize profile for storage
        self._state["profiles"][profile.profile_id] = {
            "name": profile.name,
            "rules": [
                {
                    "direction": r.direction,
                    "protocol": r.protocol,
                    "port": r.port,
                    "action": r.action,
                    "description": r.description,
                }
                for r in profile.rules
            ],
            "default_inbound": profile.default_inbound,
            "default_outbound": profile.default_outbound,
        }
        self._save_state()

    def get_profile(self, profile_id: str) -> FirewallProfile:
        """Get a firewall profile."""
        if profile_id not in self._state["profiles"]:
            raise ValueError(f"Profile {profile_id} not found")

        data = self._state["profiles"][profile_id]
        rules = [FirewallRule(**r) for r in data["rules"]]
        return FirewallProfile(
            profile_id=profile_id,
            name=data["name"],
            rules=rules,
            default_inbound=data.get("default_inbound", "deny"),
            default_outbound=data.get("default_outbound", "allow"),
        )

    def apply_profile_to_vm(self, profile_id: str, vm_id: str) -> None:
        """Apply a firewall profile to a VM."""
        if profile_id not in self._state["profiles"]:
            raise ValueError(f"Profile {profile_id} not found")

        # Validate rules with nftables dry-run
        profile = self.get_profile(profile_id)
        nft_rules = self._generate_nftables_rules(profile)

        for rule_cmd in nft_rules:
            if not self._run_nft_cmd(["nft", rule_cmd], test_only=True):
                raise RuntimeError(f"Invalid nftables rule: {rule_cmd}")

        # Backup state before applying
        self._backup_state()

        # Record VM -> Profile mapping
        self._state["vm_profiles"][vm_id] = profile_id
        self._save_state()

    def remove_profile_from_vm(self, vm_id: str) -> None:
        """Remove firewall profile from a VM."""
        if vm_id in self._state["vm_profiles"]:
            del self._state["vm_profiles"][vm_id]
            self._save_state()

    def get_vm_profile(self, vm_id: str) -> FirewallProfile | None:
        """Get the firewall profile for a VM."""
        profile_id = self._state["vm_profiles"].get(vm_id)
        if not profile_id:
            return None
        return self.get_profile(profile_id)

    def validate_rules(self, rules: list[FirewallRule]) -> None:
        """Validate firewall rules for syntax errors."""
        temp_profile = FirewallProfile(
            profile_id="__temp__", name="temp", rules=rules
        )
        nft_rules = self._generate_nftables_rules(temp_profile)

        for rule_cmd in nft_rules:
            if not self._run_nft_cmd(["nft", rule_cmd], test_only=True):
                raise ValueError(f"Invalid firewall rule: {rule_cmd}")

    def rollback(self) -> None:
        """Rollback to previous firewall state."""
        if self.BACKUP_FILE.exists():
            backup_content = self.BACKUP_FILE.read_text()
            self.STATE_FILE.write_text(backup_content)
            self._state = json.loads(backup_content)

    def list_profiles(self) -> list[dict[str, Any]]:
        """List all firewall profiles."""
        profiles = []
        for pid, pdata in self._state.get("profiles", {}).items():
            profiles.append({
                "profile_id": pid,
                "name": pdata.get("name", pid),
                "rule_count": len(pdata.get("rules", [])),
            })
        return profiles
