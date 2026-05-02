from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from ubuntu_beagle_inputs import UbuntuBeagleInputsService
from ubuntu_beagle_provisioning import UbuntuBeagleProvisioningService


DESKTOPS = {
    "plasma-cyberpunk": {
        "id": "plasma-cyberpunk",
        "label": "Beagle OS Cyberpunk",
        "session": "plasma",
        "packages": ["plasma-desktop"],
        "features": ["Dark neon profile"],
        "aliases": ["cyberpunk"],
        "visible_in_ui": True,
        "theme_variant": "cyberpunk",
        "wallpaper_required": True,
    },
    "plasma-classic": {
        "id": "plasma-classic",
        "label": "KDE Plasma Classic",
        "session": "plasma",
        "packages": ["plasma-desktop"],
        "features": ["Classic Breeze defaults"],
        "aliases": ["plasma", "kde", "classic"],
        "visible_in_ui": True,
        "theme_variant": "classic",
        "wallpaper_required": False,
    },
    "xfce": {
        "id": "xfce",
        "label": "XFCE",
        "session": "xfce",
        "packages": ["xfce4"],
        "features": ["Legacy lightweight desktop"],
        "aliases": ["xfce"],
        "visible_in_ui": False,
    },
}


def build_inputs() -> UbuntuBeagleInputsService:
    return UbuntuBeagleInputsService(
        ubuntu_beagle_default_desktop="plasma-cyberpunk",
        ubuntu_beagle_default_keymap="de",
        ubuntu_beagle_default_locale="de_DE.UTF-8",
        ubuntu_beagle_desktops=DESKTOPS,
        ubuntu_beagle_min_password_length=8,
        ubuntu_beagle_software_presets={},
    )


def build_service() -> UbuntuBeagleProvisioningService:
    inputs = build_inputs()
    service = UbuntuBeagleProvisioningService.__new__(UbuntuBeagleProvisioningService)
    service._ubuntu_beagle_default_package_presets = []
    service._ubuntu_beagle_default_desktop = "plasma-cyberpunk"
    service._ubuntu_beagle_desktops = DESKTOPS
    service._ubuntu_beagle_profile_id = "ubuntu-24.04-desktop-beagle-stream-server"
    service._ubuntu_beagle_profile_legacy_ids = {}
    service._ubuntu_beagle_default_locale = "de_DE.UTF-8"
    service._ubuntu_beagle_default_keymap = "de"
    service._ubuntu_beagle_cyberpunk_wallpaper_source = Path("/nonexistent/wallpaper.png")
    service._resolve_ubuntu_beagle_desktop = inputs.resolve_ubuntu_beagle_desktop
    service._normalize_locale = inputs.normalize_locale
    service._normalize_keymap = inputs.normalize_keymap
    service._normalize_package_presets = inputs.normalize_package_presets
    service._normalize_package_names = inputs.normalize_package_names
    service._safe_slug = lambda value, _fallback: str(value)
    service.create_ubuntu_beagle_vm = lambda payload: payload
    return service


class UbuntuBeagleDesktopProfilesTests(unittest.TestCase):
    def test_default_provisioning_profile_is_cyberpunk(self) -> None:
        service = build_service()

        payload = service.create_provisioned_vm({})

        self.assertEqual(payload["desktop"], "plasma-cyberpunk")

    def test_valid_classic_profile_is_accepted(self) -> None:
        service = build_service()

        payload = service.create_provisioned_vm({"desktop": "plasma-classic"})

        self.assertEqual(payload["desktop"], "plasma-classic")

    def test_invalid_profile_is_rejected(self) -> None:
        service = build_service()

        with self.assertRaisesRegex(ValueError, "unsupported desktop"):
            service.create_provisioned_vm({"desktop": "totally-wrong"})

    def test_provisioning_desktop_profiles_only_expose_kde_variants(self) -> None:
        service = build_service()

        profiles = service.provisioning_desktop_profiles()

        self.assertEqual([item["id"] for item in profiles], ["plasma-cyberpunk", "plasma-classic"])
        self.assertEqual([item["label"] for item in profiles], ["Beagle OS Cyberpunk", "KDE Plasma Classic"])

    def test_cyberpunk_wallpaper_requires_repo_asset(self) -> None:
        service = build_service()

        with self.assertRaisesRegex(FileNotFoundError, "requires wallpaper file"):
            service.resolve_desktop_wallpaper_asset("plasma-cyberpunk")

    def test_cyberpunk_wallpaper_uses_versioned_asset_when_present(self) -> None:
        service = build_service()
        with tempfile.TemporaryDirectory() as temp_dir:
            wallpaper = Path(temp_dir) / "beagle-cyberpunk-wallpaper.png"
            wallpaper.write_bytes(b"png")
            service._ubuntu_beagle_cyberpunk_wallpaper_source = wallpaper

            asset = service.resolve_desktop_wallpaper_asset("plasma-cyberpunk")

        self.assertEqual(asset["filename"], "beagle-cyberpunk-wallpaper.png")
        self.assertEqual(asset["source"], str(wallpaper))

    def test_classic_profile_does_not_require_wallpaper(self) -> None:
        service = build_service()

        asset = service.resolve_desktop_wallpaper_asset("plasma-classic")

        self.assertEqual(asset, {})


if __name__ == "__main__":
    unittest.main()
