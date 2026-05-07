import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.virtualization.streaming_profile import (  # noqa: E402
    StreamingColorCodec,
    StreamingEncoder,
    StreamingNetworkMode,
    production_beaglestream_profile,
    streaming_profile_from_payload,
    streaming_profile_to_dict,
)


class StreamingProfileContractTests(unittest.TestCase):
    def test_defaults(self) -> None:
        profile = streaming_profile_from_payload({})
        self.assertEqual(profile.encoder, StreamingEncoder.AUTO)
        self.assertEqual(profile.bitrate_kbps, 32000)
        self.assertEqual(profile.resolution, "1920x1080")
        self.assertEqual(profile.fps, 60)
        self.assertEqual(profile.color, StreamingColorCodec.H265)
        self.assertFalse(profile.hdr)
        self.assertFalse(profile.audio_input_enabled)
        self.assertFalse(profile.gamepad_redirect_enabled)
        self.assertFalse(profile.wacom_tablet_enabled)
        self.assertFalse(profile.usb_redirect_enabled)

    def test_production_beaglestream_profile_freezes_live_smooth_secure_baseline(self) -> None:
        profile = production_beaglestream_profile()

        self.assertEqual(profile.encoder, StreamingEncoder.SOFTWARE)
        self.assertEqual(profile.bitrate_kbps, 32000)
        self.assertEqual(profile.resolution, "1920x1080")
        self.assertEqual(profile.fps, 60)
        self.assertEqual(profile.color, StreamingColorCodec.H264)
        self.assertEqual(profile.network_mode, StreamingNetworkMode.VPN_REQUIRED)
        self.assertFalse(profile.hdr)

    def test_valid_custom_payload(self) -> None:
        profile = streaming_profile_from_payload(
            {
                "encoder": "nvenc",
                "bitrate_kbps": 35000,
                "resolution": "3840x2160",
                "fps": 120,
                "color": "av1",
                "hdr": True,
                "audio_input_enabled": True,
                "gamepad_redirect_enabled": True,
                "wacom_tablet_enabled": True,
                "usb_redirect_enabled": True,
            }
        )
        payload = streaming_profile_to_dict(profile)
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload.get("encoder"), "nvenc")
        self.assertEqual(payload.get("resolution"), "3840x2160")
        self.assertEqual(payload.get("color"), "av1")
        self.assertTrue(payload.get("hdr"))
        self.assertTrue(payload.get("audio_input_enabled"))
        self.assertTrue(payload.get("gamepad_redirect_enabled"))
        self.assertTrue(payload.get("wacom_tablet_enabled"))
        self.assertTrue(payload.get("usb_redirect_enabled"))

    def test_rejects_invalid_codec(self) -> None:
        with self.assertRaises(ValueError):
            streaming_profile_from_payload({"color": "vp9"})

    def test_rejects_invalid_resolution(self) -> None:
        with self.assertRaises(ValueError):
            streaming_profile_from_payload({"resolution": "abc"})


if __name__ == "__main__":
    unittest.main()