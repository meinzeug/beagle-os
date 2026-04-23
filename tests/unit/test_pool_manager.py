import tempfile
import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from core.virtualization.desktop_pool import DesktopLease, DesktopPoolMode, DesktopPoolSpec
from core.virtualization.streaming_profile import StreamingColorCodec, StreamingEncoder, StreamingProfile
from pool_manager import PoolManagerService


class PoolManagerServiceTests(unittest.TestCase):
    def _build_service(self, *, list_nodes=None, vm_node_of=None, list_gpu_inventory=None) -> PoolManagerService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        state_file = Path(temp_dir.name) / "desktop-pools.json"
        return PoolManagerService(
            state_file=state_file,
            utcnow=lambda: "2026-04-22T12:00:00Z",
            list_nodes=list_nodes,
            vm_node_of=vm_node_of,
            list_gpu_inventory=list_gpu_inventory,
        )

    def test_create_pool_and_list(self) -> None:
        service = self._build_service()
        info = service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-a",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=2,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )
        self.assertEqual(info.pool_id, "pool-a")
        self.assertEqual(len(service.list_pools()), 1)

    def test_create_pool_persists_gpu_class(self) -> None:
        service = self._build_service()
        info = service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-gpu",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
                gpu_class="passthrough-nvidia",
            )
        )
        self.assertEqual(info.gpu_class, "passthrough-nvidia")
        payload = service.pool_info_to_dict(info)
        self.assertEqual(payload["gpu_class"], "passthrough-nvidia")

    def test_create_pool_persists_session_recording_policy(self) -> None:
        service = self._build_service()
        info = service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-rec",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
                session_recording="always",
            )
        )
        payload = service.pool_info_to_dict(info)
        self.assertEqual(payload["session_recording"], "always")

    def test_update_pool_normalizes_invalid_session_recording(self) -> None:
        service = self._build_service()
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-rec",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )
        updated = service.update_pool("pool-rec", {"session_recording": "invalid_value"})
        payload = service.pool_info_to_dict(updated)
        self.assertEqual(payload["session_recording"], "disabled")

    def test_allocate_release_recycle_non_persistent(self) -> None:
        service = self._build_service()
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-a",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )
        service.register_vm("pool-a", 101)
        lease = service.allocate_desktop("pool-a", "alice")
        self.assertEqual(lease.vmid, 101)
        self.assertEqual(lease.state, "in_use")

        released = service.release_desktop("pool-a", 101, "alice")
        self.assertEqual(released.state, "recycling")

        recycled = service.recycle_desktop("pool-a", 101)
        self.assertEqual(recycled.state, "free")
        self.assertEqual(recycled.user_id, "")

    def test_persistent_mode_reuses_same_vm(self) -> None:
        service = self._build_service()
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-p",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )
        service.register_vm("pool-p", 201)
        lease1 = service.allocate_desktop("pool-p", "alice")
        self.assertEqual(lease1.vmid, 201)
        released = service.release_desktop("pool-p", 201, "alice")
        self.assertEqual(released.state, "free")
        lease2 = service.allocate_desktop("pool-p", "alice")
        self.assertEqual(lease2.vmid, 201)

    def test_dedicated_mode_keeps_assignment(self) -> None:
        service = self._build_service()
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-d",
                template_id="tpl-1",
                mode=DesktopPoolMode.DEDICATED,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )
        service.register_vm("pool-d", 301)
        lease1 = service.allocate_desktop("pool-d", "alice")
        self.assertEqual(lease1.vmid, 301)
        service.release_desktop("pool-d", 301, "alice")
        lease2 = service.allocate_desktop("pool-d", "alice")
        self.assertEqual(lease2.vmid, 301)

    def test_streaming_profile_persist_and_update(self) -> None:
        service = self._build_service()
        info = service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-stream",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
                streaming_profile=StreamingProfile(
                    encoder=StreamingEncoder.NVENC,
                    bitrate_kbps=30000,
                    resolution="2560x1440",
                    fps=120,
                    color=StreamingColorCodec.AV1,
                    hdr=True,
                    audio_input_enabled=True,
                    gamepad_redirect_enabled=True,
                    wacom_tablet_enabled=True,
                    usb_redirect_enabled=True,
                ),
            )
        )
        self.assertIsNotNone(info.streaming_profile)
        self.assertEqual(info.streaming_profile.encoder, StreamingEncoder.NVENC)
        self.assertEqual(info.streaming_profile.resolution, "2560x1440")

        updated = service.update_pool(
            "pool-stream",
            {
                "streaming_profile": {
                    "encoder": "software",
                    "bitrate_kbps": 12000,
                    "resolution": "1920x1080",
                    "fps": 60,
                    "color": "h264",
                    "hdr": False,
                    "audio_input_enabled": False,
                    "gamepad_redirect_enabled": False,
                    "wacom_tablet_enabled": False,
                    "usb_redirect_enabled": False,
                }
            },
        )
        self.assertIsNotNone(updated.streaming_profile)
        self.assertEqual(updated.streaming_profile.encoder, StreamingEncoder.SOFTWARE)
        self.assertEqual(updated.streaming_profile.color, StreamingColorCodec.H264)
        self.assertFalse(updated.streaming_profile.wacom_tablet_enabled)
        self.assertFalse(updated.streaming_profile.usb_redirect_enabled)

        payload = service.pool_info_to_dict(updated)
        self.assertIn("streaming_profile", payload)
        self.assertEqual(payload["streaming_profile"]["encoder"], "software")

    def test_lease_to_dict_includes_stream_health(self) -> None:
        service = self._build_service()
        lease_without_health = DesktopLease(
            pool_id="pool-a",
            vmid=101,
            user_id="alice",
            mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
            state="in_use",
            assigned_at="2026-04-22T12:00:00Z",
        )
        payload_without_health = service.lease_to_dict(lease_without_health)
        self.assertIn("stream_health", payload_without_health)
        self.assertIsNone(payload_without_health["stream_health"])

        lease_with_health = DesktopLease(
            pool_id="pool-a",
            vmid=101,
            user_id="alice",
            mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
            state="in_use",
            assigned_at="2026-04-22T12:00:00Z",
            stream_health={"fps": 60, "rtt_ms": 12},
        )
        payload_with_health = service.lease_to_dict(lease_with_health)
        self.assertEqual(payload_with_health["stream_health"], {"fps": 60, "rtt_ms": 12})

    def test_list_active_sessions_and_update_stream_health(self) -> None:
        service = self._build_service()
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-session",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=2,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )
        service.register_vm("pool-session", 501)
        lease = service.allocate_desktop("pool-session", "alice")
        self.assertEqual(lease.vmid, 501)

        sessions = service.list_active_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "pool-session:501")
        self.assertIsNone(sessions[0]["stream_health"])

        updated = service.update_stream_health(
            pool_id="pool-session",
            vmid=501,
            stream_health={
                "rtt_ms": 18,
                "fps": 60,
                "dropped_frames": 2,
                "encoder_load": 76,
                "updated_at": "2026-04-22T12:05:00Z",
            },
        )
        payload = service.lease_to_dict(updated)
        self.assertEqual(payload["stream_health"]["rtt_ms"], 18)
        self.assertEqual(payload["stream_health"]["fps"], 60)

    def test_register_vm_honors_anti_affinity_policy(self) -> None:
        online_nodes = [
            {"name": "node-a", "status": "online"},
            {"name": "node-b", "status": "online"},
        ]

        def vm_node_of(vmid: int) -> str:
            mapping = {501: "node-a", 502: "node-a"}
            return mapping.get(int(vmid), "")

        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        service = PoolManagerService(
            state_file=Path(temp_dir.name) / "desktop-pools.json",
            utcnow=lambda: "2026-04-22T12:00:00Z",
            list_nodes=lambda: online_nodes,
            vm_node_of=vm_node_of,
        )
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-anti",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=2,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )

        policy = {
            "anti_affinity_groups": [
                {"group_id": "replicas", "vmids": [501, 502]},
            ]
        }
        first = service.register_vm("pool-anti", 501, scheduler_policy=policy)
        second = service.register_vm("pool-anti", 502, scheduler_policy=policy)

        self.assertEqual(first["node"], "node-a")
        self.assertEqual(second["node"], "node-b")

    def test_register_vm_honors_affinity_policy(self) -> None:
        online_nodes = [
            {"name": "node-a", "status": "online"},
            {"name": "node-b", "status": "online"},
        ]

        def vm_node_of(vmid: int) -> str:
            mapping = {601: "node-b", 602: "node-a"}
            return mapping.get(int(vmid), "")

        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        service = PoolManagerService(
            state_file=Path(temp_dir.name) / "desktop-pools.json",
            utcnow=lambda: "2026-04-22T12:00:00Z",
            list_nodes=lambda: online_nodes,
            vm_node_of=vm_node_of,
        )
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-aff",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=2,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )

        policy = {
            "affinity_groups": [
                {"group_id": "app-db", "vmids": [601, 602]},
            ]
        }
        first = service.register_vm("pool-aff", 601, scheduler_policy=policy)
        second = service.register_vm("pool-aff", 602, scheduler_policy=policy)

        self.assertEqual(first["node"], "node-b")
        self.assertEqual(second["node"], "node-b")

    def test_register_vm_with_gpu_class_reserves_slot(self) -> None:
        online_nodes = [{"name": "node-a", "status": "online"}]
        gpu_inventory = [
            {
                "node": "node-a",
                "pci_address": "0000:01:00.0",
                "vendor": "nvidia",
                "model": "NVIDIA L4",
                "status": "available-for-passthrough",
            }
        ]
        service = self._build_service(
            list_nodes=lambda: online_nodes,
            list_gpu_inventory=lambda: gpu_inventory,
        )
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-gpu",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
                gpu_class="passthrough-nvidia",
            )
        )

        vm = service.register_vm("pool-gpu", 701)
        self.assertEqual(vm["state"], "free")
        self.assertEqual(vm["node"], "node-a")

        state = service._load()
        reservation = state["gpu_reservations"].get("701")
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation["slot"], "0000:01:00.0")
        self.assertEqual(reservation["gpu_class"], "passthrough-nvidia")

    def test_register_vm_sets_pending_gpu_when_no_slot(self) -> None:
        online_nodes = [{"name": "node-a", "status": "online"}]
        gpu_inventory = [
            {
                "node": "node-a",
                "pci_address": "0000:01:00.0",
                "vendor": "nvidia",
                "model": "NVIDIA L4",
                "status": "available-for-passthrough",
            }
        ]
        service = self._build_service(
            list_nodes=lambda: online_nodes,
            list_gpu_inventory=lambda: gpu_inventory,
        )
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-gpu",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=2,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
                gpu_class="passthrough-nvidia",
            )
        )

        first = service.register_vm("pool-gpu", 801)
        second = service.register_vm("pool-gpu", 802)
        self.assertEqual(first["state"], "free")
        self.assertEqual(second["state"], "pending-gpu")
        self.assertEqual(second["node"], "")


if __name__ == "__main__":
    unittest.main()
