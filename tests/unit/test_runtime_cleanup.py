from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from runtime_cleanup import cleanup_vm_runtime_artifacts


class RuntimeCleanupTests(unittest.TestCase):
    def test_cleanup_removes_stale_vm_runtime_files_for_reused_vmid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            endpoints_dir = root / "endpoints"
            installer_dir = root / "installer-prep"
            actions_dir = root / "actions"
            tokens_dir = root / "ubuntu-beagle-install"
            secrets_dir = root / "vm-secrets"
            usb_dir = root / "usb-auth"
            for path in (endpoints_dir, installer_dir, actions_dir, tokens_dir, secrets_dir, usb_dir):
                path.mkdir(parents=True, exist_ok=True)

            targets = [
                endpoints_dir / "beagle-0-100.json",
                installer_dir / "beagle-0-100.json",
                installer_dir / "beagle-0-100.log",
                actions_dir / "beagle-0-100-queue.json",
                actions_dir / "beagle-0-100-last-result.json",
                secrets_dir / "beagle-0-100.json",
                usb_dir / "beagle-0-100.pub",
            ]
            for path in targets:
                path.write_text("{}", encoding="utf-8")

            (tokens_dir / "old-100.json").write_text(json.dumps({"vmid": 100}), encoding="utf-8")
            (tokens_dir / "old-101.json").write_text(json.dumps({"vmid": 101}), encoding="utf-8")

            removed = cleanup_vm_runtime_artifacts(
                vmid=100,
                actions_dir=actions_dir,
                endpoints_dir=endpoints_dir,
                installer_prep_dir=installer_dir,
                load_json_file=lambda path, default: json.loads(path.read_text(encoding="utf-8")) if path.exists() else default,
                ubuntu_beagle_tokens_dir=tokens_dir,
                usb_tunnel_auth_dir=usb_dir,
                vm_secrets_dir=secrets_dir,
            )

            self.assertGreaterEqual(len(removed), 8)
            for path in targets:
                self.assertFalse(path.exists(), path)
            self.assertFalse((tokens_dir / "old-100.json").exists())
            self.assertTrue((tokens_dir / "old-101.json").exists())


if __name__ == "__main__":
    unittest.main()
