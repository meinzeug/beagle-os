#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import hashlib
import ipaddress
import base64
import secrets
import shlex
import tempfile
import time
import uuid
import pwd
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

def load_env_defaults(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value

load_env_defaults("/etc/beagle/host.env")
load_env_defaults("/etc/beagle/beagle-proxy.env")

VERSION = "dev"
ROOT_DIR = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT_DIR / "VERSION"
if VERSION_FILE.exists():
    VERSION = VERSION_FILE.read_text(encoding="utf-8").strip() or VERSION

LISTEN_HOST = os.environ.get("BEAGLE_MANAGER_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("BEAGLE_MANAGER_LISTEN_PORT", "9088"))
DATA_DIR = Path(os.environ.get("BEAGLE_MANAGER_DATA_DIR", "/var/lib/beagle/beagle-manager"))
EFFECTIVE_DATA_DIR = DATA_DIR
API_TOKEN = os.environ.get("BEAGLE_MANAGER_API_TOKEN", "").strip()
ALLOW_LOCALHOST_NOAUTH = os.environ.get("BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH", "0").strip().lower() in {"1", "true", "yes", "on"}
STALE_ENDPOINT_SECONDS = int(os.environ.get("BEAGLE_MANAGER_STALE_ENDPOINT_SECONDS", "600"))
DOWNLOADS_STATUS_FILE = ROOT_DIR / "dist" / "beagle-downloads-status.json"
VM_INSTALLERS_FILE = ROOT_DIR / "dist" / "beagle-vm-installers.json"
HOSTED_INSTALLER_TEMPLATE_FILE = ROOT_DIR / "dist" / "pve-thin-client-usb-installer-host-latest.sh"
HOSTED_LIVE_USB_TEMPLATE_FILE = ROOT_DIR / "dist" / "pve-thin-client-live-usb-host-latest.sh"
HOSTED_WINDOWS_INSTALLER_TEMPLATE_FILE = ROOT_DIR / "dist" / "pve-thin-client-usb-installer-host-latest.ps1"
RAW_WINDOWS_INSTALLER_TEMPLATE_FILE = ROOT_DIR / "thin-client-assistant" / "usb" / "pve-thin-client-usb-installer.ps1"
HOSTED_INSTALLER_ISO_FILE = ROOT_DIR / "dist" / "beagle-os-installer-amd64.iso"
INSTALLER_PREP_SCRIPT_FILE = ROOT_DIR / "scripts" / "ensure-vm-stream-ready.sh"
CREDENTIALS_ENV_FILE = Path(os.environ.get("PVE_DCV_CREDENTIALS_ENV_FILE", "/etc/beagle/credentials.env"))
MANAGER_CERT_FILE = Path(os.environ.get("BEAGLE_MANAGER_CERT_FILE", "/etc/pve/local/pveproxy-ssl.pem"))
PUBLIC_SERVER_NAME = os.environ.get("PVE_DCV_PROXY_SERVER_NAME", "").strip() or os.uname().nodename
PUBLIC_DOWNLOADS_PORT = int(os.environ.get("PVE_DCV_PROXY_LISTEN_PORT", "8443"))
PUBLIC_DOWNLOADS_PATH = os.environ.get("PVE_DCV_DOWNLOADS_PATH", "/beagle-downloads").strip() or "/beagle-downloads"
PUBLIC_STREAM_HOST = os.environ.get("BEAGLE_PUBLIC_STREAM_HOST", "").strip() or PUBLIC_SERVER_NAME
PUBLIC_STREAM_BASE_PORT = int(os.environ.get("BEAGLE_PUBLIC_STREAM_BASE_PORT", "50000"))
PUBLIC_STREAM_PORT_STEP = int(os.environ.get("BEAGLE_PUBLIC_STREAM_PORT_STEP", "32"))
PUBLIC_STREAM_PORT_COUNT = int(os.environ.get("BEAGLE_PUBLIC_STREAM_PORT_COUNT", "256"))
PUBLIC_MANAGER_URL = os.environ.get("PVE_DCV_BEAGLE_MANAGER_URL", "").strip() or f"https://{PUBLIC_SERVER_NAME}:{PUBLIC_DOWNLOADS_PORT}/beagle-api"
ENROLLMENT_TOKEN_TTL_SECONDS = int(os.environ.get("BEAGLE_ENROLLMENT_TOKEN_TTL_SECONDS", "86400"))
SUNSHINE_ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("BEAGLE_SUNSHINE_ACCESS_TOKEN_TTL_SECONDS", "600"))
USB_TUNNEL_SSH_USER = os.environ.get("BEAGLE_USB_TUNNEL_SSH_USER", "thinovernet").strip() or "thinovernet"
USB_TUNNEL_HOME_RAW = os.environ.get("BEAGLE_USB_TUNNEL_HOME", "").strip()
USB_TUNNEL_HOME = Path(USB_TUNNEL_HOME_RAW) if USB_TUNNEL_HOME_RAW else None
USB_TUNNEL_AUTH_DIR_RAW = os.environ.get("BEAGLE_USB_TUNNEL_AUTH_DIR", "").strip()
USB_TUNNEL_AUTH_DIR = Path(USB_TUNNEL_AUTH_DIR_RAW) if USB_TUNNEL_AUTH_DIR_RAW else None
USB_TUNNEL_HOSTKEY_FILE = Path(os.environ.get("BEAGLE_USB_TUNNEL_HOSTKEY_FILE", "/etc/ssh/ssh_host_ed25519_key.pub"))
USB_TUNNEL_ATTACH_HOST = os.environ.get("BEAGLE_USB_TUNNEL_ATTACH_HOST", "10.10.10.1").strip() or "10.10.10.1"
USB_TUNNEL_BASE_PORT = int(os.environ.get("BEAGLE_USB_TUNNEL_BASE_PORT", "43000"))
USB_ACTION_WAIT_SECONDS = float(os.environ.get("BEAGLE_USB_ACTION_WAIT_SECONDS", "25"))
COMMAND_TIMEOUT_SECONDS = float(os.environ.get("BEAGLE_MANAGER_COMMAND_TIMEOUT_SECONDS", "8"))
GUEST_AGENT_TIMEOUT_SECONDS = float(os.environ.get("BEAGLE_MANAGER_GUEST_AGENT_TIMEOUT_SECONDS", "2.5"))
LIST_VMS_CACHE_SECONDS = float(os.environ.get("BEAGLE_MANAGER_LIST_VMS_CACHE_SECONDS", "3"))
VM_CONFIG_CACHE_SECONDS = float(os.environ.get("BEAGLE_MANAGER_VM_CONFIG_CACHE_SECONDS", "5"))
GUEST_IPV4_CACHE_SECONDS = float(os.environ.get("BEAGLE_MANAGER_GUEST_IPV4_CACHE_SECONDS", "10"))
ENABLE_GUEST_IP_LOOKUP = os.environ.get("BEAGLE_MANAGER_ENABLE_GUEST_IP_LOOKUP", "0").strip().lower() in {"1", "true", "yes", "on"}

_CACHE: dict[str, tuple[float, Any]] = {}


def public_installer_iso_url() -> str:
    return f"https://{PUBLIC_SERVER_NAME}:{PUBLIC_DOWNLOADS_PORT}{PUBLIC_DOWNLOADS_PATH}/beagle-os-installer-amd64.iso"


def public_windows_installer_url() -> str:
    return f"https://{PUBLIC_SERVER_NAME}:{PUBLIC_DOWNLOADS_PORT}{PUBLIC_DOWNLOADS_PATH}/pve-thin-client-usb-installer-host-latest.ps1"


@dataclass
class VmSummary:
    vmid: int
    node: str
    name: str
    status: str
    tags: str


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc_timestamp(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def timestamp_age_seconds(value: str) -> int | None:
    parsed = parse_utc_timestamp(value)
    if parsed is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))


def load_json_file(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback
    except json.JSONDecodeError:
        return fallback


def cache_get(key: str, ttl_seconds: float) -> Any:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    created_at, value = entry
    if time.monotonic() - created_at > ttl_seconds:
        _CACHE.pop(key, None)
        return None
    return value


def cache_put(key: str, value: Any) -> Any:
    _CACHE[key] = (time.monotonic(), value)
    return value


def listify(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value is None:
        items = []
    else:
        items = re.split(r"[\s,]+", str(value))
    return [str(item).strip() for item in items if str(item).strip()]


def ensure_data_dir() -> Path:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return DATA_DIR
    except PermissionError:
        fallback = Path("/tmp/beagle-control-plane")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def run_json(command: list[str], *, timeout: float | None = None) -> Any:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS if timeout is None else timeout,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError:
        return None


def run_text(command: list[str], *, timeout: float | None = None) -> str:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS if timeout is None else timeout,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""
    return result.stdout


def endpoints_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "endpoints"
    path.mkdir(parents=True, exist_ok=True)
    return path


def actions_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "actions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def support_bundles_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "support-bundles"
    path.mkdir(parents=True, exist_ok=True)
    return path


def policies_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "policies"
    path.mkdir(parents=True, exist_ok=True)
    return path


def vm_secrets_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "vm-secrets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def enrollment_tokens_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "enrollment-tokens"
    path.mkdir(parents=True, exist_ok=True)
    return path


def endpoint_tokens_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "endpoint-tokens"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sunshine_access_tokens_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "sunshine-access-tokens"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_slug(value: str, default: str = "item") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-")
    return cleaned or default


def action_queue_path(node: str, vmid: int) -> Path:
    safe_node = safe_slug(node, "unknown")
    return actions_dir() / f"{safe_node}-{int(vmid)}-queue.json"


def action_result_path(node: str, vmid: int) -> Path:
    safe_node = safe_slug(node, "unknown")
    return actions_dir() / f"{safe_node}-{int(vmid)}-last-result.json"


def support_bundle_metadata_path(bundle_id: str) -> Path:
    return support_bundles_dir() / f"{safe_slug(bundle_id, 'bundle')}.json"


def support_bundle_archive_path(bundle_id: str, filename: str) -> Path:
    suffix = Path(filename or "support-bundle.tar.gz").suffixes
    extension = "".join(suffix) if suffix else ".bin"
    return support_bundles_dir() / f"{safe_slug(bundle_id, 'bundle')}{extension}"


def load_shell_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return data
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            data[key] = value
    return data


def write_json_file(path: Path, payload: Any, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def random_secret(length: int = 24) -> str:
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(max(12, length)))


def random_pin() -> str:
    return f"{secrets.randbelow(10000):04d}"


def vm_secret_path(node: str, vmid: int) -> Path:
    return vm_secrets_dir() / f"{safe_slug(node, 'unknown')}-{int(vmid)}.json"


def load_vm_secret(node: str, vmid: int) -> dict[str, Any] | None:
    payload = load_json_file(vm_secret_path(node, vmid), None)
    return payload if isinstance(payload, dict) else None


def save_vm_secret(node: str, vmid: int, payload: dict[str, Any]) -> dict[str, Any]:
    clean = dict(payload)
    clean["node"] = node
    clean["vmid"] = int(vmid)
    clean["updated_at"] = utcnow()
    write_json_file(vm_secret_path(node, vmid), clean)
    return clean


def default_usb_tunnel_port(vmid: int) -> int:
    candidate = USB_TUNNEL_BASE_PORT + int(vmid)
    if 1024 <= candidate <= 65535:
        return candidate
    return 43000 + (int(vmid) % 20000)


def generate_ssh_keypair(comment: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="beagle-usb-keygen-") as tmp_dir:
        key_path = Path(tmp_dir) / "id_ed25519"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment, "-f", str(key_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        private_key = key_path.read_text(encoding="utf-8")
        public_key = key_path.with_suffix(".pub").read_text(encoding="utf-8").strip()
        return private_key, public_key


def usb_tunnel_known_host_line() -> str:
    try:
        raw = USB_TUNNEL_HOSTKEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    parts = raw.split()
    if len(parts) < 2:
        return ""
    hostnames = [PUBLIC_SERVER_NAME]
    if PUBLIC_STREAM_HOST and PUBLIC_STREAM_HOST not in hostnames:
        hostnames.append(PUBLIC_STREAM_HOST)
    host_field = ",".join(hostnames)
    return f"{host_field} {parts[0]} {parts[1]}"


def usb_tunnel_user_info() -> pwd.struct_passwd:
    return pwd.getpwnam(USB_TUNNEL_SSH_USER)


def usb_tunnel_home() -> Path:
    if USB_TUNNEL_HOME is not None:
        return USB_TUNNEL_HOME
    return Path(usb_tunnel_user_info().pw_dir)


def usb_tunnel_auth_dir() -> Path:
    if USB_TUNNEL_AUTH_DIR is not None:
        return USB_TUNNEL_AUTH_DIR
    return usb_tunnel_home() / ".ssh" / "authorized_keys.d"


def usb_tunnel_authorized_keys_path() -> Path:
    return usb_tunnel_home() / ".ssh" / "authorized_keys"


def usb_tunnel_authorized_key_line(vm: VmSummary, secret: dict[str, Any]) -> str:
    public_key = str(secret.get("usb_tunnel_public_key", "")).strip()
    port = int(secret.get("usb_tunnel_port", 0) or 0)
    session_script = (Path(__file__).resolve().parent / "beagle-usb-tunnel-session").as_posix()
    return (
        f'command="{session_script}",no-agent-forwarding,no-pty,no-user-rc,no-X11-forwarding,'
        f'permitlisten="{USB_TUNNEL_ATTACH_HOST}:{port}" '
        f"{public_key}"
    )


def sync_usb_tunnel_authorized_key(vm: VmSummary, secret: dict[str, Any]) -> None:
    public_key = str(secret.get("usb_tunnel_public_key", "")).strip()
    port = int(secret.get("usb_tunnel_port", 0) or 0)
    if not public_key or port <= 0:
        return
    try:
        user_info = usb_tunnel_user_info()
    except KeyError:
        return
    tunnel_home = usb_tunnel_home()
    ssh_dir = tunnel_home / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    auth_dir = usb_tunnel_auth_dir()
    auth_dir.mkdir(parents=True, exist_ok=True)
    key_line = usb_tunnel_authorized_key_line(vm, secret) + "\n"
    snippet_path = auth_dir / f"{safe_slug(vm.node, 'node')}-{int(vm.vmid)}.pub"
    snippet_path.write_text(key_line, encoding="utf-8")
    authorized_keys = usb_tunnel_authorized_keys_path()
    managed_lines: list[str] = []
    for item in sorted(auth_dir.glob("*.pub")):
        try:
            text = item.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            managed_lines.append(text)
    existing_text = ""
    if authorized_keys.exists():
        try:
            existing_text = authorized_keys.read_text(encoding="utf-8")
        except OSError:
            existing_text = ""
    begin_marker = "# BEGIN BEAGLE USB TUNNELS"
    end_marker = "# END BEAGLE USB TUNNELS"
    if begin_marker in existing_text and end_marker in existing_text:
        prefix, _, remainder = existing_text.partition(begin_marker)
        _, _, suffix = remainder.partition(end_marker)
        existing_text = prefix.rstrip("\n")
        suffix = suffix.lstrip("\n")
        if suffix:
            existing_text = (existing_text + "\n" + suffix).strip("\n")
    else:
        existing_text = existing_text.strip("\n")
    with authorized_keys.open("w", encoding="utf-8") as handle:
        if existing_text:
            handle.write(existing_text.rstrip("\n") + "\n")
        if managed_lines:
            handle.write(begin_marker + "\n")
            for line in managed_lines:
                handle.write(line + "\n")
            handle.write(end_marker + "\n")
    os.chmod(ssh_dir, 0o700)
    os.chmod(authorized_keys, 0o600)
    os.chmod(snippet_path, 0o600)
    for path in (tunnel_home, ssh_dir, auth_dir, authorized_keys, snippet_path):
        try:
            os.chown(path, user_info.pw_uid, user_info.pw_gid)
        except OSError:
            pass


def ensure_vm_secret(vm: VmSummary) -> dict[str, Any]:
    existing = load_vm_secret(vm.node, vm.vmid)
    if existing:
        changed = False
        if not str(existing.get("sunshine_username", "")).strip():
            existing["sunshine_username"] = f"sunshine-vm{vm.vmid}"
            changed = True
        if not str(existing.get("sunshine_password", "")).strip():
            existing["sunshine_password"] = random_secret(26)
            changed = True
        if not str(existing.get("sunshine_pin", "")).strip():
            existing["sunshine_pin"] = random_pin()
            changed = True
        if not str(existing.get("thinclient_password", "")).strip():
            existing["thinclient_password"] = random_secret(22)
            changed = True
        if not str(existing.get("usb_tunnel_public_key", "")).strip() or not str(existing.get("usb_tunnel_private_key", "")).strip():
            private_key, public_key = generate_ssh_keypair(f"beagle-vm{vm.vmid}-usb")
            existing["usb_tunnel_private_key"] = private_key
            existing["usb_tunnel_public_key"] = public_key
            changed = True
        if int(existing.get("usb_tunnel_port", 0) or 0) <= 0:
            existing["usb_tunnel_port"] = default_usb_tunnel_port(vm.vmid)
            changed = True
        secret = save_vm_secret(vm.node, vm.vmid, existing) if changed else existing
        sync_usb_tunnel_authorized_key(vm, secret)
        return secret
    private_key, public_key = generate_ssh_keypair(f"beagle-vm{vm.vmid}-usb")
    secret = save_vm_secret(
        vm.node,
        vm.vmid,
        {
            "sunshine_username": f"sunshine-vm{vm.vmid}",
            "sunshine_password": random_secret(26),
            "sunshine_pin": random_pin(),
            "thinclient_password": random_secret(22),
            "sunshine_pinned_pubkey": "",
            "usb_tunnel_port": default_usb_tunnel_port(vm.vmid),
            "usb_tunnel_private_key": private_key,
            "usb_tunnel_public_key": public_key,
        },
    )
    sync_usb_tunnel_authorized_key(vm, secret)
    return secret


def manager_pinned_pubkey() -> str:
    if not MANAGER_CERT_FILE.is_file():
        return ""
    try:
        pubkey = subprocess.run(
            ["openssl", "x509", "-in", str(MANAGER_CERT_FILE), "-pubkey", "-noout"],
            check=True,
            capture_output=True,
            text=False,
        ).stdout
        der = subprocess.run(
            ["openssl", "pkey", "-pubin", "-outform", "der"],
            check=True,
            input=pubkey,
            capture_output=True,
            text=False,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""
    digest = hashlib.sha256(der).digest()
    return "sha256//" + base64.b64encode(digest).decode("ascii")


MANAGER_PINNED_PUBKEY = manager_pinned_pubkey()


def fetch_https_pinned_pubkey(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    host = str(parsed.hostname or "").strip()
    if not host:
        return ""
    port = parsed.port or 443
    script = (
        "set -euo pipefail; "
        f"openssl s_client -connect {shlex.quote(host)}:{int(port)} -servername {shlex.quote(host)} </dev/null 2>/dev/null "
        "| openssl x509 -pubkey -noout "
        "| openssl pkey -pubin -outform der 2>/dev/null "
        "| openssl dgst -sha256 -binary | base64"
    )
    try:
        output = subprocess.run(["bash", "-lc", script], check=True, capture_output=True, text=True).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""
    return f"sha256//{output}" if output else ""


def guest_exec_text(vmid: int, script: str) -> tuple[int, str, str]:
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    runner = (
        "set -euo pipefail\n"
        "tmp_script=$(mktemp /tmp/beagle-guest-XXXXXX.sh)\n"
        "tmp_b64=$(mktemp /tmp/beagle-guest-XXXXXX.b64)\n"
        "cleanup() { rm -f \"$tmp_script\" \"$tmp_b64\"; }\n"
        "trap cleanup EXIT\n"
        "cat > \"$tmp_b64\" <<'__BEAGLE_B64__'\n"
        f"{encoded}\n"
        "__BEAGLE_B64__\n"
        "base64 -d \"$tmp_b64\" > \"$tmp_script\"\n"
        "chmod +x \"$tmp_script\"\n"
        "\"$tmp_script\"\n"
    )
    try:
        result = subprocess.run(
            ["qm", "guest", "exec", str(vmid), "--", "bash", "-lc", runner],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        output = ""
        if isinstance(exc, subprocess.CalledProcessError):
            output = exc.stdout or exc.stderr or ""
        return 1, "", output.strip()

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return 1, "", (result.stdout or result.stderr or "").strip()

    exitcode = int(payload.get("exitcode", 0) or 0)
    stdout = str(payload.get("out-data", "") or "").strip()
    stderr = str(payload.get("err-data", "") or "").strip()
    return exitcode, stdout, stderr


def sunshine_guest_user(vm: VmSummary, config: dict[str, Any] | None = None) -> str:
    vm_config = config if isinstance(config, dict) else get_vm_config(vm.node, vm.vmid)
    meta = parse_description_meta(vm_config.get("description", ""))
    return str(meta.get("sunshine-guest-user", "")).strip() or "dennis"


def register_moonlight_certificate_on_vm(vm: VmSummary, client_cert_pem: str, *, device_name: str) -> dict[str, Any]:
    config = get_vm_config(vm.node, vm.vmid)
    guest_user = sunshine_guest_user(vm, config)
    cert_b64 = base64.b64encode(client_cert_pem.encode("utf-8")).decode("ascii")
    device_name = safe_slug(device_name or f"beagle-vm{vm.vmid}-client", f"beagle-vm{vm.vmid}-client")
    script = f"""#!/usr/bin/env bash
set -euo pipefail

guest_user={shlex.quote(guest_user)}
device_name={shlex.quote(device_name)}
state_file="/home/$guest_user/.config/sunshine/sunshine_state.json"
cert_file="$(mktemp /tmp/beagle-cert-XXXXXX.pem)"
trap 'rm -f "$cert_file"' EXIT
cat > "$cert_file.b64" <<'__BEAGLE_CERT__'
{cert_b64}
__BEAGLE_CERT__
base64 -d "$cert_file.b64" > "$cert_file"
rm -f "$cert_file.b64"

python3 - "$state_file" "$device_name" "$cert_file" <<'PY'
import json
import sys
import uuid
from pathlib import Path

state_path = Path(sys.argv[1])
device_name = sys.argv[2]
cert_path = Path(sys.argv[3])

if not state_path.exists():
    raise SystemExit(f"sunshine state file missing: {{state_path}}")

cert = cert_path.read_text(encoding="utf-8")
state = json.loads(state_path.read_text(encoding="utf-8"))
root = state.setdefault("root", {{}})
named = root.setdefault("named_devices", [])

for entry in named:
    if entry.get("cert") == cert:
        entry["name"] = device_name
        state_path.write_text(json.dumps(state, indent=4) + "\\n", encoding="utf-8")
        print("updated-existing")
        raise SystemExit(0)

named.append({{
    "name": device_name,
    "cert": cert,
    "uuid": str(uuid.uuid4()).upper(),
}})
state_path.write_text(json.dumps(state, indent=4) + "\\n", encoding="utf-8")
print("registered-new")
PY

systemctl restart beagle-sunshine.service >/dev/null 2>&1 || true
sleep 2
"""
    exitcode, stdout, stderr = guest_exec_text(vm.vmid, script)
    return {
        "ok": exitcode == 0,
        "guest_user": guest_user,
        "exitcode": exitcode,
        "stdout": stdout,
        "stderr": stderr,
    }


def fetch_sunshine_server_identity(vm: VmSummary, guest_user: str) -> dict[str, Any]:
    state_file = f"/home/{guest_user}/.config/sunshine/sunshine_state.json"
    cert_file = f"/home/{guest_user}/.config/sunshine/credentials/cacert.pem"
    conf_file = f"/home/{guest_user}/.config/sunshine/sunshine.conf"
    script = f"""#!/usr/bin/env bash
set -euo pipefail

python3 - {shlex.quote(state_file)} {shlex.quote(cert_file)} {shlex.quote(conf_file)} <<'PY'
import json
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
cert_path = Path(sys.argv[2])
conf_path = Path(sys.argv[3])

payload = {{
    "uniqueid": "",
    "server_cert_pem": "",
    "sunshine_name": "",
    "stream_port": "",
}}

if state_path.exists():
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        payload["uniqueid"] = str(((state.get("root") or {{}}).get("uniqueid") or "")).strip()
    except Exception:
        pass

if cert_path.exists():
    try:
        payload["server_cert_pem"] = cert_path.read_text(encoding="utf-8")
    except Exception:
        pass

if conf_path.exists():
    try:
        for raw_line in conf_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key == "sunshine_name":
                payload["sunshine_name"] = value
            elif key == "port":
                payload["stream_port"] = value
    except Exception:
        pass

print(json.dumps(payload))
PY
"""
    exitcode, stdout, stderr = guest_exec_text(vm.vmid, script)
    if exitcode != 0:
        return {
            "ok": False,
            "exitcode": exitcode,
            "stdout": stdout,
            "stderr": stderr,
            "uniqueid": "",
            "server_cert_pem": "",
            "sunshine_name": "",
            "stream_port": "",
        }
    try:
        payload = json.loads((stdout or "{}").strip() or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "ok": True,
        "exitcode": exitcode,
        "stdout": stdout,
        "stderr": stderr,
        "uniqueid": str(payload.get("uniqueid", "") or "").strip(),
        "server_cert_pem": str(payload.get("server_cert_pem", "") or ""),
        "sunshine_name": str(payload.get("sunshine_name", "") or "").strip(),
        "stream_port": str(payload.get("stream_port", "") or "").strip(),
    }


def internal_sunshine_api_url(vm: VmSummary, profile: dict[str, Any]) -> str:
    public_stream = profile.get("public_stream") if isinstance(profile.get("public_stream"), dict) else None
    guest_ip = str(profile.get("guest_ip", "") or "").strip()
    if public_stream:
        guest_ip = str(public_stream.get("guest_ip", "") or guest_ip).strip()
        ports = public_stream.get("ports", {}) if isinstance(public_stream.get("ports"), dict) else {}
        api_port = ports.get("sunshine_api_port")
        if guest_ip and api_port:
            return f"https://{guest_ip}:{int(api_port)}"
    base_url = str(profile.get("sunshine_api_url", "") or "")
    if guest_ip and base_url:
        parsed = urlparse(base_url)
        if parsed.scheme and parsed.port:
            return urlunparse(parsed._replace(netloc=f"{guest_ip}:{parsed.port}"))
    return base_url


def enrollment_token_path(token: str) -> Path:
    return enrollment_tokens_dir() / f"{hashlib.sha256(token.encode('utf-8')).hexdigest()}.json"


def sunshine_access_token_path(token: str) -> Path:
    return sunshine_access_tokens_dir() / f"{hashlib.sha256(token.encode('utf-8')).hexdigest()}.json"


def issue_enrollment_token(vm: VmSummary) -> tuple[str, dict[str, Any]]:
    record = ensure_vm_secret(vm)
    token = secrets.token_urlsafe(32)
    payload = {
        "vmid": vm.vmid,
        "node": vm.node,
        "profile_name": f"vm-{vm.vmid}",
        "expires_at": datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + ENROLLMENT_TOKEN_TTL_SECONDS, tz=timezone.utc).isoformat(),
        "issued_at": utcnow(),
        "used_at": "",
        "thinclient_password": str(record.get("thinclient_password", "")),
    }
    write_json_file(enrollment_token_path(token), payload)
    return token, payload


def load_enrollment_token(token: str) -> dict[str, Any] | None:
    payload = load_json_file(enrollment_token_path(token), None)
    return payload if isinstance(payload, dict) else None


def issue_sunshine_access_token(vm: VmSummary) -> tuple[str, dict[str, Any]]:
    token = secrets.token_urlsafe(32)
    payload = {
        "vmid": vm.vmid,
        "node": vm.node,
        "issued_at": utcnow(),
        "expires_at": datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + SUNSHINE_ACCESS_TOKEN_TTL_SECONDS, tz=timezone.utc).isoformat(),
    }
    write_json_file(sunshine_access_token_path(token), payload)
    return token, payload


def load_sunshine_access_token(token: str) -> dict[str, Any] | None:
    payload = load_json_file(sunshine_access_token_path(token), None)
    return payload if isinstance(payload, dict) else None


def mark_enrollment_token_used(token: str, payload: dict[str, Any], *, endpoint_id: str) -> None:
    clean = dict(payload)
    clean["used_at"] = utcnow()
    clean["endpoint_id"] = endpoint_id
    write_json_file(enrollment_token_path(token), clean)


def enrollment_token_is_valid(payload: dict[str, Any] | None, *, endpoint_id: str = "") -> bool:
    if not isinstance(payload, dict):
        return False
    expires_at = parse_utc_timestamp(str(payload.get("expires_at", "")))
    if expires_at is None:
        return False
    if expires_at <= datetime.now(timezone.utc):
        return False
    used_at = str(payload.get("used_at", "")).strip()
    if not used_at:
        return True
    if endpoint_id and str(payload.get("endpoint_id", "")).strip() == endpoint_id:
        return True
    return False


def sunshine_access_token_is_valid(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    expires_at = parse_utc_timestamp(str(payload.get("expires_at", "")))
    if expires_at is None:
        return False
    return expires_at > datetime.now(timezone.utc)


def endpoint_token_path(token: str) -> Path:
    return endpoint_tokens_dir() / f"{hashlib.sha256(token.encode('utf-8')).hexdigest()}.json"


def store_endpoint_token(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    clean = dict(payload)
    clean["token_issued_at"] = utcnow()
    write_json_file(endpoint_token_path(token), clean)
    return clean


def load_endpoint_token(token: str) -> dict[str, Any] | None:
    payload = load_json_file(endpoint_token_path(token), None)
    return payload if isinstance(payload, dict) else None


def sunshine_proxy_ticket_url(token: str) -> str:
    return f"{PUBLIC_MANAGER_URL}/api/v1/public/sunshine/{token}/"


def proxy_sunshine_request(vm: VmSummary, *, request_path: str, query: str, method: str, body: bytes | None, request_headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    profile = build_profile(vm)
    base_url = internal_sunshine_api_url(vm, profile).rstrip("/")
    if not base_url:
        raise RuntimeError("missing sunshine api url")
    secret = ensure_vm_secret(vm)
    sunshine_user = str(secret.get("sunshine_username", "") or "")
    sunshine_password = str(secret.get("sunshine_password", "") or "")
    pinned_pubkey = str(secret.get("sunshine_pinned_pubkey", "") or "")
    if not sunshine_user or not sunshine_password:
        raise RuntimeError("missing sunshine credentials")

    relative = "/" + str(request_path or "").lstrip("/")
    target_url = f"{base_url}{relative}"
    if query:
        target_url = f"{target_url}?{query}"

    header_file = tempfile.NamedTemporaryFile(prefix="beagle-sunshine-hdr-", delete=False)
    body_file = tempfile.NamedTemporaryFile(prefix="beagle-sunshine-body-", delete=False)
    header_file.close()
    body_file.close()
    input_name = ""
    try:
        command = [
            "curl",
            "-sS",
            "-D",
            header_file.name,
            "-o",
            body_file.name,
            "-X",
            method.upper(),
            "-u",
            f"{sunshine_user}:{sunshine_password}",
            "-k",
            "--connect-timeout",
            "5",
            "--max-time",
            "30",
        ]
        if pinned_pubkey:
            command.extend(["--pinnedpubkey", pinned_pubkey])
        for key in ("Content-Type", "Accept"):
            value = str(request_headers.get(key, "") or "").strip()
            if value:
                command.extend(["-H", f"{key}: {value}"])
        if body is not None:
            input_file = tempfile.NamedTemporaryFile(prefix="beagle-sunshine-in-", delete=False)
            input_file.write(body)
            input_file.flush()
            input_name = input_file.name
            input_file.close()
            command.extend(["--data-binary", f"@{input_name}"])
        command.append(target_url)
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "curl failed").strip())

        raw_headers = Path(header_file.name).read_text(encoding="utf-8", errors="replace")
        raw_body = Path(body_file.name).read_bytes()
        blocks = [block for block in re.split(r"\r?\n\r?\n", raw_headers.strip()) if block.strip()]
        header_block = blocks[-1] if blocks else ""
        lines = [line for line in re.split(r"\r?\n", header_block) if line.strip()]
        if not lines or not lines[0].startswith("HTTP/"):
            raise RuntimeError("invalid sunshine proxy response")
        status_code = int(lines[0].split()[1])
        response_headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            response_headers[key.strip()] = value.strip()
        return status_code, response_headers, raw_body
    finally:
        for path in (header_file.name, body_file.name, input_name):
            if path:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass


DEFAULT_CREDENTIALS = load_shell_env_file(CREDENTIALS_ENV_FILE)
DEFAULT_PROXMOX_USERNAME = (
    DEFAULT_CREDENTIALS.get("PVE_THIN_CLIENT_DEFAULT_PROXMOX_USERNAME")
    or DEFAULT_CREDENTIALS.get("PVE_DCV_PROXMOX_USERNAME")
    or ""
).strip()
DEFAULT_PROXMOX_PASSWORD = (
    DEFAULT_CREDENTIALS.get("PVE_THIN_CLIENT_DEFAULT_PROXMOX_PASSWORD")
    or DEFAULT_CREDENTIALS.get("PVE_DCV_PROXMOX_PASSWORD")
    or ""
).strip()
DEFAULT_PROXMOX_TOKEN = (
    DEFAULT_CREDENTIALS.get("PVE_THIN_CLIENT_DEFAULT_PROXMOX_TOKEN")
    or DEFAULT_CREDENTIALS.get("PVE_DCV_PROXMOX_TOKEN")
    or ""
).strip()


def public_streams_file() -> Path:
    return EFFECTIVE_DATA_DIR / "public-streams.json"


def load_public_streams() -> dict[str, int]:
    payload = load_json_file(public_streams_file(), {})
    if not isinstance(payload, dict):
        return {}
    streams: dict[str, int] = {}
    for key, value in payload.items():
        try:
            streams[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return streams


def save_public_streams(payload: dict[str, int]) -> None:
    public_streams_file().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def public_stream_key(node: str, vmid: int) -> str:
    return f"{safe_slug(node, 'node')}:{int(vmid)}"


def allocate_public_stream_base_port(node: str, vmid: int) -> int | None:
    if not PUBLIC_STREAM_HOST:
        return None
    mappings = load_public_streams()
    key = public_stream_key(node, vmid)
    existing = mappings.get(key)
    if existing is not None:
        return int(existing)
    used = {int(value) for value in mappings.values()}
    upper_bound = PUBLIC_STREAM_BASE_PORT + (PUBLIC_STREAM_PORT_STEP * PUBLIC_STREAM_PORT_COUNT)
    for candidate in range(PUBLIC_STREAM_BASE_PORT, upper_bound, PUBLIC_STREAM_PORT_STEP):
        if candidate in used:
            continue
        mappings[key] = candidate
        save_public_streams(mappings)
        return candidate
    return None


def stream_ports(base_port: int) -> dict[str, int]:
    base = int(base_port)
    return {
        "moonlight_port": base,
        "sunshine_api_port": base + 1,
        "https_port": base + 1,
        "rtsp_port": base + 21,
    }


def shell_double_quoted(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("`", "\\`")
    )


def patch_installer_defaults(script_text: str, preset_name: str, preset_b64: str, installer_iso_url: str) -> str:
    replacements = {
        r'^PVE_THIN_CLIENT_PRESET_NAME="\$\{PVE_THIN_CLIENT_PRESET_NAME:-[^"]*}"$':
            f'PVE_THIN_CLIENT_PRESET_NAME="${{PVE_THIN_CLIENT_PRESET_NAME:-{shell_double_quoted(preset_name)}}}"',
        r'^PVE_THIN_CLIENT_PRESET_B64="\$\{PVE_THIN_CLIENT_PRESET_B64:-[^"]*}"$':
            f'PVE_THIN_CLIENT_PRESET_B64="${{PVE_THIN_CLIENT_PRESET_B64:-{shell_double_quoted(preset_b64)}}}"',
        r'^RELEASE_ISO_URL="\$\{RELEASE_ISO_URL:-[^"]*}"$':
            f'RELEASE_ISO_URL="${{RELEASE_ISO_URL:-{shell_double_quoted(installer_iso_url)}}}"',
        r'^BOOTSTRAP_DISABLE_CACHE="\$\{PVE_DCV_BOOTSTRAP_DISABLE_CACHE:-[^"]*}"$':
            'BOOTSTRAP_DISABLE_CACHE="${PVE_DCV_BOOTSTRAP_DISABLE_CACHE:-1}"',
    }
    updated = script_text
    for pattern, replacement in replacements.items():
        updated, count = re.subn(pattern, replacement, updated, count=1, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(f"failed to patch installer template for pattern: {pattern}")
    return updated


def patch_windows_installer_defaults(script_text: str, preset_name: str, preset_b64: str, installer_iso_url: str) -> str:
    return (
        script_text
        .replace("__BEAGLE_DEFAULT_RELEASE_ISO_URL__", str(installer_iso_url or ""))
        .replace("__BEAGLE_DEFAULT_PRESET_NAME__", str(preset_name or ""))
        .replace("__BEAGLE_DEFAULT_PRESET_B64__", str(preset_b64 or ""))
    )


def encode_installer_preset(preset: dict[str, Any]) -> str:
    lines = ["# Auto-generated Beagle OS VM preset"]
    for key in sorted(preset):
        lines.append(f"{key}={shlex.quote(str(preset.get(key, '')))}")
    payload = "\n".join(lines) + "\n"
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def installer_prep_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "installer-prep"
    path.mkdir(parents=True, exist_ok=True)
    return path


def installer_prep_path(node: str, vmid: int) -> Path:
    safe_node = safe_slug(node, "unknown")
    return installer_prep_dir() / f"{safe_node}-{int(vmid)}.json"


def installer_prep_log_path(node: str, vmid: int) -> Path:
    safe_node = safe_slug(node, "unknown")
    return installer_prep_dir() / f"{safe_node}-{int(vmid)}.log"


def load_installer_prep_state(node: str, vmid: int) -> dict[str, Any] | None:
    payload = load_json_file(installer_prep_path(node, vmid), None)
    return payload if isinstance(payload, dict) else None


def guest_exec_out_data(vmid: int, command: str) -> str:
    payload = run_json(["qm", "guest", "exec", str(vmid), "--", "bash", "-lc", command])
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("out-data", "") or "")


def guest_exec_payload(vmid: int, command: str, *, timeout_seconds: int = 20) -> dict[str, Any]:
    payload = run_json(["qm", "guest", "exec", str(vmid), "--timeout", str(int(timeout_seconds)), "--", "bash", "-lc", command], timeout=timeout_seconds + 5)
    return payload if isinstance(payload, dict) else {}


def parse_usbip_port_output(output: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in str(output or "").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        port_match = re.match(r"Port (\d+):", line.strip())
        if port_match:
            if current:
                items.append(current)
            current = {"port": int(port_match.group(1))}
            continue
        if current is None:
            continue
        if "Remote Bus ID" in line:
            current["busid"] = line.split("Remote Bus ID:", 1)[1].strip()
        elif "Remote bus/dev" in line:
            current["remote_device"] = line.split("Remote bus/dev", 1)[1].strip(": ").strip()
        elif "Remote Bus ID" not in line and "-> usbip" in line:
            current["device"] = line.strip()
            match = re.search(r"/([^/\s]+)\s*$", line.strip())
            if match and not current.get("busid"):
                current["busid"] = match.group(1)
        elif "1-" in line and "usbip" not in line and not current.get("busid"):
            current["device"] = line.strip()
    if current:
        items.append(current)
    return items


def parse_vhci_status_output(output: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("hub ") or line.startswith("hs  ") is False and line.startswith("ss  ") is False:
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        local_busid = parts[-1]
        if local_busid in {"0-0", "000000"}:
            continue
        try:
            port = int(parts[1])
        except ValueError:
            port = 0
        items.append(
            {
                "port": port,
                "local_busid": local_busid,
                "device": line,
            }
        )
    return items


def guest_usb_attachment_state(vmid: int) -> dict[str, Any]:
    output = guest_exec_out_data(vmid, "command -v usbip >/dev/null 2>&1 && usbip port || true")
    attached = parse_usbip_port_output(output)
    vhci_output = guest_exec_out_data(vmid, "cat /sys/devices/platform/vhci_hcd.0/status 2>/dev/null || true")
    vhci_attached = parse_vhci_status_output(vhci_output)
    return {
        "attached": attached if attached else vhci_attached,
        "attached_count": len(attached if attached else vhci_attached),
        "usbip_available": bool(guest_exec_out_data(vmid, "command -v usbip >/dev/null 2>&1 && echo yes || true").strip()),
        "vhci_attached": vhci_attached,
    }


def wait_for_guest_usb_attachment(vmid: int, busid: str, *, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    last_state: dict[str, Any] = guest_usb_attachment_state(vmid)
    expected = str(busid).strip()
    while time.monotonic() < deadline:
        attached = last_state.get("attached", []) if isinstance(last_state, dict) else []
        if any(str(item.get("busid", "")).strip() == expected for item in attached):
            return last_state
        vhci_attached = last_state.get("vhci_attached", []) if isinstance(last_state, dict) else []
        if vhci_attached:
            return last_state
        time.sleep(1)
        last_state = guest_usb_attachment_state(vmid)
    return last_state


def wait_for_action_result(node: str, vmid: int, action_id: str, *, timeout_seconds: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    while time.monotonic() < deadline:
        payload = load_action_result(node, vmid)
        if isinstance(payload, dict) and str(payload.get("action_id", "")).strip() == action_id:
            return payload
        time.sleep(1)
    return None


def build_vm_usb_state(vm: VmSummary, report: dict[str, Any] | None = None) -> dict[str, Any]:
    secret = ensure_vm_secret(vm)
    endpoint_payload = report if isinstance(report, dict) else (load_endpoint_report(vm.node, vm.vmid) or {})
    endpoint_summary = summarize_endpoint_report(endpoint_payload)
    guest_state = guest_usb_attachment_state(vm.vmid)
    return {
        "enabled": True,
        "tunnel_host": PUBLIC_SERVER_NAME,
        "attach_host": USB_TUNNEL_ATTACH_HOST,
        "tunnel_user": USB_TUNNEL_SSH_USER,
        "tunnel_port": int(secret.get("usb_tunnel_port", 0) or 0),
        "tunnel_state": endpoint_summary.get("usb_tunnel_state", ""),
        "device_count": endpoint_summary.get("usb_device_count", 0),
        "bound_count": endpoint_summary.get("usb_bound_count", 0),
        "devices": endpoint_summary.get("usb_devices", []),
        "attached": guest_state.get("attached", []),
        "attached_count": guest_state.get("attached_count", 0),
        "guest_usbip_available": guest_state.get("usbip_available", False),
    }


def attach_usb_to_guest(vm: VmSummary, busid: str) -> dict[str, Any]:
    secret = ensure_vm_secret(vm)
    tunnel_port = int(secret.get("usb_tunnel_port", 0) or 0)
    if tunnel_port <= 0:
        raise RuntimeError("missing usb tunnel port")
    escaped_busid = shlex.quote(str(busid))
    command = (
        "set -euo pipefail; "
        "command -v usbip >/dev/null 2>&1 || { echo 'usbip missing in guest' >&2; exit 40; }; "
        "modprobe vhci-hcd >/dev/null 2>&1 || true; "
        f"if usbip port 2>/dev/null | grep -Fq 'Remote Bus ID: {str(busid)}'; then "
        "  usbip port; "
        "  exit 0; "
        "fi; "
        "ready=0; "
        "for _attempt in $(seq 1 12); do "
        f"  if timeout 2 bash -lc 'exec 3<>/dev/tcp/{USB_TUNNEL_ATTACH_HOST}/{tunnel_port}' >/dev/null 2>&1; then "
        "    ready=1; "
        "    break; "
        "  fi; "
        "  sleep 1; "
        "done; "
        "[ \"$ready\" = \"1\" ] || { echo 'usb tunnel not reachable from guest' >&2; exit 41; }; "
        f"usbip --tcp-port {tunnel_port} attach -r {shlex.quote(USB_TUNNEL_ATTACH_HOST)} -b {escaped_busid}; "
        "usbip port"
    )
    payload = guest_exec_payload(vm.vmid, command, timeout_seconds=30)
    output = str(payload.get("out-data", "") or "")
    error_output = str(payload.get("err-data", "") or "").strip()
    exit_code = int(payload.get("exitcode", 1) or 1)
    guest_state = wait_for_guest_usb_attachment(vm.vmid, busid, timeout_seconds=8)
    attached = guest_state.get("attached", []) if isinstance(guest_state, dict) else []
    vhci_attached = guest_state.get("vhci_attached", []) if isinstance(guest_state, dict) else []
    if exit_code != 0 and not attached and not vhci_attached:
        raise RuntimeError(error_output or output or "usb attach failed")
    if not attached and not vhci_attached:
        raise RuntimeError(error_output or "usb attach completed but guest state did not confirm attachment")
    return {
        "busid": busid,
        "tunnel_port": tunnel_port,
        "attach_host": USB_TUNNEL_ATTACH_HOST,
        "attached": attached or vhci_attached or parse_usbip_port_output(output),
        "guest_state": guest_state,
        "raw_output": output,
        "raw_error": error_output,
    }


def detach_usb_from_guest(vm: VmSummary, *, port: int | None = None, busid: str = "") -> dict[str, Any]:
    guest_state = guest_usb_attachment_state(vm.vmid)
    attached = guest_state.get("attached", []) if isinstance(guest_state, dict) else []
    detach_port = int(port) if port is not None else None
    if detach_port is None and busid:
        for item in attached:
            if str(item.get("busid", "")).strip() == str(busid).strip():
                detach_port = int(item.get("port", 0) or 0)
                break
    if detach_port is None or detach_port < 0:
        raise RuntimeError("usb device is not attached in guest")
    command = f"set -euo pipefail; usbip detach -p {int(detach_port)}; usbip port || true"
    payload = guest_exec_payload(vm.vmid, command, timeout_seconds=15)
    output = str(payload.get("out-data", "") or "")
    error_output = str(payload.get("err-data", "") or "").strip()
    exit_code = int(payload.get("exitcode", 1) or 1)
    post_state = guest_usb_attachment_state(vm.vmid)
    remaining = post_state.get("attached", []) if isinstance(post_state, dict) else []
    if busid:
        still_attached = any(str(item.get("busid", "")).strip() == str(busid).strip() for item in remaining)
    else:
        still_attached = any(int(item.get("port", -1) or -1) == int(detach_port) for item in remaining)
    if exit_code != 0 and still_attached:
        raise RuntimeError(error_output or output or "usb detach failed")
    return {
        "detached_port": int(detach_port),
        "busid": busid,
        "attached": remaining or parse_usbip_port_output(output),
        "raw_output": output,
        "raw_error": error_output,
    }


def quick_sunshine_status(vmid: int) -> dict[str, Any]:
    output = guest_exec_out_data(
        vmid,
        "binary=0; service=0; process=0; "
        "command -v sunshine >/dev/null 2>&1 && binary=1; "
        "(systemctl is-active sunshine >/dev/null 2>&1 || systemctl is-active beagle-sunshine.service >/dev/null 2>&1) && service=1; "
        "pgrep -x sunshine >/dev/null 2>&1 && process=1; "
        "printf '{\"binary\":%s,\"service\":%s,\"process\":%s}\\n' \"$binary\" \"$service\" \"$process\"",
    )
    text = output.strip().splitlines()[-1] if output.strip() else ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = {"binary": 0, "service": 0, "process": 0}
    return {
        "binary": bool(payload.get("binary")),
        "service": bool(payload.get("service")),
        "process": bool(payload.get("process")),
    }


def default_installer_prep_state(vm: VmSummary, sunshine_status: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = build_profile(vm)
    quick = sunshine_status if isinstance(sunshine_status, dict) else quick_sunshine_status(vm.vmid)
    eligible = bool(profile.get("installer_target_eligible"))
    ready = eligible and bool(quick.get("binary")) and bool(quick.get("service")) and bool(profile.get("stream_host")) and bool(profile.get("moonlight_port"))
    if not eligible:
        status = "unsupported"
        phase = "target"
        progress = 100
        message = str(profile.get("installer_target_message") or "Diese VM ist kein geeignetes Sunshine-Streaming-Ziel.")
    elif ready:
        status = "ready"
        phase = "complete"
        progress = 100
        message = "Sunshine ist aktiv. Das VM-spezifische USB-Installer-Skript ist sofort verfuegbar."
    else:
        status = "idle"
        phase = "inspect"
        progress = 0
        message = "Download startet zuerst die Sunshine-Pruefung und die Stream-Vorbereitung fuer diese VM."
    return {
        "vmid": vm.vmid,
        "node": vm.node,
        "status": status,
        "phase": phase,
        "progress": progress,
        "message": message,
        "updated_at": utcnow(),
        "installer_url": f"/beagle-api/api/v1/vms/{vm.vmid}/installer.sh",
        "live_usb_url": f"/beagle-api/api/v1/vms/{vm.vmid}/live-usb.sh",
        "installer_windows_url": f"/beagle-api/api/v1/vms/{vm.vmid}/installer.ps1",
        "installer_iso_url": str(profile.get("installer_iso_url") or public_installer_iso_url()),
        "stream_host": str(profile.get("stream_host", "") or ""),
        "moonlight_port": str(profile.get("moonlight_port", "") or ""),
        "sunshine_api_url": str(profile.get("sunshine_api_url", "") or ""),
        "installer_target_eligible": eligible,
        "installer_target_status": "ready" if ready else ("preparing" if eligible else "unsupported"),
        "sunshine_status": {
            "binary": bool(quick.get("binary")),
            "service": bool(quick.get("service")),
            "process": bool(quick.get("process")),
        },
        "ready": ready,
    }


def summarize_installer_prep_state(vm: VmSummary, state: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = build_profile(vm)
    payload = dict(state) if isinstance(state, dict) else default_installer_prep_state(vm)
    quick = quick_sunshine_status(vm.vmid)
    payload["sunshine_status"] = {
        "binary": bool(quick.get("binary")),
        "service": bool(quick.get("service")),
        "process": bool(quick.get("process")),
    }
    payload["ready"] = str(payload.get("status", "")).strip().lower() == "ready"
    payload.setdefault("vmid", vm.vmid)
    payload.setdefault("node", vm.node)
    payload["installer_url"] = str(payload.get("installer_url") or f"/beagle-api/api/v1/vms/{vm.vmid}/installer.sh")
    payload["live_usb_url"] = str(payload.get("live_usb_url") or f"/beagle-api/api/v1/vms/{vm.vmid}/live-usb.sh")
    payload["installer_windows_url"] = str(payload.get("installer_windows_url") or f"/beagle-api/api/v1/vms/{vm.vmid}/installer.ps1")
    payload["installer_iso_url"] = str(payload.get("installer_iso_url") or profile.get("installer_iso_url") or public_installer_iso_url())
    payload["stream_host"] = str(payload.get("stream_host") or profile.get("stream_host") or "")
    payload["moonlight_port"] = str(payload.get("moonlight_port") or profile.get("moonlight_port") or "")
    payload["sunshine_api_url"] = str(payload.get("sunshine_api_url") or profile.get("sunshine_api_url") or "")
    payload["installer_target_eligible"] = bool(payload.get("installer_target_eligible", profile.get("installer_target_eligible")))
    payload["installer_target_status"] = "ready" if payload["ready"] else ("preparing" if payload["installer_target_eligible"] else "unsupported")
    return payload


def installer_prep_running(state: dict[str, Any] | None) -> bool:
    if not isinstance(state, dict):
        return False
    if str(state.get("status", "")).strip().lower() != "running":
        return False
    age = timestamp_age_seconds(str(state.get("updated_at", "")))
    return age is None or age < 900


def start_installer_prep(vm: VmSummary) -> dict[str, Any]:
    state_path = installer_prep_path(vm.node, vm.vmid)
    log_path = installer_prep_log_path(vm.node, vm.vmid)
    state = load_installer_prep_state(vm.node, vm.vmid)
    default_state = default_installer_prep_state(vm)
    vm_secret = ensure_vm_secret(vm)
    if not bool(default_state.get("installer_target_eligible")):
        return summarize_installer_prep_state(vm, default_state)
    if installer_prep_running(state):
        return summarize_installer_prep_state(vm, state)
    if not INSTALLER_PREP_SCRIPT_FILE.is_file():
        raise FileNotFoundError(f"installer prep script missing: {INSTALLER_PREP_SCRIPT_FILE}")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("ab")
    env = os.environ.copy()
    env.update(
        {
            "VMID": str(vm.vmid),
            "NODE": vm.node,
            "BEAGLE_INSTALLER_PREP_STATE_FILE": str(state_path),
            "BEAGLE_SUNSHINE_DEFAULT_USER": str(vm_secret.get("sunshine_username", "")),
            "BEAGLE_SUNSHINE_DEFAULT_PASSWORD": str(vm_secret.get("sunshine_password", "")),
            "BEAGLE_SUNSHINE_DEFAULT_PIN": str(vm_secret.get("sunshine_pin", "")),
        }
    )
    try:
        subprocess.Popen(
            [str(INSTALLER_PREP_SCRIPT_FILE), "--vmid", str(vm.vmid), "--node", vm.node],
            cwd=str(ROOT_DIR),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log_handle.close()
    bootstrap_state = summarize_installer_prep_state(
        vm,
        {
            "vmid": vm.vmid,
            "node": vm.node,
            "status": "running",
            "phase": "queue",
            "progress": 1,
            "message": f"Sunshine-Pruefung fuer VM {vm.vmid} wurde gestartet.",
            "requested_at": utcnow(),
            "started_at": utcnow(),
            "updated_at": utcnow(),
        },
    )
    state_path.write_text(json.dumps(bootstrap_state, indent=2) + "\n", encoding="utf-8")
    return bootstrap_state


def policy_path(name: str) -> Path:
    return policies_dir() / f"{safe_slug(name, 'policy')}.json"


def load_action_queue(node: str, vmid: int) -> list[dict[str, Any]]:
    payload = load_json_file(action_queue_path(node, vmid), [])
    return payload if isinstance(payload, list) else []


def save_action_queue(node: str, vmid: int, queue: list[dict[str, Any]]) -> None:
    action_queue_path(node, vmid).write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")


def load_action_result(node: str, vmid: int) -> dict[str, Any] | None:
    payload = load_json_file(action_result_path(node, vmid), None)
    return payload if isinstance(payload, dict) else None


def store_action_result(node: str, vmid: int, payload: dict[str, Any]) -> None:
    action_result_path(node, vmid).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def queue_vm_action(vm: VmSummary, action_name: str, requested_by: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    queue = load_action_queue(vm.node, vm.vmid)
    action_id = f"{vm.node}-{vm.vmid}-{int(datetime.now(timezone.utc).timestamp())}-{len(queue) + 1}"
    payload = {
        "action_id": action_id,
        "action": action_name,
        "vmid": vm.vmid,
        "node": vm.node,
        "requested_at": utcnow(),
        "requested_by": requested_by,
    }
    if isinstance(params, dict) and params:
        payload["params"] = params
    queue.append(payload)
    save_action_queue(vm.node, vm.vmid, queue)
    return payload


def queue_bulk_actions(vmids: list[int], action_name: str, requested_by: str) -> list[dict[str, Any]]:
    queued: list[dict[str, Any]] = []
    seen: set[int] = set()
    for vmid in vmids:
        if vmid in seen:
            continue
        seen.add(vmid)
        vm = find_vm(vmid)
        if vm is None:
            continue
        queued.append(queue_vm_action(vm, action_name, requested_by))
    return queued


def dequeue_vm_actions(node: str, vmid: int) -> list[dict[str, Any]]:
    queue = load_action_queue(node, vmid)
    save_action_queue(node, vmid, [])
    return queue


def summarize_action_result(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "action_id": "",
            "action": "",
            "ok": None,
            "message": "",
            "artifact_path": "",
            "stored_artifact_path": "",
            "stored_artifact_bundle_id": "",
            "stored_artifact_download_path": "",
            "stored_artifact_size": 0,
            "requested_at": "",
            "completed_at": "",
        }
    return {
        "action_id": payload.get("action_id", ""),
        "action": payload.get("action", ""),
        "busid": payload.get("busid", ""),
        "ok": payload.get("ok"),
        "message": payload.get("message", ""),
        "artifact_path": payload.get("artifact_path", ""),
        "stored_artifact_path": payload.get("stored_artifact_path", ""),
        "stored_artifact_bundle_id": payload.get("stored_artifact_bundle_id", ""),
        "stored_artifact_download_path": payload.get("stored_artifact_download_path", ""),
        "stored_artifact_size": payload.get("stored_artifact_size", 0),
        "requested_at": payload.get("requested_at", ""),
        "completed_at": payload.get("completed_at", ""),
    }


def list_support_bundle_metadata(*, node: str | None = None, vmid: int | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(support_bundles_dir().glob("*.json")):
        payload = load_json_file(path, None)
        if not isinstance(payload, dict):
            continue
        if node is not None and str(payload.get("node", "")).strip() != str(node).strip():
            continue
        if vmid is not None and int(payload.get("vmid", -1)) != int(vmid):
            continue
        items.append(payload)
    items.sort(key=lambda item: str(item.get("uploaded_at", "")), reverse=True)
    return items


def find_support_bundle_metadata(bundle_id: str) -> dict[str, Any] | None:
    payload = load_json_file(support_bundle_metadata_path(bundle_id), None)
    return payload if isinstance(payload, dict) else None


def store_support_bundle(node: str, vmid: int, action_id: str, filename: str, content: bytes) -> dict[str, Any]:
    safe_node = safe_slug(node, "unknown")
    safe_name = safe_slug(filename, "support-bundle.tar.gz")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    bundle_id = f"{safe_node}-{int(vmid)}-{timestamp}-{safe_slug(action_id, 'action')}"
    archive_path = support_bundle_archive_path(bundle_id, safe_name)
    archive_path.write_bytes(content)
    sha256 = hashlib.sha256(content).hexdigest()
    payload = {
        "bundle_id": bundle_id,
        "node": node,
        "vmid": int(vmid),
        "action_id": action_id,
        "filename": filename,
        "stored_filename": archive_path.name,
        "stored_path": str(archive_path),
        "size": len(content),
        "sha256": sha256,
        "uploaded_at": utcnow(),
        "download_path": f"/api/v1/support-bundles/{bundle_id}/download",
    }
    support_bundle_metadata_path(bundle_id).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def normalize_policy_payload(payload: dict[str, Any], *, policy_name: str | None = None) -> dict[str, Any]:
    name = str(policy_name or payload.get("name", "")).strip()
    if not name:
        raise ValueError("missing policy name")
    selector = payload.get("selector", {})
    if selector is None:
        selector = {}
    if not isinstance(selector, dict):
        raise ValueError("selector must be an object")
    profile = payload.get("profile", {})
    if profile is None:
        profile = {}
    if not isinstance(profile, dict):
        raise ValueError("profile must be an object")
    priority = int(payload.get("priority", 100))
    enabled = bool(payload.get("enabled", True))
    normalized = {
        "name": name,
        "enabled": enabled,
        "priority": priority,
        "selector": {
            "vmid": int(selector["vmid"]) if str(selector.get("vmid", "")).strip() else None,
            "node": str(selector.get("node", "")).strip(),
            "role": str(selector.get("role", "")).strip(),
            "tags_any": [str(item).strip() for item in selector.get("tags_any", []) if str(item).strip()],
            "tags_all": [str(item).strip() for item in selector.get("tags_all", []) if str(item).strip()],
        },
        "profile": {
            "expected_profile_name": str(profile.get("expected_profile_name", "")).strip(),
            "network_mode": str(profile.get("network_mode", "")).strip(),
            "moonlight_app": str(profile.get("moonlight_app", "")).strip(),
            "stream_host": str(profile.get("stream_host", "")).strip(),
            "moonlight_port": str(profile.get("moonlight_port", "")).strip(),
            "sunshine_api_url": str(profile.get("sunshine_api_url", "")).strip(),
            "moonlight_resolution": str(profile.get("moonlight_resolution", "")).strip(),
            "moonlight_fps": str(profile.get("moonlight_fps", "")).strip(),
            "moonlight_bitrate": str(profile.get("moonlight_bitrate", "")).strip(),
            "moonlight_video_codec": str(profile.get("moonlight_video_codec", "")).strip(),
            "moonlight_video_decoder": str(profile.get("moonlight_video_decoder", "")).strip(),
            "moonlight_audio_config": str(profile.get("moonlight_audio_config", "")).strip(),
            "egress_mode": str(profile.get("egress_mode", "")).strip(),
            "egress_type": str(profile.get("egress_type", "")).strip(),
            "egress_interface": str(profile.get("egress_interface", "")).strip(),
            "egress_domains": listify(profile.get("egress_domains", [])),
            "egress_resolvers": listify(profile.get("egress_resolvers", [])),
            "egress_allowed_ips": listify(profile.get("egress_allowed_ips", [])),
            "egress_wg_address": str(profile.get("egress_wg_address", "")).strip(),
            "egress_wg_dns": str(profile.get("egress_wg_dns", "")).strip(),
            "egress_wg_public_key": str(profile.get("egress_wg_public_key", "")).strip(),
            "egress_wg_endpoint": str(profile.get("egress_wg_endpoint", "")).strip(),
            "egress_wg_private_key": str(profile.get("egress_wg_private_key", "")).strip(),
            "egress_wg_preshared_key": str(profile.get("egress_wg_preshared_key", "")).strip(),
            "egress_wg_persistent_keepalive": str(profile.get("egress_wg_persistent_keepalive", "")).strip(),
            "identity_hostname": str(profile.get("identity_hostname", "")).strip(),
            "identity_timezone": str(profile.get("identity_timezone", "")).strip(),
            "identity_locale": str(profile.get("identity_locale", "")).strip(),
            "identity_keymap": str(profile.get("identity_keymap", "")).strip(),
            "identity_chrome_profile": str(profile.get("identity_chrome_profile", "")).strip(),
            "beagle_role": str(profile.get("beagle_role", "")).strip(),
            "assigned_target": {
                "vmid": int(profile.get("assigned_target", {}).get("vmid")) if str(profile.get("assigned_target", {}).get("vmid", "")).strip() else None,
                "node": str(profile.get("assigned_target", {}).get("node", "")).strip(),
            } if isinstance(profile.get("assigned_target"), dict) else None,
        },
        "updated_at": utcnow(),
    }
    return normalized


def save_policy(payload: dict[str, Any], *, policy_name: str | None = None) -> dict[str, Any]:
    normalized = normalize_policy_payload(payload, policy_name=policy_name)
    policy_path(normalized["name"]).write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    return normalized


def load_policy(name: str) -> dict[str, Any] | None:
    payload = load_json_file(policy_path(name), None)
    return payload if isinstance(payload, dict) else None


def delete_policy(name: str) -> bool:
    path = policy_path(name)
    if not path.exists():
        return False
    path.unlink()
    return True


def list_policies() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(policies_dir().glob("*.json")):
        payload = load_json_file(path, None)
        if not isinstance(payload, dict):
            continue
        items.append(payload)
    items.sort(key=lambda item: (-int(item.get("priority", 0)), str(item.get("name", ""))))
    return items


def parse_description_meta(description: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    text = str(description or "").replace("\\r\\n", "\n").replace("\\n", "\n")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and key not in meta:
            meta[key] = value
    return meta


def safe_hostname(name: str, vmid: int) -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", str(name or "").strip().lower()).strip("-")
    if not cleaned:
        cleaned = f"beagle-{vmid}"
    return cleaned[:63].strip("-") or f"beagle-{vmid}"


def first_guest_ipv4(vmid: int) -> str:
    if not ENABLE_GUEST_IP_LOOKUP:
        return ""
    cache_key = f"guest-ipv4:{int(vmid)}"
    cached = cache_get(cache_key, GUEST_IPV4_CACHE_SECONDS)
    if isinstance(cached, str):
        return cached
    payload = run_json(["qm", "guest", "cmd", str(vmid), "network-get-interfaces"], timeout=GUEST_AGENT_TIMEOUT_SECONDS)
    if not isinstance(payload, list):
        return ""
    for iface in payload:
        for address in iface.get("ip-addresses", []):
            ip = str(address.get("ip-address", ""))
            if address.get("ip-address-type") != "ipv4":
                continue
            if not ip or ip.startswith("127.") or ip.startswith("169.254."):
                continue
            return cache_put(cache_key, ip)
    return ""


def list_vms() -> list[VmSummary]:
    cached = cache_get("list-vms", LIST_VMS_CACHE_SECONDS)
    if isinstance(cached, list):
        return cached
    resources = run_json(["pvesh", "get", "/cluster/resources", "--type", "vm", "--output-format", "json"])
    vms: list[VmSummary] = []
    if not isinstance(resources, list):
        return vms
    for item in resources:
        if item.get("type") != "qemu" or item.get("vmid") is None or not item.get("node"):
            continue
        vms.append(
            VmSummary(
                vmid=int(item["vmid"]),
                node=str(item["node"]),
                name=str(item.get("name") or f"vm-{item['vmid']}"),
                status=str(item.get("status") or "unknown"),
                tags=str(item.get("tags") or ""),
            )
        )
    return cache_put("list-vms", sorted(vms, key=lambda vm: vm.vmid))


def get_vm_config(node: str, vmid: int) -> dict[str, Any]:
    cache_key = f"vm-config:{node}:{int(vmid)}"
    cached = cache_get(cache_key, VM_CONFIG_CACHE_SECONDS)
    if isinstance(cached, dict):
        return cached
    payload = run_json(["pvesh", "get", f"/nodes/{node}/qemu/{vmid}/config", "--output-format", "json"])
    if isinstance(payload, dict):
        return cache_put(cache_key, payload)
    return {}


def find_vm(vmid: int) -> VmSummary | None:
    return next((candidate for candidate in list_vms() if candidate.vmid == vmid), None)


def should_use_public_stream(meta: dict[str, str], guest_ip: str) -> bool:
    if not PUBLIC_STREAM_HOST:
        return False
    if str(meta.get("beagle-public-stream", "1")).strip().lower() in {"0", "false", "no", "off"}:
        return False
    if meta.get("beagle-public-moonlight-port"):
        return True
    if meta.get("sunshine-user") or meta.get("sunshine-password") or meta.get("sunshine-api-url"):
        return True
    if meta.get("moonlight-host") or meta.get("sunshine-host") or meta.get("sunshine-ip"):
        return True
    if guest_ip and str(meta.get("beagle-role", "")).strip().lower() == "desktop":
        return True
    return False


def build_public_stream_details(vm: VmSummary, meta: dict[str, str], guest_ip: str) -> dict[str, Any] | None:
    if not should_use_public_stream(meta, guest_ip):
        return None
    explicit_port = str(meta.get("beagle-public-moonlight-port", "")).strip()
    if explicit_port.isdigit():
        base_port = int(explicit_port)
    else:
        allocated = allocate_public_stream_base_port(vm.node, vm.vmid)
        if allocated is None:
            return None
        base_port = int(allocated)
    public_host = str(meta.get("beagle-public-stream-host", "")).strip() or PUBLIC_STREAM_HOST
    ports = stream_ports(base_port)
    return {
        "enabled": True,
        "host": public_host,
        "guest_ip": guest_ip,
        "moonlight_port": ports["moonlight_port"],
        "sunshine_api_url": str(meta.get("beagle-public-sunshine-api-url", "")).strip() or f"https://{public_host}:{ports['sunshine_api_port']}",
        "ports": ports,
    }


def resolve_assigned_target(target_vmid: int, target_node: str, *, allow_assignment: bool) -> dict[str, Any] | None:
    target_vm = find_vm(target_vmid)
    if target_vm is None:
        return None
    if target_node and target_node != target_vm.node:
        return None
    target_profile = build_profile(target_vm, allow_assignment=False)
    return {
        "vmid": target_vm.vmid,
        "node": target_vm.node,
        "name": target_vm.name,
        "stream_host": target_profile["stream_host"],
        "moonlight_port": target_profile.get("moonlight_port", ""),
        "sunshine_api_url": target_profile["sunshine_api_url"],
        "moonlight_app": target_profile["moonlight_app"],
    }


def resolve_policy_for_vm(vm: VmSummary, meta: dict[str, str]) -> dict[str, Any] | None:
    tags = {item.strip() for item in str(vm.tags or "").split(";") if item.strip()}
    role = meta.get("beagle-role", "desktop" if meta.get("moonlight-host") or meta.get("sunshine-ip") or meta.get("sunshine-host") else "")
    for policy in list_policies():
        if not policy.get("enabled", True):
            continue
        selector = policy.get("selector", {}) if isinstance(policy.get("selector"), dict) else {}
        selector_vmid = selector.get("vmid")
        if selector_vmid is not None and int(selector_vmid) != vm.vmid:
            continue
        if selector.get("node") and str(selector.get("node")).strip() != vm.node:
            continue
        if selector.get("role") and str(selector.get("role")).strip() != role:
            continue
        tags_any = {item for item in selector.get("tags_any", []) if item}
        if tags_any and not tags.intersection(tags_any):
            continue
        tags_all = {item for item in selector.get("tags_all", []) if item}
        if tags_all and not tags_all.issubset(tags):
            continue
        return policy
    return None


def assess_vm_fingerprint(config: dict[str, Any], meta: dict[str, str], guest_ip: str) -> dict[str, Any]:
    vga = str(config.get("vga", "") or "").strip()
    machine = str(config.get("machine", "") or "").strip()
    cpu = str(config.get("cpu", "") or "").strip()
    tags = str(config.get("tags", "") or "")
    risk_flags: list[str] = []
    recommendations: list[str] = []
    if "virtio" in vga.lower():
      risk_flags.append("virtio-gpu")
      recommendations.append("Use GPU passthrough or a less generic virtual display path.")
    if "q35" in machine.lower():
      risk_flags.append("q35-machine")
    if not cpu or cpu.lower() in {"kvm64", "x86-64-v2-aes"}:
      risk_flags.append("generic-cpu")
      recommendations.append("Set CPU type to host for more realistic guest characteristics.")
    if guest_ip:
      risk_flags.append("guest-networked")
    if meta.get("beagle-public-stream-host") or meta.get("beagle-public-moonlight-port"):
      risk_flags.append("public-stream")
    risk_level = "low"
    if len(risk_flags) >= 4:
      risk_level = "high"
    elif len(risk_flags) >= 2:
      risk_level = "medium"
    return {
      "risk_level": risk_level,
      "flags": risk_flags,
      "recommendations": recommendations,
      "vga": vga,
      "machine": machine,
      "cpu": cpu,
      "tags": tags,
    }


def build_profile(vm: VmSummary, *, allow_assignment: bool = True) -> dict[str, Any]:
    config = get_vm_config(vm.node, vm.vmid)
    meta = parse_description_meta(config.get("description", ""))
    matched_policy = resolve_policy_for_vm(vm, meta) if allow_assignment else None
    policy_profile = matched_policy.get("profile", {}) if isinstance(matched_policy, dict) and isinstance(matched_policy.get("profile"), dict) else {}
    needs_guest_ip = not any(
        [
            policy_profile.get("stream_host"),
            meta.get("moonlight-host"),
            meta.get("sunshine-ip"),
            meta.get("sunshine-host"),
            meta.get("sunshine-api-url"),
            meta.get("beagle-public-stream-host"),
            meta.get("beagle-public-moonlight-port"),
        ]
    )
    guest_ip = first_guest_ipv4(vm.vmid) if vm.status == "running" and needs_guest_ip else ""
    guest_ip = guest_ip or str(meta.get("sunshine-ip", "")).strip()
    stream_host = policy_profile.get("stream_host") or meta.get("moonlight-host") or meta.get("sunshine-ip") or meta.get("sunshine-host") or guest_ip
    moonlight_port = str(policy_profile.get("moonlight_port") or meta.get("moonlight-port") or meta.get("beagle-public-moonlight-port") or "").strip()
    sunshine_api_url = policy_profile.get("sunshine_api_url") or meta.get("sunshine-api-url") or (f"https://{stream_host}:47990" if stream_host else "")
    public_stream = build_public_stream_details(vm, meta, guest_ip)
    if public_stream is not None:
        stream_host = public_stream["host"]
        moonlight_port = str(public_stream["moonlight_port"])
        sunshine_api_url = public_stream["sunshine_api_url"]
    installer_url = f"/beagle-api/api/v1/vms/{vm.vmid}/installer.sh"
    live_usb_url = f"/beagle-api/api/v1/vms/{vm.vmid}/live-usb.sh"
    installer_windows_url = f"/beagle-api/api/v1/vms/{vm.vmid}/installer.ps1"
    installer_iso_url = public_installer_iso_url()
    vm_secret = load_vm_secret(vm.node, vm.vmid)
    has_sunshine_password = bool((vm_secret or {}).get("sunshine_password"))
    expected_profile_name = policy_profile.get("expected_profile_name") or meta.get("beagle-profile-name", "")
    moonlight_app = policy_profile.get("moonlight_app") or meta.get("moonlight-app", meta.get("sunshine-app", "Desktop"))
    egress_domains = listify(policy_profile.get("egress_domains") or meta.get("beagle-egress-domains", ""))
    egress_resolvers = listify(policy_profile.get("egress_resolvers") or meta.get("beagle-egress-resolvers", ""))
    egress_allowed_ips = listify(policy_profile.get("egress_allowed_ips") or meta.get("beagle-egress-allowed-ips", ""))
    profile = {
        "vmid": vm.vmid,
        "node": vm.node,
        "name": config.get("name") or vm.name,
        "status": vm.status,
        "tags": vm.tags,
        "guest_ip": guest_ip,
        "stream_host": stream_host,
        "moonlight_port": moonlight_port,
        "sunshine_api_url": sunshine_api_url,
        "sunshine_username": "",
        "sunshine_password_configured": has_sunshine_password,
        "sunshine_pin": "",
        "moonlight_app": moonlight_app,
        "moonlight_resolution": policy_profile.get("moonlight_resolution") or meta.get("moonlight-resolution", "auto"),
        "moonlight_fps": policy_profile.get("moonlight_fps") or meta.get("moonlight-fps", "60"),
        "moonlight_bitrate": policy_profile.get("moonlight_bitrate") or meta.get("moonlight-bitrate", "20000"),
        "moonlight_video_codec": policy_profile.get("moonlight_video_codec") or meta.get("moonlight-video-codec", "H.264"),
        "moonlight_video_decoder": policy_profile.get("moonlight_video_decoder") or meta.get("moonlight-video-decoder", "auto"),
        "moonlight_audio_config": policy_profile.get("moonlight_audio_config") or meta.get("moonlight-audio-config", "stereo"),
        "egress_mode": policy_profile.get("egress_mode") or meta.get("beagle-egress-mode", "direct"),
        "egress_type": policy_profile.get("egress_type") or meta.get("beagle-egress-type", ""),
        "egress_interface": policy_profile.get("egress_interface") or meta.get("beagle-egress-interface", "beagle-egress"),
        "egress_domains": egress_domains,
        "egress_resolvers": egress_resolvers,
        "egress_allowed_ips": egress_allowed_ips,
        "egress_wg_address": policy_profile.get("egress_wg_address") or meta.get("beagle-egress-wg-address", ""),
        "egress_wg_dns": policy_profile.get("egress_wg_dns") or meta.get("beagle-egress-wg-dns", ""),
        "egress_wg_public_key": policy_profile.get("egress_wg_public_key") or meta.get("beagle-egress-wg-public-key", ""),
        "egress_wg_endpoint": policy_profile.get("egress_wg_endpoint") or meta.get("beagle-egress-wg-endpoint", ""),
        "egress_wg_private_key": policy_profile.get("egress_wg_private_key") or meta.get("beagle-egress-wg-private-key", ""),
        "egress_wg_preshared_key": policy_profile.get("egress_wg_preshared_key") or meta.get("beagle-egress-wg-preshared-key", ""),
        "egress_wg_persistent_keepalive": policy_profile.get("egress_wg_persistent_keepalive") or meta.get("beagle-egress-wg-persistent-keepalive", "25"),
        "identity_hostname": policy_profile.get("identity_hostname") or meta.get("beagle-identity-hostname", safe_hostname(config.get("name") or vm.name, vm.vmid)),
        "identity_timezone": policy_profile.get("identity_timezone") or meta.get("beagle-identity-timezone", "UTC"),
        "identity_locale": policy_profile.get("identity_locale") or meta.get("beagle-identity-locale", "en_US.UTF-8"),
        "identity_keymap": policy_profile.get("identity_keymap") or meta.get("beagle-identity-keymap", ""),
        "identity_chrome_profile": policy_profile.get("identity_chrome_profile") or meta.get("beagle-identity-chrome-profile", expected_profile_name or f"vm-{vm.vmid}"),
        "network_mode": policy_profile.get("network_mode") or meta.get("thinclient-network-mode", "dhcp"),
        "default_mode": "MOONLIGHT" if stream_host else "",
        "beagle_hostname": safe_hostname(config.get("name") or vm.name, vm.vmid),
        "beagle_manager_pinned_pubkey": MANAGER_PINNED_PUBKEY,
        "beagle_role": policy_profile.get("beagle_role") or meta.get("beagle-role", "desktop" if stream_host else ""),
        "expected_profile_name": expected_profile_name,
        "installer_url": installer_url,
        "live_usb_url": live_usb_url,
        "installer_windows_url": installer_windows_url,
        "installer_iso_url": installer_iso_url,
        "public_stream": public_stream,
        "metadata_keys": sorted(meta.keys()),
        "applied_policy": {
            "name": matched_policy.get("name", ""),
            "priority": matched_policy.get("priority", 0),
        } if matched_policy else None,
        "config_digest": {
            "memory": config.get("memory"),
            "cores": config.get("cores"),
            "sockets": config.get("sockets"),
            "machine": config.get("machine"),
            "ostype": config.get("ostype"),
            "agent": config.get("agent"),
            "vga": config.get("vga"),
        },
        "vm_fingerprint": assess_vm_fingerprint(config, meta, guest_ip),
    }
    if allow_assignment:
        target_vmid = None
        target_node = ""
        assignment_source = ""
        policy_target = policy_profile.get("assigned_target") if isinstance(policy_profile.get("assigned_target"), dict) else None
        if policy_target and policy_target.get("vmid") is not None:
            target_vmid = int(policy_target["vmid"])
            target_node = str(policy_target.get("node", "")).strip()
            assignment_source = "manager-policy"
        else:
            assigned_vmid = meta.get("beagle-target-vmid", "").strip()
            if assigned_vmid.isdigit():
                target_vmid = int(assigned_vmid)
                target_node = meta.get("beagle-target-node", "").strip()
                assignment_source = "vm-metadata"
        if target_vmid is not None:
            assigned_target = resolve_assigned_target(target_vmid, target_node, allow_assignment=False)
            if assigned_target is not None:
                profile["assigned_target"] = assigned_target
                profile["assignment_source"] = assignment_source
                profile["beagle_role"] = "endpoint"
                if (assignment_source == "manager-policy" or not meta.get("moonlight-host")) and assigned_target["stream_host"]:
                    profile["stream_host"] = assigned_target["stream_host"]
                if (assignment_source == "manager-policy" or not meta.get("moonlight-port")) and assigned_target.get("moonlight_port"):
                    profile["moonlight_port"] = assigned_target["moonlight_port"]
                if (assignment_source == "manager-policy" or not meta.get("sunshine-api-url")) and assigned_target["sunshine_api_url"]:
                    profile["sunshine_api_url"] = assigned_target["sunshine_api_url"]
                if (assignment_source == "manager-policy" or not meta.get("moonlight-app")) and assigned_target["moonlight_app"]:
                    profile["moonlight_app"] = assigned_target["moonlight_app"]
                if not expected_profile_name:
                    profile["expected_profile_name"] = f"vm-{target_vmid}"
                profile["default_mode"] = "MOONLIGHT" if profile["stream_host"] else ""
                if assigned_target.get("moonlight_port"):
                    profile["public_stream"] = {
                        "enabled": True,
                        "host": profile["stream_host"],
                        "moonlight_port": profile["moonlight_port"],
                        "sunshine_api_url": profile["sunshine_api_url"],
                    }
    role_text = str(profile.get("beagle_role", "")).strip().lower()
    installer_target_eligible = bool(profile.get("stream_host")) and role_text not in {"endpoint", "thinclient", "client"}
    if installer_target_eligible:
        installer_target_message = "Diese VM kann als Sunshine-Ziel vorbereitet und als Beagle-Profil installiert werden."
    elif role_text in {"endpoint", "thinclient", "client"}:
        installer_target_message = "Diese VM ist als Beagle-Endpunkt klassifiziert und wird nicht als Streaming-Ziel angeboten."
    else:
        installer_target_message = "Diese VM hat aktuell kein verwertbares Sunshine-/Moonlight-Streaming-Ziel."
    profile["installer_target_eligible"] = installer_target_eligible
    profile["installer_target_message"] = installer_target_message
    return profile


def evaluate_endpoint_compliance(profile: dict[str, Any], report: dict[str, Any] | None) -> dict[str, Any]:
    managed = bool(profile.get("stream_host") or profile.get("assigned_target") or profile.get("expected_profile_name"))
    desired = {
        "stream_host": profile.get("stream_host", ""),
        "moonlight_port": profile.get("moonlight_port", ""),
        "moonlight_app": profile.get("moonlight_app", ""),
        "network_mode": profile.get("network_mode", ""),
        "egress_mode": profile.get("egress_mode", ""),
        "identity_timezone": profile.get("identity_timezone", ""),
        "identity_locale": profile.get("identity_locale", ""),
        "profile_name": profile.get("expected_profile_name", ""),
        "assigned_target": profile.get("assigned_target"),
    }
    if not isinstance(report, dict):
        return {
            "managed": managed,
            "endpoint_seen": False,
            "status": "pending" if managed else "unmanaged",
            "compliant": False,
            "drift_count": 0,
            "alert_count": 0,
            "drift": [],
            "alerts": [],
            "desired": desired,
        }

    summary = summarize_endpoint_report(report)
    drift: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    reported_at = str(summary.get("reported_at", ""))
    report_age_seconds = timestamp_age_seconds(reported_at)

    def compare(field: str, expected: str, actual: str, label: str) -> None:
        if not expected:
            return
        if str(expected).strip() == str(actual).strip():
            return
        drift.append({"field": field, "label": label, "expected": expected, "actual": actual})

    compare("stream_host", str(profile.get("stream_host", "")), str(summary.get("stream_host", "")), "Stream Host")
    compare("moonlight_port", str(profile.get("moonlight_port", "")), str(summary.get("moonlight_port", "")), "Moonlight Port")
    compare("moonlight_app", str(profile.get("moonlight_app", "")), str(summary.get("moonlight_app", "")), "Moonlight App")
    compare("network_mode", str(profile.get("network_mode", "")), str(summary.get("network_mode", "")), "Network Mode")
    compare("egress_mode", str(profile.get("egress_mode", "")), str(summary.get("egress_mode", "")), "Egress Mode")
    compare("identity_timezone", str(profile.get("identity_timezone", "")), str(summary.get("identity_timezone", "")), "Timezone")
    compare("identity_locale", str(profile.get("identity_locale", "")), str(summary.get("identity_locale", "")), "Locale")
    compare("profile_name", str(profile.get("expected_profile_name", "")), str(summary.get("profile_name", "")), "Profile Name")

    def alert(field: str, label: str, actual: str, expected: str = "1") -> None:
        if str(actual).strip() == str(expected).strip():
            return
        alerts.append({"field": field, "label": label, "expected": expected, "actual": actual})

    alert("moonlight_target_reachable", "Target Reachable", str(summary.get("moonlight_target_reachable", "")))
    alert("sunshine_api_reachable", "Sunshine API Reachable", str(summary.get("sunshine_api_reachable", "")))
    alert("runtime_binary_available", "Moonlight Runtime", str(summary.get("runtime_binary_available", "")))
    vm_fingerprint = profile.get("vm_fingerprint", {}) if isinstance(profile.get("vm_fingerprint"), dict) else {}
    if str(vm_fingerprint.get("risk_level", "")).lower() == "high":
        alerts.append({
            "field": "vm_fingerprint",
            "label": "VM Fingerprint",
            "expected": "low/medium risk",
            "actual": "high risk",
        })

    autologin_state = str(summary.get("autologin_state", "")).strip()
    if autologin_state and autologin_state != "active":
        alerts.append({"field": "autologin_state", "label": "Autologin", "expected": "active", "actual": autologin_state})

    status = "healthy"
    if drift:
        status = "drifted"
    elif report_age_seconds is not None and report_age_seconds > STALE_ENDPOINT_SECONDS:
        status = "stale"
        alerts.append({
            "field": "reported_at",
            "label": "Last Check-In",
            "expected": f"<={STALE_ENDPOINT_SECONDS}s",
            "actual": f"{report_age_seconds}s",
        })
    elif alerts:
        status = "degraded"

    return {
        "managed": managed,
        "endpoint_seen": True,
        "status": status,
        "compliant": not drift,
        "stale": bool(report_age_seconds is not None and report_age_seconds > STALE_ENDPOINT_SECONDS),
        "report_age_seconds": report_age_seconds,
        "drift_count": len(drift),
        "alert_count": len(alerts),
        "drift": drift,
        "alerts": alerts,
        "desired": desired,
    }


def build_vm_state(vm: VmSummary) -> dict[str, Any]:
    profile = build_profile(vm)
    report = load_endpoint_report(vm.node, vm.vmid)
    endpoint = summarize_endpoint_report(report or {})
    compliance = evaluate_endpoint_compliance(profile, report)
    last_action = summarize_action_result(load_action_result(vm.node, vm.vmid))
    pending_actions = load_action_queue(vm.node, vm.vmid)
    installer_prep = summarize_installer_prep_state(vm, load_installer_prep_state(vm.node, vm.vmid))
    return {
        "profile": profile,
        "endpoint": endpoint,
        "compliance": compliance,
        "last_action": last_action,
        "pending_action_count": len(pending_actions),
        "installer_prep": installer_prep,
    }


def build_health_payload() -> dict[str, Any]:
    downloads_status = load_json_file(DOWNLOADS_STATUS_FILE, {})
    vm_installers = load_json_file(VM_INSTALLERS_FILE, [])
    endpoint_reports = list_endpoint_reports()
    policies = list_policies()
    vms = list_vms()
    status_counts = {"healthy": 0, "degraded": 0, "drifted": 0, "stale": 0, "pending": 0, "unmanaged": 0}
    pending_action_count = 0
    for vm in vms:
        profile = build_profile(vm)
        endpoint = summarize_endpoint_report(load_endpoint_report(vm.node, vm.vmid) or {})
        role = str(profile.get("beagle_role", "")).strip().lower()
        report_age = endpoint.get("report_age_seconds")
        if role in {"endpoint", "thinclient", "client"}:
            if not endpoint.get("reported_at"):
                status = "pending"
            elif report_age is not None and int(report_age) > STALE_ENDPOINT_SECONDS:
                status = "stale"
            elif endpoint.get("moonlight_target_reachable") not in {"1", 1, True}:
                status = "degraded"
            else:
                status = "healthy"
        elif profile.get("installer_target_eligible"):
            status = "healthy" if vm.status == "running" else "degraded"
        else:
            status = "unmanaged"
        status_counts[status] = status_counts.get(status, 0) + 1
        pending_action_count += len(load_action_queue(vm.node, vm.vmid))
    return {
        "service": "beagle-control-plane",
        "ok": True,
        "version": VERSION,
        "generated_at": utcnow(),
        "downloads_status_present": DOWNLOADS_STATUS_FILE.exists(),
        "downloads_status": downloads_status,
        "vm_installer_inventory_present": VM_INSTALLERS_FILE.exists(),
        "vm_installer_count": len(vm_installers) if isinstance(vm_installers, list) else 0,
        "vm_count": len(vms),
        "endpoint_count": len(endpoint_reports),
        "policy_count": len(policies),
        "pending_action_count": pending_action_count,
        "endpoint_status_counts": status_counts,
        "data_dir": str(EFFECTIVE_DATA_DIR),
    }


def summarize_endpoint_report(payload: dict[str, Any]) -> dict[str, Any]:
    health = payload.get("health", {}) if isinstance(payload.get("health"), dict) else {}
    session = payload.get("session", {}) if isinstance(payload.get("session"), dict) else {}
    runtime = payload.get("runtime", {}) if isinstance(payload.get("runtime"), dict) else {}
    egress = payload.get("egress", {}) if isinstance(payload.get("egress"), dict) else {}
    identity = payload.get("identity", {}) if isinstance(payload.get("identity"), dict) else {}
    return {
        "endpoint_id": payload.get("endpoint_id", ""),
        "hostname": payload.get("hostname", ""),
        "profile_name": payload.get("profile_name", ""),
        "vmid": payload.get("vmid"),
        "node": payload.get("node", ""),
        "reported_at": payload.get("reported_at", ""),
        "stream_host": payload.get("stream_host", ""),
        "moonlight_port": payload.get("moonlight_port", ""),
        "moonlight_app": payload.get("moonlight_app", ""),
        "network_mode": payload.get("network_mode", ""),
        "egress_mode": payload.get("egress_mode", "") or egress.get("mode", ""),
        "egress_state": egress.get("state", ""),
        "egress_public_ip": egress.get("public_ip", ""),
        "identity_timezone": identity.get("timezone", ""),
        "identity_locale": identity.get("locale", ""),
        "identity_keymap": identity.get("keymap", ""),
        "identity_chrome_profile": identity.get("chrome_profile", ""),
        "ip_summary": health.get("ip_summary", ""),
        "external_ip": health.get("external_ip", ""),
        "virtualization_type": health.get("virtualization_type", ""),
        "networkmanager_state": health.get("networkmanager_state", ""),
        "autologin_state": health.get("autologin_state", ""),
        "prepare_state": health.get("prepare_state", ""),
        "guest_agent_state": health.get("guest_agent_state", ""),
        "moonlight_target_reachable": health.get("moonlight_target_reachable", ""),
        "sunshine_api_reachable": health.get("sunshine_api_reachable", ""),
        "runtime_binary": runtime.get("required_binary", ""),
        "runtime_binary_available": runtime.get("binary_available", ""),
        "last_launch_mode": session.get("mode", ""),
        "last_launch_target": session.get("target", ""),
        "last_launch_time": session.get("timestamp", ""),
        "usb_tunnel_state": (payload.get("usb", {}) if isinstance(payload.get("usb"), dict) else {}).get("tunnel_state", ""),
        "usb_tunnel_port": (payload.get("usb", {}) if isinstance(payload.get("usb"), dict) else {}).get("tunnel_port", ""),
        "usb_device_count": int((payload.get("usb", {}) if isinstance(payload.get("usb"), dict) else {}).get("device_count", 0) or 0),
        "usb_bound_count": int((payload.get("usb", {}) if isinstance(payload.get("usb"), dict) else {}).get("bound_count", 0) or 0),
        "usb_devices": (payload.get("usb", {}) if isinstance(payload.get("usb"), dict) else {}).get("devices", []) or [],
        "report_age_seconds": timestamp_age_seconds(payload.get("reported_at", "")),
    }


def endpoint_report_path(node: str, vmid: int) -> Path:
    safe_node = re.sub(r"[^A-Za-z0-9._-]+", "-", str(node or "unknown")).strip("-") or "unknown"
    return endpoints_dir() / f"{safe_node}-{int(vmid)}.json"


def load_endpoint_report(node: str, vmid: int) -> dict[str, Any] | None:
    payload = load_json_file(endpoint_report_path(node, vmid), None)
    return payload if isinstance(payload, dict) else None


def list_endpoint_reports() -> list[dict[str, Any]]:
    reports = []
    for path in sorted(endpoints_dir().glob("*.json")):
        payload = load_json_file(path, None)
        if not isinstance(payload, dict):
            continue
        payload["_path"] = str(path)
        reports.append(payload)
    reports.sort(key=lambda item: (str(item.get("node", "")), int(item.get("vmid", 0))))
    return reports


def build_vm_inventory() -> dict[str, Any]:
    inventory = []
    installers = load_json_file(VM_INSTALLERS_FILE, [])
    installers_by_vmid = {
        int(item.get("vmid")): item for item in installers if isinstance(item, dict) and item.get("vmid") is not None
    }
    for vm in list_vms():
        profile = build_profile(vm)
        installer = installers_by_vmid.get(vm.vmid, {})
        endpoint = summarize_endpoint_report(load_endpoint_report(vm.node, vm.vmid) or {})
        last_action = summarize_action_result(load_action_result(vm.node, vm.vmid))
        pending_action_count = len(load_action_queue(vm.node, vm.vmid))
        inventory.append(
            {
                "vmid": vm.vmid,
                "node": vm.node,
                "name": vm.name,
                "status": vm.status,
                "stream_host": profile["stream_host"],
                "moonlight_port": profile.get("moonlight_port", ""),
                "sunshine_api_url": profile["sunshine_api_url"],
                "moonlight_app": profile["moonlight_app"],
                "network_mode": profile["network_mode"],
                "egress_mode": profile.get("egress_mode", "direct"),
                "identity_timezone": profile.get("identity_timezone", ""),
                "identity_locale": profile.get("identity_locale", ""),
                "vm_fingerprint": profile.get("vm_fingerprint"),
                "expected_profile_name": profile["expected_profile_name"],
                "default_mode": "MOONLIGHT" if profile["stream_host"] else "",
                "installer_url": profile["installer_url"],
                "live_usb_url": profile.get("live_usb_url", f"/beagle-api/api/v1/vms/{vm.vmid}/live-usb.sh"),
                "installer_windows_url": profile.get("installer_windows_url", f"/beagle-api/api/v1/vms/{vm.vmid}/installer.ps1"),
                "installer_iso_url": profile.get("installer_iso_url", public_installer_iso_url()),
                "installer_target_eligible": profile.get("installer_target_eligible", False),
                "installer_target_message": profile.get("installer_target_message", ""),
                "available_modes": installer.get("available_modes") or (["MOONLIGHT"] if profile["stream_host"] else []),
                "assigned_target": profile.get("assigned_target"),
                "assignment_source": profile.get("assignment_source", ""),
                "applied_policy": profile.get("applied_policy"),
                "endpoint": endpoint,
                "compliance": {},
                "last_action": last_action,
                "pending_action_count": pending_action_count,
                "support_bundle_count": len(list_support_bundle_metadata(node=vm.node, vmid=vm.vmid)),
            }
        )
    return {
        "service": "beagle-control-plane",
        "version": VERSION,
        "generated_at": utcnow(),
        "vms": inventory,
    }


def build_installer_preset(vm: VmSummary, profile: dict[str, Any], config: dict[str, Any], *, enrollment_token: str, thinclient_password: str) -> dict[str, str]:
    meta = parse_description_meta(config.get("description", ""))
    vm_name = str(config.get("name") or vm.name or f"vm-{vm.vmid}")
    proxmox_scheme = meta.get("proxmox-scheme", "https")
    proxmox_host = meta.get("proxmox-host", PUBLIC_SERVER_NAME)
    proxmox_port = meta.get("proxmox-port", "8006")
    proxmox_realm = meta.get("proxmox-realm", "pam")
    proxmox_verify_tls = meta.get("proxmox-verify-tls", "1")
    expected_profile_name = str(profile.get("expected_profile_name") or f"vm-{vm.vmid}")
    moonlight_host = str(profile.get("stream_host", "") or "")
    moonlight_port = str(profile.get("moonlight_port", "") or "")
    sunshine_api_url = str(profile.get("sunshine_api_url", "") or "")
    vm_secret = ensure_vm_secret(vm)
    sunshine_username = str(vm_secret.get("sunshine_username", "") or "")
    sunshine_password = str(vm_secret.get("sunshine_password", "") or "")
    sunshine_pin = str(vm_secret.get("sunshine_pin", "") or "")
    sunshine_pinned_pubkey = str(vm_secret.get("sunshine_pinned_pubkey", "") or "")

    return {
        "PVE_THIN_CLIENT_PRESET_PROFILE_NAME": expected_profile_name,
        "PVE_THIN_CLIENT_PRESET_VM_NAME": vm_name,
        "PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE": safe_hostname(vm_name, vm.vmid),
        "PVE_THIN_CLIENT_PRESET_AUTOSTART": meta.get("thinclient-autostart", "1"),
        "PVE_THIN_CLIENT_PRESET_DEFAULT_MODE": "MOONLIGHT" if moonlight_host else "",
        "PVE_THIN_CLIENT_PRESET_NETWORK_MODE": meta.get("thinclient-network-mode", "dhcp"),
        "PVE_THIN_CLIENT_PRESET_NETWORK_INTERFACE": meta.get("thinclient-network-interface", "eth0"),
        "PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_ADDRESS": meta.get("thinclient-network-static-address", ""),
        "PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_PREFIX": meta.get("thinclient-network-static-prefix", "24"),
        "PVE_THIN_CLIENT_PRESET_NETWORK_GATEWAY": meta.get("thinclient-network-gateway", ""),
        "PVE_THIN_CLIENT_PRESET_NETWORK_DNS_SERVERS": meta.get("thinclient-network-dns-servers", "1.1.1.1 8.8.8.8"),
        "PVE_THIN_CLIENT_PRESET_PROXMOX_SCHEME": proxmox_scheme,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_HOST": proxmox_host,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_PORT": proxmox_port,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_NODE": vm.node,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_VMID": str(vm.vmid),
        "PVE_THIN_CLIENT_PRESET_PROXMOX_REALM": proxmox_realm,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_VERIFY_TLS": proxmox_verify_tls,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_PROXMOX_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_PROXMOX_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_URL": PUBLIC_MANAGER_URL,
        "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_PINNED_PUBKEY": MANAGER_PINNED_PUBKEY,
        "PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_URL": f"{PUBLIC_MANAGER_URL}/api/v1/endpoints/enroll",
        "PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_TOKEN": enrollment_token,
        "PVE_THIN_CLIENT_PRESET_THINCLIENT_PASSWORD": thinclient_password,
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_MODE": str(profile.get("egress_mode", "direct") or "direct"),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_TYPE": str(profile.get("egress_type", "") or ""),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_INTERFACE": str(profile.get("egress_interface", "beagle-egress") or "beagle-egress"),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_DOMAINS": " ".join(profile.get("egress_domains", []) or []),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_RESOLVERS": " ".join(profile.get("egress_resolvers", []) or []),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_ALLOWED_IPS": " ".join(profile.get("egress_allowed_ips", []) or []),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ADDRESS": str(profile.get("egress_wg_address", "") or ""),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_DNS": str(profile.get("egress_wg_dns", "") or ""),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PUBLIC_KEY": str(profile.get("egress_wg_public_key", "") or ""),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ENDPOINT": str(profile.get("egress_wg_endpoint", "") or ""),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRIVATE_KEY": str(profile.get("egress_wg_private_key", "") or ""),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRESHARED_KEY": str(profile.get("egress_wg_preshared_key", "") or ""),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE": str(profile.get("egress_wg_persistent_keepalive", "25") or "25"),
        "PVE_THIN_CLIENT_PRESET_IDENTITY_HOSTNAME": str(profile.get("identity_hostname", "") or ""),
        "PVE_THIN_CLIENT_PRESET_IDENTITY_TIMEZONE": str(profile.get("identity_timezone", "") or ""),
        "PVE_THIN_CLIENT_PRESET_IDENTITY_LOCALE": str(profile.get("identity_locale", "") or ""),
        "PVE_THIN_CLIENT_PRESET_IDENTITY_KEYMAP": str(profile.get("identity_keymap", "") or ""),
        "PVE_THIN_CLIENT_PRESET_IDENTITY_CHROME_PROFILE": str(profile.get("identity_chrome_profile", "") or ""),
        "PVE_THIN_CLIENT_PRESET_SPICE_METHOD": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_URL": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_URL": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_DCV_URL": "",
        "PVE_THIN_CLIENT_PRESET_DCV_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_DCV_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_DCV_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_DCV_SESSION": "",
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST": moonlight_host,
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_PORT": moonlight_port,
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_APP": str(profile.get("moonlight_app", "Desktop") or "Desktop"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_BIN": meta.get("moonlight-bin", "moonlight"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_RESOLUTION": str(profile.get("moonlight_resolution", "auto") or "auto"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_FPS": str(profile.get("moonlight_fps", "60") or "60"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_BITRATE": str(profile.get("moonlight_bitrate", "20000") or "20000"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_CODEC": str(profile.get("moonlight_video_codec", "H.264") or "H.264"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_DECODER": str(profile.get("moonlight_video_decoder", "auto") or "auto"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_AUDIO_CONFIG": str(profile.get("moonlight_audio_config", "stereo") or "stereo"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_ABSOLUTE_MOUSE": meta.get("moonlight-absolute-mouse", "1"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_QUIT_AFTER": meta.get("moonlight-quit-after", "0"),
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_API_URL": sunshine_api_url,
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_USERNAME": sunshine_username,
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_PASSWORD": sunshine_password,
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_PIN": sunshine_pin,
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_PINNED_PUBKEY": sunshine_pinned_pubkey,
    }


def render_vm_installer_script(vm: VmSummary) -> tuple[bytes, str]:
    if not HOSTED_INSTALLER_TEMPLATE_FILE.is_file():
        raise FileNotFoundError(f"missing installer template: {HOSTED_INSTALLER_TEMPLATE_FILE}")
    if not HOSTED_INSTALLER_ISO_FILE.is_file():
        raise FileNotFoundError(f"missing installer ISO: {HOSTED_INSTALLER_ISO_FILE}")
    config = get_vm_config(vm.node, vm.vmid)
    profile = build_profile(vm)
    enrollment_token, enrollment_record = issue_enrollment_token(vm)
    preset = build_installer_preset(
        vm,
        profile,
        config,
        enrollment_token=enrollment_token,
        thinclient_password=str(enrollment_record.get("thinclient_password", "")),
    )
    preset_name = preset.get("PVE_THIN_CLIENT_PRESET_PROFILE_NAME") or f"vm-{vm.vmid}"
    preset_b64 = encode_installer_preset(preset)
    rendered = patch_installer_defaults(
        HOSTED_INSTALLER_TEMPLATE_FILE.read_text(encoding="utf-8"),
        preset_name,
        preset_b64,
        str(profile.get("installer_iso_url") or public_installer_iso_url()),
    )
    filename = f"pve-thin-client-usb-installer-vm-{vm.vmid}.sh"
    return rendered.encode("utf-8"), filename


def render_vm_live_usb_script(vm: VmSummary) -> tuple[bytes, str]:
    if not HOSTED_LIVE_USB_TEMPLATE_FILE.is_file():
        raise FileNotFoundError(f"missing live USB template: {HOSTED_LIVE_USB_TEMPLATE_FILE}")
    if not HOSTED_INSTALLER_ISO_FILE.is_file():
        raise FileNotFoundError(f"missing installer ISO: {HOSTED_INSTALLER_ISO_FILE}")
    config = get_vm_config(vm.node, vm.vmid)
    profile = build_profile(vm)
    enrollment_token, enrollment_record = issue_enrollment_token(vm)
    preset = build_installer_preset(
        vm,
        profile,
        config,
        enrollment_token=enrollment_token,
        thinclient_password=str(enrollment_record.get("thinclient_password", "")),
    )
    preset_name = preset.get("PVE_THIN_CLIENT_PRESET_PROFILE_NAME") or f"vm-{vm.vmid}"
    preset_b64 = encode_installer_preset(preset)
    rendered = patch_installer_defaults(
        HOSTED_LIVE_USB_TEMPLATE_FILE.read_text(encoding="utf-8"),
        preset_name,
        preset_b64,
        str(profile.get("installer_iso_url") or public_installer_iso_url()),
    )
    filename = f"pve-thin-client-live-usb-vm-{vm.vmid}.sh"
    return rendered.encode("utf-8"), filename


def render_vm_windows_installer_script(vm: VmSummary) -> tuple[bytes, str]:
    if not RAW_WINDOWS_INSTALLER_TEMPLATE_FILE.is_file():
        raise FileNotFoundError(f"missing windows installer template: {RAW_WINDOWS_INSTALLER_TEMPLATE_FILE}")
    if not HOSTED_INSTALLER_ISO_FILE.is_file():
        raise FileNotFoundError(f"missing installer ISO: {HOSTED_INSTALLER_ISO_FILE}")
    config = get_vm_config(vm.node, vm.vmid)
    profile = build_profile(vm)
    enrollment_token, enrollment_record = issue_enrollment_token(vm)
    preset = build_installer_preset(
        vm,
        profile,
        config,
        enrollment_token=enrollment_token,
        thinclient_password=str(enrollment_record.get("thinclient_password", "")),
    )
    preset_name = preset.get("PVE_THIN_CLIENT_PRESET_PROFILE_NAME") or f"vm-{vm.vmid}"
    preset_b64 = encode_installer_preset(preset)
    rendered = patch_windows_installer_defaults(
        RAW_WINDOWS_INSTALLER_TEMPLATE_FILE.read_text(encoding="utf-8"),
        preset_name,
        preset_b64,
        str(profile.get("installer_iso_url") or public_installer_iso_url()),
    )
    filename = f"pve-thin-client-usb-installer-vm-{vm.vmid}.ps1"
    return rendered.encode("utf-8"), filename


def extract_bearer_token(header_value: str) -> str:
    header = str(header_value or "").strip()
    if header.startswith("Bearer "):
        return header[7:].strip()
    return ""


class Handler(BaseHTTPRequestHandler):
    server_version = f"BeagleControlPlane/{VERSION}"

    def _is_authenticated(self) -> bool:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in {"/healthz", "/api/v1/health"}:
            return True
        if ALLOW_LOCALHOST_NOAUTH and self.client_address[0] in {"127.0.0.1", "::1"}:
            return True
        if not API_TOKEN:
            return False
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer ") and header[7:].strip() == API_TOKEN:
            return True
        if self.headers.get("X-Beagle-Api-Token", "").strip() == API_TOKEN:
            return True
        return False

    def _endpoint_identity(self) -> dict[str, Any] | None:
        token = extract_bearer_token(self.headers.get("Authorization", ""))
        if not token:
            token = self.headers.get("X-Beagle-Endpoint-Token", "").strip()
        if not token:
            return None
        payload = load_endpoint_token(token)
        return payload if isinstance(payload, dict) else None

    def _is_endpoint_authenticated(self) -> bool:
        if ALLOW_LOCALHOST_NOAUTH and self.client_address[0] in {"127.0.0.1", "::1"}:
            return True
        return self._endpoint_identity() is not None

    def _cors_origin(self) -> str:
        origin = self.headers.get("Origin", "")
        if origin:
            return origin
        return "*"

    def _write_json(self, status: HTTPStatus, payload: Any) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 256 * 1024:
            raise ValueError("invalid content length")
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid payload")
        return payload

    def _read_binary_body(self, *, max_bytes: int) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > max_bytes:
            raise ValueError("invalid content length")
        return self.rfile.read(length)

    def _write_bytes(self, status: HTTPStatus, body: bytes, *, content_type: str, filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _endpoint_summary_for_vmid(self, vmid: int) -> dict[str, Any] | None:
        for vm in list_vms():
            if vm.vmid == vmid:
                report = load_endpoint_report(vm.node, vm.vmid)
                if report is None:
                    return None
                return summarize_endpoint_report(report)
        return None

    def _vm_state_for_vmid(self, vmid: int) -> dict[str, Any] | None:
        vm = find_vm(vmid)
        if vm is None:
            return None
        return build_vm_state(vm)

    def _requester_identity(self) -> str:
        if self.client_address and self.client_address[0]:
            return self.client_address[0]
        return "unknown"

    def _sunshine_ticket_vm(self, path: str) -> tuple[VmSummary | None, str]:
        prefix = "/api/v1/public/sunshine/"
        if not path.startswith(prefix):
            return None, ""
        remainder = path[len(prefix):]
        parts = remainder.split("/", 1)
        token = parts[0].strip()
        if not token:
            return None, ""
        payload = load_sunshine_access_token(token)
        if not sunshine_access_token_is_valid(payload):
            return None, ""
        vm = find_vm(int(payload.get("vmid", -1))) if payload else None
        relative = "/" if len(parts) == 1 or not parts[1] else f"/{parts[1]}"
        return vm, relative

    def _write_proxy_response(self, status_code: int, headers: dict[str, str], body: bytes) -> None:
        self.send_response(status_code)
        for key, value in headers.items():
            lower = key.lower()
            if lower in {"transfer-encoding", "connection", "content-length", "content-encoding"}:
                continue
            self.send_header(key, value)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Beagle-Api-Token, X-Beagle-Endpoint-Token")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query_text = parsed.query

        if path.startswith("/api/v1/public/sunshine/"):
            vm, relative = self._sunshine_ticket_vm(parsed.path)
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "sunshine ticket not found"})
                return
            try:
                status_code, headers, body = proxy_sunshine_request(
                    vm,
                    request_path=relative,
                    query=query_text,
                    method="GET",
                    body=None,
                    request_headers={"Accept": self.headers.get("Accept", "")},
                )
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"sunshine proxy failed: {exc}"})
                return
            self._write_proxy_response(status_code, headers, body)
            return

        if path.startswith("/api/v1/public/vms/") and path.endswith("/state"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            state = self._vm_state_for_vmid(int(vmid_text))
            if state is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    **state,
                },
            )
            return

        if path.startswith("/api/v1/public/vms/") and path.endswith("/endpoint"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            state = self._vm_state_for_vmid(int(vmid_text))
            if state is None or not state["endpoint"].get("reported_at"):
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "endpoint not found"})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    **state,
                },
            )
            return

        if path.startswith("/api/v1/public/vms/") and path.endswith("/installer.sh"):
            self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "public installer download disabled"})
            return
        if path.startswith("/api/v1/public/vms/") and path.endswith("/live-usb.sh"):
            self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "public live USB download disabled"})
            return
        if path.startswith("/api/v1/public/vms/") and path.endswith("/installer.ps1"):
            self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "public installer download disabled"})
            return

        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return

        if path == "/healthz":
            self._write_json(HTTPStatus.OK, {"ok": True, "service": "beagle-control-plane", "version": VERSION})
            return
        if path == "/api/v1/health":
            self._write_json(HTTPStatus.OK, build_health_payload())
            return
        if path == "/api/v1/vms":
            self._write_json(HTTPStatus.OK, build_vm_inventory())
            return
        if path == "/api/v1/endpoints":
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "endpoints": [summarize_endpoint_report(item) for item in list_endpoint_reports()],
                },
            )
            return
        if path == "/api/v1/policies":
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "policies": list_policies(),
                },
            )
            return
        if path.startswith("/api/v1/policies/"):
            policy_name = path.rsplit("/", 1)[-1]
            policy = load_policy(policy_name)
            if policy is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "policy not found"})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "policy": policy,
                },
            )
            return
        if path.startswith("/api/v1/support-bundles/") and path.endswith("/download"):
            bundle_id = path.split("/")[-2]
            metadata = find_support_bundle_metadata(bundle_id)
            if metadata is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "support bundle not found"})
                return
            archive_path = Path(str(metadata.get("stored_path", "")))
            if not archive_path.is_file():
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "support bundle payload missing"})
                return
            self._write_bytes(
                HTTPStatus.OK,
                archive_path.read_bytes(),
                content_type="application/gzip",
                filename=str(metadata.get("stored_filename") or archive_path.name),
            )
            return
        if path.startswith("/api/v1/vms/"):
            match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/installer\.sh$", path)
            if match:
                vm = find_vm(int(match.group("vmid")))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                try:
                    body, filename = render_vm_installer_script(vm)
                except FileNotFoundError as exc:
                    self._write_json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": str(exc)})
                    return
                except ValueError as exc:
                    self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                    return
                self._write_bytes(
                    HTTPStatus.OK,
                    body,
                    content_type="text/x-shellscript; charset=utf-8",
                    filename=filename,
                )
                return
            if path.endswith("/installer.sh"):
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/live-usb\.sh$", path)
            if match:
                vm = find_vm(int(match.group("vmid")))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                try:
                    body, filename = render_vm_live_usb_script(vm)
                except FileNotFoundError as exc:
                    self._write_json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": str(exc)})
                    return
                except ValueError as exc:
                    self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                    return
                self._write_bytes(
                    HTTPStatus.OK,
                    body,
                    content_type="text/x-shellscript; charset=utf-8",
                    filename=filename,
                )
                return
            if path.endswith("/live-usb.sh"):
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/installer\.ps1$", path)
            if match:
                vm = find_vm(int(match.group("vmid")))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                try:
                    body, filename = render_vm_windows_installer_script(vm)
                except FileNotFoundError as exc:
                    self._write_json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": str(exc)})
                    return
                except ValueError as exc:
                    self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                    return
                self._write_bytes(
                    HTTPStatus.OK,
                    body,
                    content_type="text/plain; charset=utf-8",
                    filename=filename,
                )
                return
            if path.endswith("/installer.ps1"):
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            if path.endswith("/credentials"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vm = find_vm(int(vmid_text))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                secret = ensure_vm_secret(vm)
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "credentials": {
                            "vmid": vm.vmid,
                            "node": vm.node,
                            "thinclient_username": "thinclient",
                            "thinclient_password": str(secret.get("thinclient_password", "")),
                            "sunshine_username": str(secret.get("sunshine_username", "")),
                            "sunshine_password": str(secret.get("sunshine_password", "")),
                            "sunshine_pin": str(secret.get("sunshine_pin", "")),
                            "usb_tunnel_host": PUBLIC_SERVER_NAME,
                            "usb_tunnel_user": USB_TUNNEL_SSH_USER,
                            "usb_tunnel_port": int(secret.get("usb_tunnel_port", 0) or 0),
                        },
                    },
                )
                return
            if path.endswith("/installer-prep"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vm = find_vm(int(vmid_text))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                state = summarize_installer_prep_state(vm, load_installer_prep_state(vm.node, vm.vmid))
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "installer_prep": state,
                    },
                )
                return
            if path.endswith("/policy"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vm = find_vm(int(vmid_text))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                profile = build_profile(vm)
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "applied_policy": profile.get("applied_policy"),
                        "assignment_source": profile.get("assignment_source", ""),
                    },
                )
                return
            if path.endswith("/support-bundles"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vm = find_vm(int(vmid_text))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "support_bundles": list_support_bundle_metadata(node=vm.node, vmid=vm.vmid),
                    },
                )
                return
            if path.endswith("/usb"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vm = find_vm(int(vmid_text))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                report = load_endpoint_report(vm.node, vm.vmid)
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "usb": build_vm_usb_state(vm, report),
                    },
                )
                return
            if path.endswith("/state"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                state = self._vm_state_for_vmid(int(vmid_text))
                if state is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        **state,
                    },
                )
                return
            if path.endswith("/actions"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vmid = int(vmid_text)
                state = self._vm_state_for_vmid(vmid)
                if state is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                vm = find_vm(vmid)
                assert vm is not None
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "pending_actions": load_action_queue(vm.node, vm.vmid),
                        "last_action": state["last_action"],
                    },
                )
                return
            if path.endswith("/endpoint"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                state = self._vm_state_for_vmid(int(vmid_text))
                if state is None or not state["endpoint"].get("reported_at"):
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "endpoint not found"})
                    return
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        **state,
                    },
                )
                return
            vmid_text = path.rsplit("/", 1)[-1]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vmid = int(vmid_text)
            vm = next((candidate for candidate in list_vms() if candidate.vmid == vmid), None)
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "profile": build_profile(vm),
                },
            )
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query or "")

        if path.startswith("/api/v1/public/sunshine/"):
            vm, relative = self._sunshine_ticket_vm(parsed.path)
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "sunshine ticket not found"})
                return
            try:
                body = self._read_binary_body(max_bytes=16 * 1024 * 1024)
                status_code, headers, response_body = proxy_sunshine_request(
                    vm,
                    request_path=relative,
                    query=parsed.query,
                    method="POST",
                    body=body,
                    request_headers={
                        "Content-Type": self.headers.get("Content-Type", ""),
                        "Accept": self.headers.get("Accept", ""),
                    },
                )
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"sunshine proxy failed: {exc}"})
                return
            self._write_proxy_response(status_code, headers, response_body)
            return

        if path == "/api/v1/endpoints/enroll":
            try:
                payload = self._read_json_body()
                enrollment_token = str(payload.get("enrollment_token", "")).strip()
                endpoint_id = str(payload.get("endpoint_id", "")).strip() or str(payload.get("hostname", "")).strip()
                if not enrollment_token or not endpoint_id:
                    raise ValueError("missing enrollment_token or endpoint_id")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            enrollment = load_enrollment_token(enrollment_token)
            if not enrollment_token_is_valid(enrollment, endpoint_id=endpoint_id):
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "invalid or expired enrollment token"})
                return
            vm = find_vm(int(enrollment.get("vmid", 0)))
            if vm is None or vm.node != str(enrollment.get("node", "")).strip():
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            profile = build_profile(vm)
            secret = ensure_vm_secret(vm)
            sunshine_pinned_pubkey = fetch_https_pinned_pubkey(internal_sunshine_api_url(vm, profile))
            if sunshine_pinned_pubkey and sunshine_pinned_pubkey != str(secret.get("sunshine_pinned_pubkey", "")):
                secret["sunshine_pinned_pubkey"] = sunshine_pinned_pubkey
                secret = save_vm_secret(vm.node, vm.vmid, secret)
            endpoint_token = secrets.token_urlsafe(32)
            endpoint_payload = store_endpoint_token(
                endpoint_token,
                {
                    "endpoint_id": endpoint_id,
                    "hostname": str(payload.get("hostname", "")).strip(),
                    "vmid": vm.vmid,
                    "node": vm.node,
                },
            )
            mark_enrollment_token_used(enrollment_token, enrollment, endpoint_id=endpoint_id)
            self._write_json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "endpoint": endpoint_payload,
                    "config": {
                        "beagle_manager_url": PUBLIC_MANAGER_URL,
                        "beagle_manager_token": endpoint_token,
                        "beagle_manager_pinned_pubkey": MANAGER_PINNED_PUBKEY,
                        "sunshine_api_url": str(profile.get("sunshine_api_url", "") or ""),
                        "sunshine_username": str(secret.get("sunshine_username", "")),
                        "sunshine_password": str(secret.get("sunshine_password", "")),
                        "sunshine_pin": str(secret.get("sunshine_pin", "")),
                        "sunshine_pinned_pubkey": str(secret.get("sunshine_pinned_pubkey", "")),
                        "usb_enabled": True,
                        "usb_tunnel_host": PUBLIC_SERVER_NAME,
                        "usb_tunnel_user": USB_TUNNEL_SSH_USER,
                        "usb_tunnel_port": int(secret.get("usb_tunnel_port", 0) or 0),
                        "usb_tunnel_attach_host": USB_TUNNEL_ATTACH_HOST,
                        "usb_tunnel_private_key": str(secret.get("usb_tunnel_private_key", "")),
                        "usb_tunnel_known_host": usb_tunnel_known_host_line(),
                        "moonlight_host": str(profile.get("stream_host", "") or ""),
                        "moonlight_port": str(profile.get("moonlight_port", "") or ""),
                        "moonlight_app": str(profile.get("moonlight_app", "Desktop") or "Desktop"),
                        "egress_mode": str(profile.get("egress_mode", "direct") or "direct"),
                        "egress_type": str(profile.get("egress_type", "") or ""),
                        "egress_interface": str(profile.get("egress_interface", "beagle-egress") or "beagle-egress"),
                        "egress_domains": list(profile.get("egress_domains", []) or []),
                        "egress_resolvers": list(profile.get("egress_resolvers", []) or []),
                        "egress_allowed_ips": list(profile.get("egress_allowed_ips", []) or []),
                        "egress_wg_address": str(profile.get("egress_wg_address", "") or ""),
                        "egress_wg_dns": str(profile.get("egress_wg_dns", "") or ""),
                        "egress_wg_public_key": str(profile.get("egress_wg_public_key", "") or ""),
                        "egress_wg_endpoint": str(profile.get("egress_wg_endpoint", "") or ""),
                        "egress_wg_private_key": str(profile.get("egress_wg_private_key", "") or ""),
                        "egress_wg_preshared_key": str(profile.get("egress_wg_preshared_key", "") or ""),
                        "egress_wg_persistent_keepalive": str(profile.get("egress_wg_persistent_keepalive", "25") or "25"),
                        "identity_hostname": str(profile.get("identity_hostname", "") or ""),
                        "identity_timezone": str(profile.get("identity_timezone", "") or ""),
                        "identity_locale": str(profile.get("identity_locale", "") or ""),
                        "identity_keymap": str(profile.get("identity_keymap", "") or ""),
                        "identity_chrome_profile": str(profile.get("identity_chrome_profile", "") or ""),
                    },
                },
            )
            return

        if path == "/api/v1/endpoints/moonlight/register":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            identity = self._endpoint_identity() or {}
            vmid = int(identity.get("vmid", 0) or 0)
            vm = find_vm(vmid)
            if vm is None or str(identity.get("node", "")).strip() != vm.node:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            try:
                payload = self._read_json_body()
                client_cert_pem = str(payload.get("client_cert_pem", "")).strip()
                device_name = (
                    str(payload.get("device_name", "")).strip()
                    or str(identity.get("hostname", "")).strip()
                    or f"beagle-vm{vmid}-client"
                )
                if not client_cert_pem or "BEGIN CERTIFICATE" not in client_cert_pem:
                    raise ValueError("missing client certificate")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            result = register_moonlight_certificate_on_vm(vm, client_cert_pem, device_name=device_name)
            guest_user = str(result.get("guest_user", "") or "").strip()
            sunshine_server: dict[str, Any] = {
                "ok": False,
                "uniqueid": "",
                "server_cert_pem": "",
                "sunshine_name": "",
                "stream_port": "",
                "stdout": "",
                "stderr": "",
            }
            if bool(result.get("ok")) and guest_user:
                sunshine_server = fetch_sunshine_server_identity(vm, guest_user)
            overall_ok = bool(result.get("ok")) and bool(sunshine_server.get("ok")) and bool(
                sunshine_server.get("uniqueid")
            ) and bool(sunshine_server.get("server_cert_pem"))
            self._write_json(
                HTTPStatus.CREATED if overall_ok else HTTPStatus.BAD_GATEWAY,
                {
                    "ok": overall_ok,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "vmid": vm.vmid,
                    "node": vm.node,
                    "device_name": device_name,
                    "guest_user": result.get("guest_user", ""),
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "sunshine_server": {
                        "ok": bool(sunshine_server.get("ok")),
                        "uniqueid": sunshine_server.get("uniqueid", ""),
                        "server_cert_pem": sunshine_server.get("server_cert_pem", ""),
                        "sunshine_name": sunshine_server.get("sunshine_name", ""),
                        "stream_port": sunshine_server.get("stream_port", ""),
                        "stdout": sunshine_server.get("stdout", ""),
                        "stderr": sunshine_server.get("stderr", ""),
                    },
                },
            )
            return

        if path == "/api/v1/endpoints/actions/pull":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            identity = self._endpoint_identity() or {}
            try:
                payload = self._read_json_body()
                vmid = int(payload.get("vmid"))
                node = str(payload.get("node", "")).strip()
                if not node:
                    raise ValueError("missing node")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            if identity and (int(identity.get("vmid", -1)) != vmid or str(identity.get("node", "")).strip() != node):
                self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
                return
            actions = dequeue_vm_actions(node, vmid)
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "actions": actions,
                },
            )
            return

        if path == "/api/v1/endpoints/actions/result":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            identity = self._endpoint_identity() or {}
            try:
                payload = self._read_json_body()
                vmid = int(payload.get("vmid"))
                node = str(payload.get("node", "")).strip()
                action_name = str(payload.get("action", "")).strip()
                action_id = str(payload.get("action_id", "")).strip()
                if not node or not action_name or not action_id:
                    raise ValueError("missing action result fields")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            if identity and (int(identity.get("vmid", -1)) != vmid or str(identity.get("node", "")).strip() != node):
                self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
                return

            payload["vmid"] = vmid
            payload["node"] = node
            payload["received_at"] = utcnow()
            store_action_result(node, vmid, payload)
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "last_action": summarize_action_result(payload),
                },
            )
            return

        if path == "/api/v1/policies":
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                payload = self._read_json_body()
                policy = save_policy(payload)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid policy: {exc}"})
                return
            self._write_json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "policy": policy,
                },
            )
            return

        if path == "/api/v1/actions/bulk":
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                payload = self._read_json_body()
                action_name = str(payload.get("action", "")).strip().lower()
                vmid_values = payload.get("vmids", [])
                if action_name not in {"healthcheck", "recheckin", "restart-session", "restart-runtime", "support-bundle"}:
                    raise ValueError("unsupported action")
                if not isinstance(vmid_values, list) or not vmid_values:
                    raise ValueError("missing vmids")
                vmids = [int(item) for item in vmid_values]
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid bulk action: {exc}"})
                return
            queued = queue_bulk_actions(vmids, action_name, self._requester_identity())
            self._write_json(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "queued_actions": queued,
                    "queued_count": len(queued),
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/installer-prep"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            try:
                state = start_installer_prep(vm)
            except Exception as exc:
                self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": f"failed to start installer prep: {exc}"})
                return
            status = HTTPStatus.ACCEPTED if str(state.get("status", "")).lower() == "running" else HTTPStatus.OK
            self._write_json(
                status,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "installer_prep": state,
                },
            )
            return

        if path == "/api/v1/endpoints/support-bundles/upload":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            identity = self._endpoint_identity() or {}
            try:
                vmid_values = query.get("vmid", [])
                node_values = query.get("node", [])
                action_values = query.get("action_id", [])
                filename_values = query.get("filename", [])
                vmid = int(vmid_values[0])
                node = str(node_values[0]).strip()
                action_id = str(action_values[0]).strip()
                filename = str(filename_values[0]).strip() or "support-bundle.tar.gz"
                if not node or not action_id:
                    raise ValueError("missing upload fields")
                payload = self._read_binary_body(max_bytes=128 * 1024 * 1024)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid upload: {exc}"})
                return
            if identity and (int(identity.get("vmid", -1)) != vmid or str(identity.get("node", "")).strip() != node):
                self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
                return
            bundle = store_support_bundle(node, vmid, action_id, filename, payload)
            self._write_json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "support_bundle": bundle,
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/actions"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            try:
                payload = self._read_json_body()
                action_name = str(payload.get("action", "")).strip().lower()
                if action_name not in {"healthcheck", "recheckin", "restart-session", "restart-runtime", "support-bundle"}:
                    raise ValueError("unsupported action")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            queued = queue_vm_action(vm, action_name, self._requester_identity())
            self._write_json(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "queued_action": queued,
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/usb/refresh"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-3]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            queued = queue_vm_action(vm, "usb-refresh", self._requester_identity())
            self._write_json(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "queued_action": queued,
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/usb/attach"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-3]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            try:
                payload = self._read_json_body()
                busid = str(payload.get("busid", "")).strip()
                if not busid:
                    raise ValueError("missing busid")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            queued = queue_vm_action(vm, "usb-bind", self._requester_identity(), {"busid": busid})
            result = wait_for_action_result(vm.node, vm.vmid, queued["action_id"], timeout_seconds=USB_ACTION_WAIT_SECONDS)
            if result is None:
                self._write_json(
                    HTTPStatus.ACCEPTED,
                    {
                        "ok": True,
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "queued_action": queued,
                        "message": "USB export queued on endpoint; refresh in a few seconds.",
                    },
                )
                return
            if not bool(result.get("ok")):
                self._write_json(
                    HTTPStatus.CONFLICT,
                    {
                        "ok": False,
                        "error": str(result.get("message", "") or "endpoint usb export failed"),
                        "queued_action": queued,
                        "endpoint_result": summarize_action_result(result),
                    },
                )
                return
            try:
                attach_result = attach_usb_to_guest(vm, busid)
            except Exception as exc:
                message = str(exc)
                if "Device busy (exported)" in message:
                    retry = queue_vm_action(vm, "usb-bind", self._requester_identity(), {"busid": busid})
                    retry_result = wait_for_action_result(vm.node, vm.vmid, retry["action_id"], timeout_seconds=USB_ACTION_WAIT_SECONDS)
                    if retry_result is not None and bool(retry_result.get("ok")):
                        try:
                            attach_result = attach_usb_to_guest(vm, busid)
                        except Exception as retry_exc:
                            message = str(retry_exc)
                        else:
                            self._write_json(
                                HTTPStatus.OK,
                                {
                                    "ok": True,
                                    "service": "beagle-control-plane",
                                    "version": VERSION,
                                    "generated_at": utcnow(),
                                    "queued_action": queued,
                                    "endpoint_result": summarize_action_result(result),
                                    "retry_action": retry,
                                    "retry_endpoint_result": summarize_action_result(retry_result),
                                    "attach_result": attach_result,
                                },
                            )
                            return
                self._write_json(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": f"guest usb attach failed: {message}",
                        "queued_action": queued,
                        "endpoint_result": summarize_action_result(result),
                    },
                )
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "queued_action": queued,
                    "endpoint_result": summarize_action_result(result),
                    "guest_attach": attach_result,
                    "usb": build_vm_usb_state(vm),
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/usb/detach"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-3]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            try:
                payload = self._read_json_body()
                busid = str(payload.get("busid", "")).strip()
                port_value = payload.get("port")
                port = int(port_value) if port_value is not None and str(port_value).strip() else None
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            try:
                detach_result = detach_usb_from_guest(vm, port=port, busid=busid)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"guest usb detach failed: {exc}"})
                return
            queued = None
            endpoint_result = None
            if busid:
                queued = queue_vm_action(vm, "usb-unbind", self._requester_identity(), {"busid": busid})
                endpoint_result = wait_for_action_result(vm.node, vm.vmid, queued["action_id"], timeout_seconds=USB_ACTION_WAIT_SECONDS)
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "guest_detach": detach_result,
                    "queued_action": queued,
                    "endpoint_result": summarize_action_result(endpoint_result),
                    "usb": build_vm_usb_state(vm),
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/sunshine-access"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            token, payload = issue_sunshine_access_token(vm)
            self._write_json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "sunshine_access": {
                        **payload,
                        "url": sunshine_proxy_ticket_url(token),
                    },
                },
            )
            return

        if path != "/api/v1/endpoints/check-in":
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        if not self._is_endpoint_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        identity = self._endpoint_identity() or {}

        try:
            payload = self._read_json_body()
            vmid = int(payload.get("vmid"))
            node = str(payload.get("node", "")).strip()
            if not node:
                raise ValueError("missing node")
        except Exception as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
            return
        if identity and (int(identity.get("vmid", -1)) != vmid or str(identity.get("node", "")).strip() != node):
            self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
            return

        payload["vmid"] = vmid
        payload["node"] = node
        payload["received_at"] = utcnow()
        payload["remote_addr"] = self.client_address[0]

        path_obj = endpoint_report_path(node, vmid)
        path_obj.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self._write_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "service": "beagle-control-plane",
                "version": VERSION,
                "stored_at": str(path_obj),
                "endpoint": summarize_endpoint_report(payload),
            },
        )

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if not path.startswith("/api/v1/policies/"):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        policy_name = path.rsplit("/", 1)[-1]
        try:
            payload = self._read_json_body()
            policy = save_policy(payload, policy_name=policy_name)
        except Exception as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid policy: {exc}"})
            return
        self._write_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "service": "beagle-control-plane",
                "version": VERSION,
                "generated_at": utcnow(),
                "policy": policy,
            },
        )

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if not path.startswith("/api/v1/policies/"):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        policy_name = path.rsplit("/", 1)[-1]
        if not delete_policy(policy_name):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "policy not found"})
            return
        self._write_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "service": "beagle-control-plane",
                "version": VERSION,
                "generated_at": utcnow(),
                "deleted": policy_name,
            },
        )

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{utcnow()}] {self.address_string()} {fmt % args}", flush=True)


def main() -> int:
    global EFFECTIVE_DATA_DIR
    EFFECTIVE_DATA_DIR = ensure_data_dir()
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(
        json.dumps(
            {
                "service": "beagle-control-plane",
                "version": VERSION,
                "listen_host": LISTEN_HOST,
                "listen_port": LISTEN_PORT,
                "allow_localhost_noauth": ALLOW_LOCALHOST_NOAUTH,
                "data_dir": str(EFFECTIVE_DATA_DIR),
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
