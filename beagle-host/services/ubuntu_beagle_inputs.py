"""Ubuntu-Beagle input validation and preset helpers.

This service owns canonical ubuntu-beagle input validation plus desktop and
package preset normalization. The control plane keeps thin wrappers so helper
signatures stay stable while provisioning-facing input semantics leave the
entrypoint.
"""

from __future__ import annotations

import re
from typing import Any


class UbuntuBeagleInputsService:
    def __init__(
        self,
        *,
        ubuntu_beagle_default_desktop: str,
        ubuntu_beagle_default_keymap: str,
        ubuntu_beagle_default_locale: str,
        ubuntu_beagle_desktops: dict[str, dict[str, Any]],
        ubuntu_beagle_min_password_length: int,
        ubuntu_beagle_software_presets: dict[str, dict[str, Any]],
    ) -> None:
        self._ubuntu_beagle_default_desktop = str(ubuntu_beagle_default_desktop or "")
        self._ubuntu_beagle_default_keymap = str(ubuntu_beagle_default_keymap or "")
        self._ubuntu_beagle_default_locale = str(ubuntu_beagle_default_locale or "")
        self._ubuntu_beagle_desktops = dict(ubuntu_beagle_desktops or {})
        self._ubuntu_beagle_min_password_length = int(ubuntu_beagle_min_password_length)
        self._ubuntu_beagle_software_presets = dict(ubuntu_beagle_software_presets or {})

    def validate_linux_username(self, value: str, field_name: str) -> str:
        candidate = str(value or "").strip().lower()
        if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", candidate):
            raise ValueError(f"invalid {field_name}")
        return candidate

    def validate_password(self, value: str, field_name: str, *, allow_empty: bool = False) -> str:
        candidate = str(value or "")
        if not candidate and allow_empty:
            return ""
        if len(candidate) < self._ubuntu_beagle_min_password_length:
            raise ValueError(
                f"{field_name} must be at least {self._ubuntu_beagle_min_password_length} characters"
            )
        return candidate

    def normalize_locale(self, value: str) -> str:
        candidate = str(value or "").strip() or self._ubuntu_beagle_default_locale
        if not re.fullmatch(r"[A-Za-z0-9_.@-]+", candidate):
            raise ValueError("invalid identity_locale")
        return candidate

    def normalize_keymap(self, value: str) -> str:
        candidate = str(value or "").strip().lower() or self._ubuntu_beagle_default_keymap
        if not re.fullmatch(r"[A-Za-z0-9_-]+", candidate):
            raise ValueError("invalid identity_keymap")
        return candidate

    def normalize_package_names(self, value: Any, *, field_name: str) -> list[str]:
        if isinstance(value, list):
            raw_items = value
        else:
            raw_items = re.split(r"[\s,]+", str(value or ""))
        names: list[str] = []
        seen: set[str] = set()
        for raw_item in raw_items:
            item = str(raw_item or "").strip().lower()
            if not item:
                continue
            if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", item):
                raise ValueError(f"invalid {field_name}: {item}")
            if item in seen:
                continue
            seen.add(item)
            names.append(item)
        return names

    def resolve_ubuntu_beagle_desktop(self, value: str) -> dict[str, Any]:
        candidate = str(value or "").strip().lower()
        if not candidate:
            candidate = self._ubuntu_beagle_default_desktop
        if candidate in self._ubuntu_beagle_desktops:
            return self._ubuntu_beagle_desktops[candidate]
        for desktop in self._ubuntu_beagle_desktops.values():
            aliases = [str(item).strip().lower() for item in desktop.get("aliases", []) if str(item).strip()]
            if candidate == str(desktop.get("label", "")).strip().lower() or candidate in aliases:
                return desktop
        raise ValueError(f"unsupported desktop: {candidate}")

    def normalize_package_presets(self, value: Any) -> list[str]:
        presets = self.normalize_package_names(value, field_name="package_presets")
        supported = set(self._ubuntu_beagle_software_presets.keys())
        unknown = [item for item in presets if item not in supported]
        if unknown:
            raise ValueError(f"unsupported package presets: {', '.join(unknown)}")
        return presets

    def expand_software_packages(self, package_presets: list[str], extra_packages: list[str]) -> list[str]:
        packages: list[str] = []
        seen: set[str] = set()
        for preset_id in package_presets:
            preset = self._ubuntu_beagle_software_presets.get(preset_id, {})
            for package_name in preset.get("packages", []) if isinstance(preset, dict) else []:
                candidate = str(package_name or "").strip().lower()
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    packages.append(candidate)
        for package_name in extra_packages:
            candidate = str(package_name or "").strip().lower()
            if candidate and candidate not in seen:
                seen.add(candidate)
                packages.append(candidate)
        return packages
