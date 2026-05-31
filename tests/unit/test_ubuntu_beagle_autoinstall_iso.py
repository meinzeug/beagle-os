from __future__ import annotations

import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from ubuntu_beagle_provisioning import UbuntuBeagleProvisioningService


class UbuntuBeagleAutoinstallIsoTests(unittest.TestCase):
    def test_autoinstall_boot_iso_filename_is_versioned_from_base_iso(self) -> None:
        service = UbuntuBeagleProvisioningService.__new__(UbuntuBeagleProvisioningService)

        filename = service.ubuntu_beagle_autoinstall_boot_iso_filename("ubuntu-24.04.4-live-server-amd64.iso")

        self.assertEqual(filename, "ubuntu-24.04.4-live-server-amd64-beagle-autoinstall.iso")

    def test_patch_autoinstall_grub_cfg_adds_kernel_flag_to_default_entries(self) -> None:
        original = (
            'menuentry "Try or Install Ubuntu Server" {\n'
            '\tlinux\t/casper/vmlinuz  ---\n'
            '\tinitrd\t/casper/initrd\n'
            '}\n'
            'menuentry "Ubuntu Server with the HWE kernel" {\n'
            '\tlinux\t/casper/hwe-vmlinuz  ---\n'
            '\tinitrd\t/casper/hwe-initrd\n'
            '}\n'
        )

        patched = UbuntuBeagleProvisioningService.patch_autoinstall_grub_cfg(original)

        self.assertIn("\tlinux\t/casper/vmlinuz autoinstall ---", patched)
        self.assertIn("\tlinux\t/casper/hwe-vmlinuz autoinstall ---", patched)
        self.assertNotIn("\tlinux\t/casper/vmlinuz  ---", patched)

    def test_create_ubuntu_beagle_boot_iso_replays_boot_image_and_maps_grub_cfg(self) -> None:
        service = UbuntuBeagleProvisioningService.__new__(UbuntuBeagleProvisioningService)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local_iso_dir = root / "iso"
            local_iso_dir.mkdir()
            base_iso = local_iso_dir / "ubuntu.iso"
            base_iso.write_bytes(b"iso")
            copied_grub = root / "copied-grub.cfg"
            copied_grub.write_text(
                'menuentry "Try or Install Ubuntu Server" {\n'
                '\tlinux\t/casper/vmlinuz  ---\n'
                '}\n',
                encoding="utf-8",
            )
            commands: list[list[str]] = []

            def fake_run_checked(command, timeout=None):
                del timeout
                commands.append(list(command))
                if command[:6] == ["xorriso", "-osirrox", "on", "-indev", str(base_iso), "-extract"]:
                    Path(command[-1]).write_text(copied_grub.read_text(encoding="utf-8"), encoding="utf-8")
                return ""

            service._run_checked = fake_run_checked
            service.local_iso_storage_dir = lambda: local_iso_dir

            result = service.ensure_ubuntu_beagle_autoinstall_boot_iso(base_iso, "ubuntu.iso")

            self.assertEqual(result["boot_iso_filename"], "ubuntu-beagle-autoinstall.iso")
            self.assertEqual(Path(result["boot_iso_path"]).name, "ubuntu-beagle-autoinstall.iso")
            self.assertTrue(any(cmd[:5] == ["xorriso", "-dev", str(local_iso_dir / "ubuntu-beagle-autoinstall.iso.part"), "-boot_image", "any"] for cmd in commands))
            remaster_cmd = next(cmd for cmd in commands if cmd[:2] == ["xorriso", "-dev"])
            self.assertIn("replay", remaster_cmd)
            self.assertIn("/boot/grub/grub.cfg", remaster_cmd)
            self.assertTrue((local_iso_dir / "ubuntu-beagle-autoinstall.iso").exists())

    def test_local_iso_storage_dir_falls_back_to_libvirt_images_dir_when_legacy_path_is_unwritable(self) -> None:
        service = UbuntuBeagleProvisioningService.__new__(UbuntuBeagleProvisioningService)
        with tempfile.TemporaryDirectory() as temp_dir:
            fallback = Path(temp_dir) / "libvirt-images"
            legacy = Path("/var/lib/vz/template/iso")
            service._local_iso_dir = legacy
            original_mkdir = Path.mkdir

            def fake_mkdir(path_obj, parents=False, exist_ok=False):
                if path_obj == legacy:
                    raise PermissionError("legacy proxmox iso path is not writable")
                return original_mkdir(path_obj, parents=parents, exist_ok=exist_ok)

            with mock.patch.dict("os.environ", {"BEAGLE_LIBVIRT_IMAGES_DIR": str(fallback)}):
                with mock.patch.object(Path, "mkdir", autospec=True, side_effect=fake_mkdir):
                    resolved = service.local_iso_storage_dir()

            self.assertEqual(resolved, fallback)
            self.assertEqual(service._local_iso_dir, fallback)
            self.assertTrue(fallback.is_dir())


if __name__ == "__main__":
    unittest.main()
