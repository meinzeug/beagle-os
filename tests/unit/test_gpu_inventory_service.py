import tempfile
import unittest
from pathlib import Path

import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from gpu_inventory import GpuInventoryService


class GpuInventoryServiceTests(unittest.TestCase):
    def _mk_service(self, lspci_text: str, base: Path) -> GpuInventoryService:
        return GpuInventoryService(
            run_text=lambda _cmd: lspci_text,
            sys_bus_pci_root=base / "sys" / "bus" / "pci" / "devices",
            sys_iommu_root=base / "sys" / "kernel" / "iommu_groups",
            hostname_provider=lambda: "node-a",
        )

    def test_list_gpus_parses_gpu_lines_and_iommu_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            devices = root / "sys" / "bus" / "pci" / "devices"
            iommu = root / "sys" / "kernel" / "iommu_groups"
            devices.mkdir(parents=True)
            iommu.mkdir(parents=True)

            # GPU 1 has isolated group, driver vfio-pci.
            gpu1 = devices / "0000:01:00.0"
            gpu1.mkdir(parents=True)
            (iommu / "7" / "devices").mkdir(parents=True)
            (iommu / "7" / "devices" / "0000:01:00.0").mkdir(parents=True)
            (gpu1 / "iommu_group").symlink_to(iommu / "7")
            (gpu1 / "driver").symlink_to(root / "drivers" / "vfio-pci")

            # GPU 2 has shared group, not isolatable.
            gpu2 = devices / "0000:02:00.0"
            gpu2.mkdir(parents=True)
            (iommu / "8" / "devices").mkdir(parents=True)
            (iommu / "8" / "devices" / "0000:02:00.0").mkdir(parents=True)
            (iommu / "8" / "devices" / "0000:02:00.1").mkdir(parents=True)
            (gpu2 / "iommu_group").symlink_to(iommu / "8")
            (gpu2 / "driver").symlink_to(root / "drivers" / "amdgpu")

            lspci_output = "\n".join(
                [
                    "0000:01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 [10de:1eb8]",
                    "0000:01:00.1 Audio device [0403]: NVIDIA Corporation Device [10de:10f8]",
                    "0000:02:00.0 3D controller [0302]: Advanced Micro Devices, Inc. [AMD/ATI] Navi [1002:744c]",
                ]
            )

            service = self._mk_service(lspci_output, root)
            gpus = service.list_gpus()

            self.assertEqual(len(gpus), 2)
            first = gpus[0]
            self.assertEqual(first["node"], "node-a")
            self.assertEqual(first["pci_address"], "0000:01:00.0")
            self.assertEqual(first["vendor"], "nvidia")
            self.assertEqual(first["driver"], "vfio-pci")
            self.assertEqual(first["iommu_group"], "7")
            self.assertEqual(first["iommu_group_size"], 1)
            self.assertEqual(first["status"], "assigned")
            self.assertTrue(first["passthrough_ready"])

            second = gpus[1]
            self.assertEqual(second["vendor"], "amd")
            self.assertEqual(second["iommu_group"], "8")
            self.assertEqual(second["iommu_group_size"], 2)
            self.assertEqual(second["status"], "not-isolatable")
            self.assertFalse(second["passthrough_ready"])


if __name__ == "__main__":
    unittest.main()
