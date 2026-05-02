from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class StoragePoolPathRegressionTests(unittest.TestCase):
    def test_install_host_services_prefers_beagle_volume_for_libvirt_images(self) -> None:
        script = (ROOT / "scripts" / "install-beagle-host-services.sh").read_text(encoding="utf-8")

        self.assertIn('detect_default_libvirt_images_dir() {', script)
        self.assertIn('local beagle_default="/var/lib/beagle/libvirt/images"', script)
        self.assertIn('BEAGLE_LIBVIRT_IMAGES_DIR="$(resolve_libvirt_images_dir)"', script)
        self.assertIn('sync_local_storage_pool "$BEAGLE_LIBVIRT_IMAGES_DIR"', script)

    def test_provider_uses_configured_libvirt_images_dir_for_local_pool(self) -> None:
        provider = (ROOT / "beagle-host" / "providers" / "beagle_host_provider.py").read_text(encoding="utf-8")

        self.assertIn('configured_images_dir = os.environ.get("BEAGLE_LIBVIRT_IMAGES_DIR", "")', provider)
        self.assertIn("self._libvirt_images_dir = Path(", provider)
        self.assertIn("local_path = self._libvirt_images_dir", provider)
        self.assertIn("return str(self._libvirt_images_dir)", provider)


if __name__ == "__main__":
    unittest.main()
