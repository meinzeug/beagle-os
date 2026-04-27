import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.virtualization.desktop_template import DesktopTemplateBuildSpec, DesktopTemplateInfo


class DesktopTemplateContractTests(unittest.TestCase):
    def test_build_spec_fields(self) -> None:
        spec = DesktopTemplateBuildSpec(
            template_id="tmpl-ubuntu-xfce-01",
            source_vmid=150,
            template_name="Ubuntu XFCE Gold",
            os_family="ubuntu",
            storage_pool="local",
            snapshot_name="sealed-2026-04-22",
            backing_image="local/templates/ubuntu-xfce-gold.qcow2",
            cpu_cores=4,
            memory_mib=8192,
            software_packages=("sunshine", "qemu-guest-agent"),
        )
        self.assertEqual(spec.template_id, "tmpl-ubuntu-xfce-01")
        self.assertEqual(spec.source_vmid, 150)
        self.assertEqual(spec.storage_pool, "local")
        self.assertEqual(spec.cpu_cores, 4)
        self.assertEqual(spec.memory_mib, 8192)
        self.assertEqual(spec.software_packages, ("sunshine", "qemu-guest-agent"))
        self.assertEqual(spec.notes, "")

    def test_template_info_fields(self) -> None:
        info = DesktopTemplateInfo(
            template_id="tmpl-ubuntu-xfce-01",
            template_name="Ubuntu XFCE Gold",
            source_vmid=150,
            os_family="ubuntu",
            storage_pool="local",
            snapshot_name="sealed-2026-04-22",
            backing_image="local/templates/ubuntu-xfce-gold.qcow2",
            cpu_cores=4,
            memory_mib=8192,
            software_packages=("sunshine",),
            created_at="2026-04-22T08:00:00Z",
            sealed=True,
        )
        self.assertEqual(info.template_id, "tmpl-ubuntu-xfce-01")
        self.assertEqual(info.template_name, "Ubuntu XFCE Gold")
        self.assertEqual(info.source_vmid, 150)
        self.assertEqual(info.os_family, "ubuntu")
        self.assertEqual(info.storage_pool, "local")
        self.assertEqual(info.snapshot_name, "sealed-2026-04-22")
        self.assertEqual(info.backing_image, "local/templates/ubuntu-xfce-gold.qcow2")
        self.assertEqual(info.cpu_cores, 4)
        self.assertEqual(info.memory_mib, 8192)
        self.assertEqual(info.software_packages, ("sunshine",))
        self.assertEqual(info.created_at, "2026-04-22T08:00:00Z")
        self.assertTrue(info.sealed)
        self.assertEqual(info.health, "unknown")


if __name__ == "__main__":
    unittest.main()
