"""Beagle Endpoint OS Profile Manager.

Handles profile discovery, loading, and configuration for Beagle Endpoint OS.
Each profile specifies packages, systemd services/targets, and hardware capabilities.
"""

from __future__ import annotations

import configparser
import json
from pathlib import Path
from typing import Any


class EndpointProfile:
    """Represents a Beagle Endpoint OS profile configuration."""

    def __init__(self, profile_dir: Path) -> None:
        """Initialize profile from directory containing profile.conf."""
        self.profile_dir = Path(profile_dir)
        self.config = configparser.ConfigParser()

        config_file = self.profile_dir / "profile.conf"
        if not config_file.exists():
            raise FileNotFoundError(f"Profile config not found: {config_file}")

        # Load the config file (it's a simple KEY=VALUE format, so use read_string with section wrapper)
        config_content = config_file.read_text(encoding="utf-8")
        config_string = f"[DEFAULT]\n{config_content}"
        self.config.read_string(config_string)

    def name(self) -> str:
        """Return profile name."""
        return self.config.get("DEFAULT", "PROFILE_NAME", fallback="unknown")

    def description(self) -> str:
        """Return profile description."""
        return self.config.get("DEFAULT", "PROFILE_DESCRIPTION", fallback="")

    def version(self) -> str:
        """Return profile version."""
        return self.config.get("DEFAULT", "PROFILE_VERSION", fallback="1.0")

    def packages(self) -> list[str]:
        """Return list of additional packages for this profile."""
        packages_raw = self.config.get("DEFAULT", "PROFILE_PACKAGES", fallback="")
        return [p.strip() for p in packages_raw.split(",") if p.strip()]

    def systemd_targets(self) -> list[str]:
        """Return list of systemd targets to enable."""
        targets_raw = self.config.get("DEFAULT", "PROFILE_SYSTEMD_TARGETS", fallback="")
        return [t.strip() for t in targets_raw.split(",") if t.strip()]

    def systemd_services(self) -> list[str]:
        """Return list of systemd services to enable."""
        services_raw = self.config.get("DEFAULT", "PROFILE_SYSTEMD_SERVICES", fallback="")
        return [s.strip() for s in services_raw.split(",") if s.strip()]

    def system_slots(self) -> int:
        """Return number of A/B system slots."""
        return self.config.getint("DEFAULT", "PROFILE_SYSTEM_SLOTS", fallback=2)

    def encrypt_disk(self) -> bool:
        """Return whether disk encryption is default."""
        value = self.config.get("DEFAULT", "PROFILE_ENCRYPT_DISK", fallback="true").lower()
        return value in {"true", "1", "yes"}

    def encrypt_method(self) -> str:
        """Return encryption method."""
        return self.config.get("DEFAULT", "PROFILE_ENCRYPT_METHOD", fallback="luks2-tpm2")

    def icon(self) -> str:
        """Return icon name for UI display."""
        return self.config.get("DEFAULT", "PROFILE_ICON", fallback="device")

    def display_order(self) -> int:
        """Return display order priority."""
        return self.config.getint("DEFAULT", "PROFILE_DISPLAY_ORDER", fallback=100)

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary for JSON serialization."""
        return {
            "name": self.name(),
            "description": self.description(),
            "version": self.version(),
            "packages": self.packages(),
            "systemd_targets": self.systemd_targets(),
            "systemd_services": self.systemd_services(),
            "system_slots": self.system_slots(),
            "encrypt_disk": self.encrypt_disk(),
            "encrypt_method": self.encrypt_method(),
            "icon": self.icon(),
            "display_order": self.display_order(),
        }


class ProfileManager:
    """Manages discovery and loading of all available profiles."""

    def __init__(self, profiles_base_dir: Path | str = "beagle-os/profiles") -> None:
        """Initialize profile manager with base directory."""
        self.profiles_base_dir = Path(profiles_base_dir)
        self._profiles: dict[str, EndpointProfile] = {}
        self._discover_profiles()

    def _discover_profiles(self) -> None:
        """Discover all profiles in the base directory."""
        if not self.profiles_base_dir.is_dir():
            return

        for item in self.profiles_base_dir.iterdir():
            if item.is_dir() and (item / "profile.conf").exists():
                try:
                    profile = EndpointProfile(item)
                    name = profile.name()
                    self._profiles[name] = profile
                except Exception as e:
                    print(f"Warning: failed to load profile from {item}: {e}")

    def list_profiles(self) -> list[tuple[str, EndpointProfile]]:
        """Return sorted list of (name, profile) tuples."""
        return sorted(
            self._profiles.items(),
            key=lambda x: x[1].display_order(),
        )

    def get_profile(self, name: str) -> EndpointProfile | None:
        """Get a profile by name."""
        return self._profiles.get(name)

    def profiles_as_json(self) -> str:
        """Return all profiles as JSON."""
        profiles_list = [
            {"name": name, "config": profile.to_dict()}
            for name, profile in self.list_profiles()
        ]
        return json.dumps(profiles_list, indent=2)


def main() -> None:
    """CLI demo of profile manager."""
    manager = ProfileManager()
    profiles = manager.list_profiles()

    if not profiles:
        print("No profiles found.")
        return

    for name, profile in profiles:
        print(f"\n=== Profile: {name} ===")
        print(f"Description: {profile.description()}")
        print(f"Version: {profile.version()}")
        print(f"Packages ({len(profile.packages())}): {', '.join(profile.packages()[:3])}...")
        print(f"Targets: {', '.join(profile.systemd_targets())}")
        print(f"Services: {', '.join(profile.systemd_services()[:2])}...")
        print(f"System slots: {profile.system_slots()}")
        print(f"Encryption: {profile.encrypt_method()}")


if __name__ == "__main__":
    main()
