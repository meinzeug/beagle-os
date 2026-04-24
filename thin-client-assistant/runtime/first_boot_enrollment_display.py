#!/usr/bin/env python3
"""First-boot enrollment display for Beagle Endpoint OS.

Shows an enrollment code and QR code on the terminal on first boot when
the endpoint has not yet been enrolled with a Beagle cluster.

Usage:
    python3 first_boot_enrollment_display.py [--once] [--config /etc/pve-thin-client/thinclient.conf]

The script:
  1. Detects whether enrollment is needed (no MANAGER_TOKEN set).
  2. Generates a short human-readable enrollment display code.
  3. Shows an ASCII QR code and text URL pointing to the Web Console enrollment page.
  4. Optionally polls the config file every 10s to detect when enrollment completes.

Exit codes:
  0  Already enrolled or enrollment completed successfully.
  1  Error or enrollment not yet complete (in --once mode).
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
import argparse
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Minimal ASCII QR code using qrencode if available, else URL text only
# ---------------------------------------------------------------------------

def _run_qrencode(data: str) -> str | None:
    """Try to generate ASCII QR code via qrencode CLI."""
    try:
        result = subprocess.run(
            ["qrencode", "-t", "UTF8", "-o", "-", data],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _run_qr_python(data: str) -> str | None:
    """Try to generate ASCII QR code via Python qrcode library."""
    try:
        import qrcode  # type: ignore[import]
        import io

        qr = qrcode.QRCode(border=1)
        qr.add_data(data)
        qr.make(fit=True)
        buf = io.StringIO()
        qr.print_ascii(out=buf)
        return buf.getvalue().strip()
    except ImportError:
        pass
    return None


def display_qr_code(url: str) -> None:
    """Display QR code for the URL using best available method."""
    qr_ascii = _run_qrencode(url) or _run_qr_python(url)
    if qr_ascii:
        print(qr_ascii)
    else:
        # Fallback: show URL in a visible box
        border = "+" + "-" * (len(url) + 4) + "+"
        print(border)
        print(f"|  {url}  |")
        print(border)
        print("  (Install qrencode for QR code display)")


# ---------------------------------------------------------------------------
# Enrollment code generation
# ---------------------------------------------------------------------------

def _generate_display_code(machine_id: str) -> str:
    """Generate a short deterministic display code from machine-id.

    Format: XXXX-DDDD  (4 uppercase letters + 4 digits)
    This is human-typeable and long enough to avoid collisions in small fleets.
    """
    digest = hashlib.sha256(machine_id.encode()).hexdigest()
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"  # no I, O, Q for readability
    code_letters = "".join(letters[int(digest[i * 2: i * 2 + 2], 16) % len(letters)] for i in range(4))
    code_digits = str(int(digest[8:12], 16) % 10000).zfill(4)
    return f"{code_letters}-{code_digits}"


def _read_machine_id() -> str:
    """Read the system machine-id (stable identifier for this endpoint)."""
    for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
        try:
            content = Path(path).read_text(encoding="utf-8").strip()
            if content:
                return content
        except OSError:
            continue
    # Fallback: use hostname
    try:
        import socket
        return socket.gethostname()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Config / enrollment state detection
# ---------------------------------------------------------------------------

def _read_env_file(path: str) -> dict[str, str]:
    """Read a simple KEY=VALUE env file, ignoring comments."""
    result: dict[str, str] = {}
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                # Strip surrounding quotes from value
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                    v = v[1:-1]
                result[k.strip()] = v
    except OSError:
        pass
    return result


def _is_enrolled(config_path: str, credentials_path: str) -> bool:
    """Return True if the endpoint already has a manager token."""
    env = os.environ.copy()
    env.update(_read_env_file(config_path))
    env.update(_read_env_file(credentials_path))
    token = env.get("PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN", "").strip()
    return bool(token)


def _get_manager_url(config_path: str, credentials_path: str) -> str:
    """Return the configured manager URL or empty string."""
    env = os.environ.copy()
    env.update(_read_env_file(config_path))
    env.update(_read_env_file(credentials_path))
    return env.get("PVE_THIN_CLIENT_BEAGLE_MANAGER_URL", "").strip()


# ---------------------------------------------------------------------------
# Display banner
# ---------------------------------------------------------------------------

def _clear_screen() -> None:
    os.system("clear")


def _print_enrollment_screen(display_code: str, enroll_url: str, manager_url: str, hostname: str) -> None:
    """Print the enrollment screen."""
    _clear_screen()
    width = 72
    print("=" * width)
    print(" BEAGLE ENDPOINT OS — ENROLLMENT REQUIRED ".center(width))
    print("=" * width)
    print()
    print(f"  Hostname:        {hostname}")
    print(f"  Enrollment Code: {display_code}")
    print()
    print("  To enroll this endpoint:")
    print(f"  1. Open the Beagle Web Console: {manager_url or '<not configured>'}")
    print("  2. Navigate to: Endpoints → Enroll New Endpoint")
    print(f"  3. Enter code: {display_code}")
    print("     or scan the QR code below:")
    print()
    display_qr_code(enroll_url)
    print()
    print("-" * width)
    print("  Waiting for enrollment... (checking every 10 seconds)")
    print("  Press Ctrl+C to exit without waiting.")
    print("=" * width)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Beagle Endpoint OS first-boot enrollment display",
    )
    parser.add_argument(
        "--config",
        default="/etc/pve-thin-client/thinclient.conf",
        help="Path to thinclient.conf (default: /etc/pve-thin-client/thinclient.conf)",
    )
    parser.add_argument(
        "--credentials",
        default="/etc/pve-thin-client/credentials.env",
        help="Path to credentials.env",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Check enrollment once and exit (no polling loop)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds between enrollment status checks (default: 10)",
    )
    args = parser.parse_args(argv)

    config_path = args.config
    credentials_path = args.credentials

    # Already enrolled?
    if _is_enrolled(config_path, credentials_path):
        print("Endpoint is already enrolled. Enrollment display not needed.")
        return 0

    machine_id = _read_machine_id()
    display_code = _generate_display_code(machine_id)
    manager_url = _get_manager_url(config_path, credentials_path)

    # Construct enrollment URL with pre-filled code
    if manager_url:
        enroll_url = f"{manager_url.rstrip('/')}/enroll?code={display_code}"
    else:
        enroll_url = f"https://beagle-console/enroll?code={display_code}"

    try:
        import socket
        hostname = socket.gethostname()
    except Exception:
        hostname = machine_id[:12]

    _print_enrollment_screen(display_code, enroll_url, manager_url, hostname)

    if args.once:
        return 1  # Not yet enrolled

    # Poll loop
    interval = max(5, args.poll_interval)
    try:
        while True:
            time.sleep(interval)
            if _is_enrolled(config_path, credentials_path):
                _clear_screen()
                print("=" * 72)
                print(" ENROLLMENT COMPLETE ".center(72))
                print("=" * 72)
                print(f"\n  Endpoint '{hostname}' has been successfully enrolled.")
                print("  Starting Beagle runtime...\n")
                return 0
            # Re-draw the screen to update any info
            _print_enrollment_screen(display_code, enroll_url, manager_url, hostname)
    except KeyboardInterrupt:
        print("\nEnrollment display exited.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
