from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "thin-client-assistant" / "usb" / "usb_manifest.py"


class UsbManifestTests(unittest.TestCase):
    def test_write_usb_manifest_persists_remote_url_and_bundled_payload_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "manifest.json"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "write-usb-manifest",
                    "--path",
                    str(manifest),
                    "--project-version",
                    "test",
                    "--usb-label",
                    "BEAGLEOS",
                    "--target-device",
                    "/dev/sdz",
                    "--payload-source",
                    "https://srv1.beagle-os.com/beagle-downloads/pve-thin-client-usb-payload-latest.tar.gz",
                    "--payload-source-url",
                    "https://srv1.beagle-os.com/beagle-downloads/pve-thin-client-usb-payload-latest.tar.gz",
                    "--payload-source-kind",
                    "bundled-usb",
                    "--bundled-payload-relpath",
                    "pve-thin-client/live",
                    "--filesystem-squashfs-sha256",
                    "deadbeef",
                    "--usb-writer-variant",
                    "installer",
                ],
                check=True,
            )

            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["payload_source"], "bundled-usb")
            self.assertEqual(
                payload["payload_source_url"],
                "https://srv1.beagle-os.com/beagle-downloads/pve-thin-client-usb-payload-latest.tar.gz",
            )
            self.assertEqual(payload["bundled_payload_relpath"], "pve-thin-client/live")

            remote_url = subprocess.check_output(
                [sys.executable, str(SCRIPT), "read-payload-source", "--path", str(manifest)],
                text=True,
            ).strip()
            bundled_relpath = subprocess.check_output(
                [sys.executable, str(SCRIPT), "read-bundled-payload-relpath", "--path", str(manifest)],
                text=True,
            ).strip()

            self.assertEqual(
                remote_url,
                "https://srv1.beagle-os.com/beagle-downloads/pve-thin-client-usb-payload-latest.tar.gz",
            )
            self.assertEqual(bundled_relpath, "pve-thin-client/live")


if __name__ == "__main__":
    unittest.main()
