"""Regression coverage for USB/IP reconciliation and guest configuration."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'thin-client-assistant/runtime/beagle_usb_runtime_usbipd.sh'
ATTACH = ROOT / 'scripts/lib/beagle-usb-attach'


class UsbStabilityTests(unittest.TestCase):
    def test_already_attached_device_is_not_rebound_or_daemon_restarted(self):
        script = r'''
source "$1"
usb_auto_bind() { echo 1; }
require_enabled() { :; }
is_bound_to_usbip_host() { return 0; }
bound_add() { :; }
state_bound_busids() { echo 1-2.1; }
ensure_usbipd() { :; }
usbip_bin() { echo false; }
restart_usbipd() { echo forbidden; return 1; }
autobind_hotplug_device 1-2.1
sync_bound_devices
'''
        result = subprocess.run(['bash', '-c', script, 'test', str(RUNTIME)], capture_output=True, text=True, check=True)
        self.assertNotIn('forbidden', result.stdout)

    def test_guest_reads_configured_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'env').write_text('BEAGLE_USB_ATTACH_HOST=10.88.1.1\nBEAGLE_USB_ATTACH_PORT=3240\n')
            for name, content in {'modprobe': 'exit 0', 'usbip': 'echo "$*" >> "$CALLS"; exit 1', 'sleep': 'exit 9'}.items():
                path = root / name
                path.write_text('#!/bin/sh\n' + content + '\n')
                path.chmod(0o755)
            env = dict(os.environ, PATH=f'{root}:' + os.environ['PATH'], CALLS=str(root / 'calls'), BEAGLE_USB_ATTACH_ENV_FILE=str(root / 'env'))
            proc = subprocess.Popen(['bash', str(ATTACH)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                import time
                time.sleep(.1)
            finally:
                proc.terminate()
                proc.wait(timeout=3)
            self.assertIn('--tcp-port 3240 list -r 10.88.1.1', (root / 'calls').read_text())

    def test_guest_attaches_kernel_and_userspace_bus_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'env').write_text('BEAGLE_USB_ATTACH_HOST=127.0.0.1\nBEAGLE_USB_ATTACH_PORT=13240\n')
            commands = {
                'modprobe': 'exit 0',
                'sleep': 'exec /bin/sleep 10',
                'usbip': r'''case "$*" in
                  *" list "*) printf "    1-2.1.3: kernel device\\n    1-55-3: userspace device\\n    invalid-device: ignore\\n" ;;
                  *" attach "*) printf "%s\\n" "$*" >> "$CALLS" ;;
                  *) exit 0 ;;
                esac''',
            }
            for name, content in commands.items():
                path = root / name
                path.write_text('#!/bin/sh\n' + content + '\n')
                path.chmod(0o755)
            env = dict(os.environ, PATH=f'{root}:' + os.environ['PATH'], CALLS=str(root / 'calls'), BEAGLE_USB_ATTACH_ENV_FILE=str(root / 'env'))
            proc = subprocess.Popen(['bash', str(ATTACH)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                import time
                for _ in range(100):
                    if (root / 'calls').exists() and len((root / 'calls').read_text().splitlines()) >= 2:
                        break
                    time.sleep(.02)
                calls = (root / 'calls').read_text().splitlines()
                self.assertEqual(len(calls), 2)
                self.assertTrue(any('-b 1-2.1.3' in line for line in calls))
                self.assertTrue(any('-b 1-55-3' in line for line in calls))
            finally:
                import signal
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()
