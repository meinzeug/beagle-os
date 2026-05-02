import tempfile
import unittest

import sys
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from core.virtualization.desktop_template import DesktopTemplateBuildSpec
from desktop_template_builder import DesktopTemplateBuilderService


class DesktopTemplateBuilderServiceTests(unittest.TestCase):
    def _build_service(self, temp_dir: str) -> DesktopTemplateBuilderService:
        return DesktopTemplateBuilderService(
            state_file=Path(temp_dir) / "desktop-templates.json",
            template_images_dir=Path(temp_dir) / "template-images",
            vm_disk_path_fn=lambda vmid: str(Path(temp_dir) / f"{vmid}.qcow2"),
            stop_vm_fn=lambda vmid: None,
            utcnow=lambda: "2026-04-22T12:00:00Z",
        )

    @patch("desktop_template_builder.subprocess.run")
    @patch("desktop_template_builder.shutil.which", create=True)
    def test_build_template_persists_metadata(self, which_mock, run_mock) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self._build_service(temp_dir)
            which_mock.side_effect = lambda cmd: "/usr/bin/virt-sysprep" if cmd == "virt-sysprep" else "/usr/bin/qemu-img"
            source_disk = Path(temp_dir) / "100.qcow2"
            source_disk.write_text("fake", encoding="utf-8")

            info = service.build_template(
                DesktopTemplateBuildSpec(
                    template_id="tpl-1",
                    source_vmid=100,
                    template_name="Ubuntu XFCE Golden",
                    os_family="linux",
                    storage_pool="local",
                    snapshot_name="sealed",
                    backing_image="",
                    cpu_cores=2,
                    memory_mib=4096,
                    software_packages=("xfce4", "beagle-stream-server"),
                )
            )
            self.assertEqual(info.template_id, "tpl-1")
            self.assertTrue(info.sealed)
            self.assertEqual(info.source_vmid, 100)
            self.assertEqual(info.health, "ready")
            self.assertEqual(info.backing_image, str(Path(temp_dir) / "template-images" / "tpl-1.qcow2"))
            self.assertGreaterEqual(run_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
