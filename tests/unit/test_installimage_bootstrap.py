from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BOOTSTRAP_SCRIPT = ROOT_DIR / "server-installer" / "installimage" / "usr" / "local" / "bin" / "beagle-installimage-bootstrap"
BOOTSTRAP_SERVICE = ROOT_DIR / "server-installer" / "installimage" / "etc" / "systemd" / "system" / "beagle-installimage-bootstrap.service"
NETWORK_HEAL_SERVICE = ROOT_DIR / "server-installer" / "installimage" / "etc" / "systemd" / "system" / "beagle-network-interface-heal.service"


class BootstrapServiceUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._service_text = BOOTSTRAP_SERVICE.read_text(encoding="utf-8")

    def test_service_depends_on_network_online_target(self) -> None:
        self.assertIn("network-online.target", self._service_text)
        self.assertIn("Wants=network-online.target", self._service_text)

    def test_service_orders_after_network_heal(self) -> None:
        self.assertIn("beagle-network-interface-heal.service", self._service_text)

    def test_service_condition_prevents_rerun_if_done_file_exists(self) -> None:
        self.assertIn("ConditionPathExists=!/var/lib/beagle/installimage-bootstrap/done", self._service_text)

    def test_service_has_timeout(self) -> None:
        self.assertIn("TimeoutStartSec=", self._service_text)
        for line in self._service_text.splitlines():
            if "TimeoutStartSec=" in line:
                value = line.split("=", 1)[1].strip()
                self.assertTrue(value.isdigit() or value.isalpha(), f"Unexpected TimeoutStartSec: {value}")

    def test_service_type_is_oneshot(self) -> None:
        self.assertIn("Type=oneshot", self._service_text)

    def test_service_output_goes_to_journal(self) -> None:
        self.assertIn("StandardOutput=journal", self._service_text)
        self.assertIn("StandardError=journal", self._service_text)

    def test_service_wantedby_multi_user_target(self) -> None:
        self.assertIn("WantedBy=multi-user.target", self._service_text)


class BootstrapScriptSyntaxTests(unittest.TestCase):
    def test_bootstrap_script_passes_bash_syntax_check(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(BOOTSTRAP_SCRIPT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"bash -n failed: {result.stderr}")

    def test_bootstrap_script_uses_set_euo_pipefail(self) -> None:
        text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", text)

    def test_bootstrap_script_generates_log_file(self) -> None:
        text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("/var/log/beagle-installimage-bootstrap.log", text)

    def test_bootstrap_script_writes_done_file(self) -> None:
        text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("touch \"$DONE_FILE\"", text)

    def test_bootstrap_script_guards_missing_source_archive(self) -> None:
        text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("missing Beagle source archive", text)

    def test_bootstrap_script_credentials_file_chmod_600(self) -> None:
        text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("chmod 0600 \"$CREDENTIALS_FILE\"", text)

    def test_bootstrap_script_password_file_chmod_600(self) -> None:
        text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("chmod 0600 \"$PASSWORD_FILE\"", text)

    def test_bootstrap_skip_if_done_file_present(self) -> None:
        text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("installimage bootstrap already completed", text)

    def test_bootstrap_respects_disable_env_var(self) -> None:
        text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("BOOTSTRAP_DISABLE", text)
        self.assertIn("bootstrap admin user generation disabled", text)

    def test_bootstrap_sets_public_stream_host_from_ip(self) -> None:
        text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("BEAGLE_PUBLIC_STREAM_HOST", text)

    def test_bootstrap_uses_noninteractive_install_mode(self) -> None:
        text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("BEAGLE_INSTALL_NONINTERACTIVE=1", text)


class BootstrapEarlyExitTests(unittest.TestCase):
    """
    Test that the bootstrap script exits cleanly when done file is already present.
    Uses a minimal bash call with env substitution only (no real filesystem).
    """

    def test_bootstrap_exits_zero_when_done_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            done_file = Path(tmp) / "done"
            done_file.write_text("", encoding="utf-8")

            script_text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
            # Patch the DONE_FILE path and disable the exec redirect that appends to a real log file.
            patched = script_text.replace(
                'STATE_DIR="/var/lib/beagle/installimage-bootstrap"',
                f'STATE_DIR="{tmp}"',
            ).replace(
                'exec >>"$LOG_FILE" 2>&1',
                "# exec disabled for test",
            ).replace(
                'SOURCE_ARCHIVE="/usr/local/share/beagle/beagle-os-source.tar.gz"',
                f'SOURCE_ARCHIVE="{tmp}/nonexistent.tar.gz"',
            )

            patched_path = Path(tmp) / "bootstrap-test"
            patched_path.write_text(patched, encoding="utf-8")
            patched_path.chmod(0o755)

            result = subprocess.run(
                ["bash", str(patched_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"Expected 0 (done), got {result.returncode}\nstderr: {result.stderr}")

    def test_bootstrap_exits_nonzero_when_archive_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script_text = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
            patched = script_text.replace(
                'STATE_DIR="/var/lib/beagle/installimage-bootstrap"',
                f'STATE_DIR="{tmp}"',
            ).replace(
                'exec >>"$LOG_FILE" 2>&1',
                "# exec disabled for test",
            ).replace(
                'SOURCE_ARCHIVE="/usr/local/share/beagle/beagle-os-source.tar.gz"',
                f'SOURCE_ARCHIVE="{tmp}/nonexistent.tar.gz"',
            ).replace(
                'PRIMARY_IP="$(wait_for_ip || true)"',
                'PRIMARY_IP=""',
            ).replace(
                'SERVER_NAME="$(hostname -f 2>/dev/null || hostname)"',
                'SERVER_NAME="test-host"',
            )

            patched_path = Path(tmp) / "bootstrap-test"
            patched_path.write_text(patched, encoding="utf-8")
            patched_path.chmod(0o755)

            result = subprocess.run(
                ["bash", str(patched_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(result.returncode, 0, "Expected non-zero exit when archive missing")


if __name__ == "__main__":
    unittest.main()
