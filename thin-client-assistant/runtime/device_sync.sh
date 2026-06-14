#!/usr/bin/env bash

SCRIPT_DIR="${RUNTIME_SCRIPT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
if [[ "$SCRIPT_DIR" == /var/local/* ]]; then
  SCRIPT_DIR="/usr/local/${SCRIPT_DIR#/var/local/}"
fi
COMMON_SH="${COMMON_SH:-$SCRIPT_DIR/common.sh}"
RUNTIME_ENDPOINT_ENROLLMENT_SH="${RUNTIME_ENDPOINT_ENROLLMENT_SH:-$SCRIPT_DIR/runtime_endpoint_enrollment.sh}"

if [[ -r "$COMMON_SH" ]]; then
  # shellcheck disable=SC1090
  source "$COMMON_SH"
fi
if [[ -r "$RUNTIME_ENDPOINT_ENROLLMENT_SH" ]]; then
  # shellcheck disable=SC1090
  source "$RUNTIME_ENDPOINT_ENROLLMENT_SH"
fi

runtime_manager_sync_url() {
  local manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  [[ -n "$manager_url" ]] || return 1
  printf '%s/api/v1/endpoints/device/sync\n' "${manager_url%/}"
}

runtime_manager_confirm_wiped_url() {
  local manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  [[ -n "$manager_url" ]] || return 1
  printf '%s/api/v1/endpoints/device/confirm-wiped\n' "${manager_url%/}"
}

runtime_device_id() {
  local configured="${PVE_THIN_CLIENT_BEAGLE_DEVICE_ID:-}"
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi
  runtime_endpoint_id
}

runtime_os_version() {
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    printf '%s\n' "${PRETTY_NAME:-${VERSION_ID:-unknown}}"
    return 0
  fi
  printf '%s\n' "unknown"
}

runtime_cpu_model() {
  awk -F: '/model name/ {gsub(/^[ \t]+/, "", $2); print $2; exit}' /proc/cpuinfo 2>/dev/null || true
}

runtime_ram_gb() {
  awk '/MemTotal:/ {printf "%d\n", ($2 + 1024*1024 - 1) / (1024*1024); exit}' /proc/meminfo 2>/dev/null || printf '0\n'
}

runtime_gpu_model() {
  if command -v lspci >/dev/null 2>&1; then
    lspci 2>/dev/null | awk -F': ' '/VGA compatible controller|3D controller|Display controller/ {print $2; exit}' || true
    return 0
  fi
  printf '%s\n' ""
}

runtime_network_interfaces_json() {
  if command -v ip >/dev/null 2>&1; then
    ip -o link show 2>/dev/null | awk -F': ' '{print $2}' | cut -d@ -f1 | grep -v '^lo$' | python3 -c 'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))'
    return 0
  fi
  printf '[]\n'
}

runtime_wireguard_active() {
  local iface="${1:-wg-beagle}"
  ip link show "$iface" >/dev/null 2>&1
}

runtime_wireguard_ip() {
  local iface="${1:-wg-beagle}"
  ip -o -4 addr show dev "$iface" 2>/dev/null | awk '{print $4; exit}' || true
}

runtime_boot_id() {
  cat /proc/sys/kernel/random/boot_id 2>/dev/null || true
}

runtime_boot_history_file_path() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s/runtime-boot-history.json\n' "$state_dir"
}

runtime_record_boot_occurrence() {
  local history_file boot_id now_value
  history_file="$(runtime_boot_history_file_path)"
  boot_id="$(runtime_boot_id)"
  now_value="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || true)"
  [[ -n "$boot_id" && -n "$now_value" ]] || return 0
  mkdir -p "$(dirname "$history_file")" >/dev/null 2>&1 || true
  python3 - "$history_file" "$boot_id" "$now_value" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

path = Path(sys.argv[1])
boot_id = sys.argv[2].strip()
now_value = datetime.fromisoformat(sys.argv[3].replace("Z", "+00:00"))
payload = {"entries": []}
if path.exists():
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload = loaded
    except Exception:
        payload = {"entries": []}
entries = payload.get("entries")
if not isinstance(entries, list):
    entries = []
cutoff = now_value - timedelta(days=7)
filtered = []
seen = False
for item in entries:
    if not isinstance(item, dict):
        continue
    item_boot_id = str(item.get("boot_id") or "").strip()
    item_seen_at = str(item.get("seen_at") or "").strip()
    try:
        seen_at = datetime.fromisoformat(item_seen_at.replace("Z", "+00:00"))
    except ValueError:
        continue
    if seen_at < cutoff:
        continue
    if item_boot_id == boot_id:
        filtered.append({"boot_id": boot_id, "seen_at": now_value.strftime("%Y-%m-%dT%H:%M:%SZ")})
        seen = True
    else:
        filtered.append({"boot_id": item_boot_id, "seen_at": seen_at.strftime("%Y-%m-%dT%H:%M:%SZ")})
if not seen:
    filtered.append({"boot_id": boot_id, "seen_at": now_value.strftime("%Y-%m-%dT%H:%M:%SZ")})
payload["entries"] = filtered[-32:]
path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
}

runtime_boot_count_7d() {
  local history_file
  history_file="$(runtime_boot_history_file_path)"
  [[ -r "$history_file" ]] || {
    printf '1\n'
    return 0
  }
  python3 - "$history_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
entries = payload.get("entries")
if not isinstance(entries, list):
    entries = []
print(max(1, len(entries)))
PY
}

runtime_uptime_hours() {
  LC_NUMERIC=C awk '{printf "%.2f\n", $1 / 3600.0}' /proc/uptime 2>/dev/null || printf '0\n'
}

runtime_cpu_temp_c() {
  python3 - <<'PY'
from pathlib import Path

values = []
for path in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
    try:
        raw = path.read_text(encoding="utf-8").strip()
        value = float(raw)
        if value > 1000:
            value /= 1000.0
        if value > 0:
            values.append(value)
    except Exception:
        pass
print(f"{max(values) if values else 0.0:.1f}")
PY
}

runtime_network_errors() {
  python3 - <<'PY'
from pathlib import Path

total = 0
for base in Path("/sys/class/net").iterdir():
    if base.name == "lo":
        continue
    for field in ("rx_errors", "tx_errors"):
        try:
            total += int((base / "statistics" / field).read_text(encoding="utf-8").strip())
        except Exception:
            pass
print(total)
PY
}

runtime_device_log_bundle_json() {
  local state_dir enabled update_env_file
  state_dir="$(beagle_state_dir)"
  update_env_file="$state_dir/device-updates.env"
  enabled="${PVE_THIN_CLIENT_BEAGLE_LOG_CAPTURE_ENABLED:-1}"
  if [[ -z "${PVE_THIN_CLIENT_BEAGLE_LOG_CAPTURE_ENABLED+x}" && -r "$update_env_file" ]]; then
    enabled="$(python3 - "$update_env_file" <<'PY'
import sys
from pathlib import Path

value = ""
for line in Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if not line.startswith("export PVE_THIN_CLIENT_BEAGLE_LOG_CAPTURE_ENABLED="):
        continue
    value = line.split("=", 1)[1].strip().strip("'\"")
    break
print(value)
PY
)"
  fi
  [[ -n "$enabled" ]] || enabled="1"
  python3 - "$state_dir" "$enabled" <<'PY'
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

state_dir = Path(sys.argv[1])
enabled = str(sys.argv[2] or "1").strip().lower() not in {"0", "false", "no", "off"}
if not enabled:
  print(json.dumps({"captured_at": "", "entries": []}))
  raise SystemExit(0)

captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
entries: list[dict[str, str]] = []

def add_entry(source: str, level: str, content: str) -> None:
  text = str(content or "").strip()
  if text:
    entries.append({"source": source, "level": level, "captured_at": captured_at, "content": text})

def tail_text(path: Path, *, lines: int = 40) -> str:
  if not path.exists():
    return ""
  try:
    items = path.read_text(encoding="utf-8", errors="replace").splitlines()
  except Exception:
    return ""
  return "\n".join(items[-lines:])

add_entry("runtime-heartbeat.status", "info", tail_text(state_dir / "runtime-heartbeat.status", lines=80))
add_entry("runtime-trace.log", "info", tail_text(state_dir / "runtime-trace.log", lines=80))

journalctl = shutil.which("journalctl")
if journalctl:
  journal_specs = [
    ("journal:beagle-runtime", [journalctl, "-b", "--no-pager", "-o", "short-iso", "-u", "beagle-runtime-heartbeat", "-u", "beagle-usb-tunnel", "-u", "beagle-kiosk", "-u", "pve-thin-client-runtime", "-u", "pve-thin-client-prepare"], "info"),
    ("journal:kernel", [journalctl, "-k", "-b", "--no-pager", "-o", "short-iso"], "warn"),
    ("journal:warnings", [journalctl, "-b", "--no-pager", "-p", "warning..alert", "-o", "short-iso"], "warn"),
  ]
  for source, command, level in journal_specs:
    try:
      result = subprocess.run(command, check=False, text=True, capture_output=True)
    except Exception:
      continue
    text = (result.stdout or "").strip()
    if not text:
      continue
    lines = text.splitlines()
    add_entry(source, level, "\n".join(lines[-60:]))

print(json.dumps({"captured_at": captured_at, "entries": entries}))
PY
}

runtime_usb_tunnel_public_key() {
  local key_path="${PVE_THIN_CLIENT_USB_TUNNEL_KEY_PATH:-/etc/pve-thin-client/usb-tunnel.key}"
  if [[ ! -r "$key_path" ]] || ! command -v ssh-keygen >/dev/null 2>&1; then
    printf '\n'
    return 0
  fi
  ssh-keygen -y -f "$key_path" 2>/dev/null | head -n 1 | tr -d '\r' || true
}

runtime_wipe_report_file_path() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s/device-wipe-report.json\n' "$state_dir"
}

runtime_wipe_report_json() {
  local wipe_report_file
  wipe_report_file="${1:-$(runtime_wipe_report_file_path)}"
  if [[ -r "$wipe_report_file" ]]; then
    python3 - "$wipe_report_file" <<'PY'
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
if not isinstance(payload, dict):
    payload = {}
print(json.dumps(payload))
PY
    return 0
  fi
  printf '{}\n'
}

runtime_lock_state_file_path() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s/device.locked\n' "$state_dir"
}

runtime_lock_marker_file_path() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s/device-lock-screen.marker\n' "$state_dir"
}

runtime_lock_pid_file_path() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s/device-lock-screen.pid\n' "$state_dir"
}

runtime_lock_info_file_path() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s/device-lock-screen.env\n' "$state_dir"
}

runtime_display_list_json() {
  local configured primary
  configured="${BEAGLE_LOCK_SCREEN_X11_DISPLAYS:-}"
  primary="${DISPLAY:-:0}"
  python3 - "$configured" "$primary" <<'PY'
import json
import sys

configured = sys.argv[1].strip()
primary = sys.argv[2].strip() or ":0"
items = []
if configured:
    items = [part.strip() for part in configured.replace(",", "\n").splitlines() if part.strip()]
if not items:
    items = [primary]
print(json.dumps(items))
PY
}

runtime_report_json() {
  local lock_active lock_marker lock_pid session_type backend displays_json info_file stream_active stream_pid stream_started stream_host stream_port stream_app stream_vmid stream_profile_json profile_override_env
  if [[ -f "$(runtime_lock_state_file_path)" ]]; then
    lock_active=1
  else
    lock_active=0
  fi
  if [[ -f "$(runtime_lock_marker_file_path)" ]]; then
    lock_marker=1
  else
    lock_marker=0
  fi
  if [[ -f "$(runtime_lock_pid_file_path)" ]]; then
    lock_pid=1
  else
    lock_pid=0
  fi
  session_type="${XDG_SESSION_TYPE:-x11}"
  backend="unknown"
  displays_json="$(runtime_display_list_json)"
  info_file="$(runtime_lock_info_file_path)"
  if [[ -r "$info_file" ]]; then
    # shellcheck disable=SC1090
    source "$info_file"
    session_type="${BEAGLE_LOCK_SCREEN_RUNTIME_SESSION_TYPE:-$session_type}"
    backend="${BEAGLE_LOCK_SCREEN_RUNTIME_BACKEND:-$backend}"
    if [[ -n "${BEAGLE_LOCK_SCREEN_RUNTIME_DISPLAYS:-}" ]]; then
      displays_json="$(python3 - "${BEAGLE_LOCK_SCREEN_RUNTIME_DISPLAYS}" <<'PY'
import json
import sys

print(json.dumps([part.strip() for part in sys.argv[1].split(",") if part.strip()]))
PY
)"
    fi
  fi
  profile_override_env="${BEAGLE_STREAM_PROFILE_OVERRIDE_ENV:-$(beagle_state_dir)/stream-profile.env}"
  if [[ -r "$profile_override_env" ]]; then
    # shellcheck disable=SC1090
    source "$profile_override_env"
  fi
  if pgrep -x beagle-stream >/dev/null 2>&1 || pgrep -x beagle-stream-client >/dev/null 2>&1; then
    stream_active=1
    stream_pid="$(pgrep -xo beagle-stream 2>/dev/null || pgrep -xo beagle-stream-client 2>/dev/null || true)"
  else
    stream_active=0
    stream_pid=""
  fi
  stream_started=""
  if [[ -n "$stream_pid" && -r "/proc/$stream_pid/stat" ]]; then
    stream_started="$(awk '{print $22}' "/proc/$stream_pid/stat" 2>/dev/null || true)"
  fi
  stream_host="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST:-${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BROKER_HOST:-}}"
  stream_port="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PORT:-${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_STREAM_PORT:-}}"
  stream_app="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_APP:-Desktop}"
  stream_vmid="${PVE_THIN_CLIENT_BEAGLE_VMID:-${PVE_THIN_CLIENT_PRESET_BEAGLE_VMID:-0}}"
  stream_profile_json="$(python3 - <<'PY'
import json
import os

def env(name, default=""):
    return str(os.environ.get(name, default) or default)

def as_int(name, default):
    try:
        return int(env(name, str(default)))
    except ValueError:
        return default

payload = {
    "preset": env("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PRESET", ""),
    "resolution": env("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESOLUTION", "auto"),
    "fps": as_int("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS", 60),
    "bitrate": as_int("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE", 32000),
    "packet_size": as_int("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PACKET_SIZE", 0),
    "video_codec": env("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_CODEC", "H.264"),
    "video_decoder": env("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_DECODER", "auto"),
    "audio_config": env("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUDIO_CONFIG", "stereo"),
    "frame_pacing": env("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FRAME_PACING", "") == "1",
    "vsync": env("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VSYNC", "") == "1",
}
print(json.dumps(payload))
PY
)"

  python3 - "$lock_active" "$lock_marker" "$lock_pid" "$session_type" "$backend" "$displays_json" "$stream_active" "$stream_pid" "$stream_started" "$stream_host" "$stream_port" "$stream_app" "$stream_vmid" "$stream_profile_json" <<'PY'
import json
import sys
profile = json.loads(sys.argv[14] or "{}")

payload = {
    "lock_active": sys.argv[1] == "1",
    "lock_marker_present": sys.argv[2] == "1",
    "lock_watcher_pid_present": sys.argv[3] == "1",
    "session_type": sys.argv[4],
    "lock_screen_backend": sys.argv[5],
    "x11_displays": json.loads(sys.argv[6] or "[]"),
    "stream": {
      "active": sys.argv[7] == "1",
      "pid": int(sys.argv[8] or "0"),
      "started_at": sys.argv[9],
      "host": sys.argv[10],
      "port": sys.argv[11],
      "app": sys.argv[12] or "Desktop",
      "vmid": int(sys.argv[13] or "0"),
      "profile": profile,
      "health": {
        "fps": profile.get("fps") if isinstance(profile, dict) else None,
      },
    },
}
print(json.dumps(payload))
PY
}

runtime_device_sync_payload() {
  local device_id="${1:-}"
  local hostname_value="${2:-}"
  local wg_iface="${3:-wg-beagle}"
  local wg_active="${4:-0}"
  local wg_ip="${5:-}"
  local wipe_report_json runtime_report_json logs_json interfaces_json cpu_model cpu_cores ram_gb gpu_model os_version
  local uptime_hours reboot_count_7d cpu_temp_c network_errors usb_tunnel_public_key

  wipe_report_json="$(runtime_wipe_report_json)"
  runtime_report_json="$(runtime_report_json)"
  logs_json="$(runtime_device_log_bundle_json)"
  interfaces_json="$(runtime_network_interfaces_json)"
  cpu_model="$(runtime_cpu_model)"
  cpu_cores="$(nproc 2>/dev/null || printf '0')"
  ram_gb="$(runtime_ram_gb)"
  gpu_model="$(runtime_gpu_model)"
  os_version="$(runtime_os_version)"
  uptime_hours="$(runtime_uptime_hours)"
  reboot_count_7d="$(runtime_boot_count_7d)"
  cpu_temp_c="$(runtime_cpu_temp_c)"
  network_errors="$(runtime_network_errors)"
  usb_tunnel_public_key="$(runtime_usb_tunnel_public_key)"

  python3 - "$device_id" "$hostname_value" "$os_version" "$cpu_model" "$cpu_cores" "$ram_gb" "$gpu_model" "$interfaces_json" "$wg_iface" "$wg_active" "$wg_ip" "$wipe_report_json" "$runtime_report_json" "$uptime_hours" "$reboot_count_7d" "$cpu_temp_c" "$network_errors" "$usb_tunnel_public_key" "$logs_json" <<'PY'
import json, sys
runtime_report = json.loads(sys.argv[13] or "{}")
stream_report = runtime_report.get("stream") if isinstance(runtime_report, dict) else {}
streaming_active = bool(stream_report.get("active")) if isinstance(stream_report, dict) else False
logs_bundle = json.loads(sys.argv[19] or "{}")
log_entries = logs_bundle.get("entries") if isinstance(logs_bundle, dict) else []
if not isinstance(log_entries, list):
    log_entries = []

payload = {
    "device_id": sys.argv[1],
    "hostname": sys.argv[2],
    "os_version": sys.argv[3],
    "hardware": {
        "cpu_model": sys.argv[4],
        "cpu_cores": int(sys.argv[5] or "0"),
        "ram_gb": int(sys.argv[6] or "0"),
        "gpu_model": sys.argv[7],
        "network_interfaces": json.loads(sys.argv[8] or "[]"),
        "disk_gb": 0,
    },
    "vpn": {
        "interface": sys.argv[9],
        "active": sys.argv[10] == "1",
        "assigned_ip": sys.argv[11],
    },
    "metrics": {
      "streaming_active": streaming_active,
        "uptime_hours": float(sys.argv[14] or "0"),
        "reboot_count_7d": int(float(sys.argv[15] or "0")),
        "cpu_temp_c": float(sys.argv[16] or "0"),
        "gpu_temp_c": 0.0,
        "network_errors": int(float(sys.argv[17] or "0")),
        "ram_ecc_errors": 0,
        "disk_reallocated_sectors": 0,
        "disk_pending_sectors": 0,
        "disk_smart_ok": True,
    },
    "reports": {
        "wipe": json.loads(sys.argv[12] or "{}"),
      "runtime": runtime_report,
    },
    "logs": {
      "captured_at": str(logs_bundle.get("captured_at") or "") if isinstance(logs_bundle, dict) else "",
      "entries": log_entries,
    },
    "usb_tunnel_public_key": sys.argv[18],
}
print(json.dumps(payload))
PY
}

apply_runtime_sync_response() {
  local response_file="${1:-}"
  [[ -r "$response_file" ]] || return 1

  local state_dir lock_file wipe_file policy_file stream_env_file restart_marker update_file update_env_file engine_marker system_marker
  state_dir="$(beagle_state_dir)"
  mkdir -p "$state_dir" >/dev/null 2>&1 || true
  lock_file="$state_dir/device.locked"
  wipe_file="$state_dir/device.wipe-pending"
  policy_file="$state_dir/device-policy.json"
  stream_env_file="$state_dir/stream-profile.env"
  restart_marker="$state_dir/stream-profile.restart"
  update_file="$state_dir/device-updates.json"
  update_env_file="$state_dir/device-updates.env"
  engine_marker="$state_dir/beagle-os-update.requested"
  system_marker="$state_dir/system-update.requested"

  python3 - "$response_file" "$lock_file" "$wipe_file" "$policy_file" "$stream_env_file" "$restart_marker" "$update_file" "$update_env_file" "$engine_marker" "$system_marker" <<'PY'
import json, sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
commands = payload.get("commands") if isinstance(payload, dict) else {}
policy = payload.get("policy") if isinstance(payload, dict) else {}
updates = payload.get("updates") if isinstance(payload, dict) else {}
if not isinstance(updates, dict):
  updates = {}

lock_file = Path(sys.argv[2])
wipe_file = Path(sys.argv[3])
policy_file = Path(sys.argv[4])
stream_env_file = Path(sys.argv[5])
restart_marker = Path(sys.argv[6])
update_file = Path(sys.argv[7])
update_env_file = Path(sys.argv[8])
engine_marker = Path(sys.argv[9])
system_marker = Path(sys.argv[10])

if commands.get("lock_screen"):
    lock_file.write_text("locked\n", encoding="utf-8")
else:
    lock_file.unlink(missing_ok=True)

if commands.get("wipe_pending"):
    wipe_file.write_text("wipe_pending\n", encoding="utf-8")
else:
    wipe_file.unlink(missing_ok=True)

policy_file.write_text(json.dumps(policy, indent=2), encoding="utf-8")

stream_profile = policy.get("stream_profile") if isinstance(policy, dict) else {}
if not isinstance(stream_profile, dict):
  stream_profile = {}

def shell_value(value):
  text = str(value)
  return "'" + text.replace("'", "'\\''") + "'"

env_map = {}
if stream_profile:
  env_map = {
    "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PRESET": stream_profile.get("preset", ""),
    "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESOLUTION": stream_profile.get("resolution", "1920x1080"),
    "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS": stream_profile.get("fps", 45),
    "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE": stream_profile.get("bitrate", 16000),
    "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PACKET_SIZE": stream_profile.get("packet_size", 1200),
    "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_CODEC": stream_profile.get("video_codec", "H.264"),
    "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_DECODER": stream_profile.get("video_decoder", "auto"),
    "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUDIO_CONFIG": stream_profile.get("audio_config", "stereo"),
    "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FRAME_PACING": "1" if stream_profile.get("frame_pacing") else "0",
    "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VSYNC": "1" if stream_profile.get("vsync") else "0",
  }

content = "".join(f"export {key}={shell_value(value)}\n" for key, value in env_map.items())
old = stream_env_file.read_text(encoding="utf-8") if stream_env_file.exists() else ""
if content != old:
  if content:
    stream_env_file.write_text(content, encoding="utf-8")
  else:
    stream_env_file.unlink(missing_ok=True)
  restart_marker.write_text("restart\n", encoding="utf-8")

beagle_os = updates.get("beagle_os") if isinstance(updates.get("beagle_os"), dict) else {}
system = updates.get("system") if isinstance(updates.get("system"), dict) else {}
update_file.write_text(json.dumps(updates, indent=2), encoding="utf-8")
update_env = {
  "PVE_THIN_CLIENT_BEAGLE_UPDATE_ENABLED": "1" if beagle_os.get("auto_update", True) else "0",
  "PVE_THIN_CLIENT_BEAGLE_UPDATE_CHANNEL": beagle_os.get("channel", "stable") or "stable",
  "PVE_THIN_CLIENT_BEAGLE_UPDATE_BEHAVIOR": beagle_os.get("behavior", "prompt") or "prompt",
  "PVE_THIN_CLIENT_BEAGLE_UPDATE_VERSION_PIN": beagle_os.get("target_version", "") or "",
  "PVE_THIN_CLIENT_SYSTEM_UPDATE_ENABLED": "1" if system.get("auto_update", False) else "0",
  "PVE_THIN_CLIENT_SYSTEM_UPDATE_TARGET": system.get("target", "") or "",
  "PVE_THIN_CLIENT_BEAGLE_LOG_CAPTURE_ENABLED": "1" if bool((updates.get("logging") or {}).get("enabled", True)) else "0",
  "PVE_THIN_CLIENT_BEAGLE_LOG_RETENTION_SECONDS": str((updates.get("logging") or {}).get("retention_seconds", 86400) or 86400),
}
update_env_content = "".join(f"export {key}={shell_value(value)}\n" for key, value in update_env.items())
old_update_env = update_env_file.read_text(encoding="utf-8") if update_env_file.exists() else ""
if update_env_content != old_update_env:
  update_env_file.write_text(update_env_content, encoding="utf-8")
if commands.get("install_update") or beagle_os.get("install_requested"):
  engine_marker.write_text(str(beagle_os.get("target_version", "") or "latest") + "\n", encoding="utf-8")
else:
  engine_marker.unlink(missing_ok=True)
if commands.get("install_sys_update") or system.get("install_requested"):
  system_marker.write_text(str(system.get("target", "") or "all") + "\n", encoding="utf-8")
else:
  system_marker.unlink(missing_ok=True)
PY
  if [[ -f "$restart_marker" ]]; then
  rm -f "$restart_marker" >/dev/null 2>&1 || true
  if pgrep -x beagle-stream >/dev/null 2>&1 || pgrep -x beagle-stream-client >/dev/null 2>&1; then
    pkill -TERM -x beagle-stream >/dev/null 2>&1 || true
    pkill -TERM -x beagle-stream-client >/dev/null 2>&1 || true
  fi
  fi
}

sync_device_runtime_state() {
  local sync_url manager_token manager_pin manager_ca_cert device_id hostname_value wg_iface wg_active=0 wg_ip="" response_file payload_file http_status curl_bin
  local -a curl_args tls_args

  sync_url="$(runtime_manager_sync_url)" || return 0
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  [[ -n "$manager_token" ]] || return 0
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  device_id="$(runtime_device_id)"
  hostname_value="$(runtime_endpoint_hostname)"
  wg_iface="${WG_IFACE:-wg-beagle}"
  runtime_record_boot_occurrence
  if runtime_wireguard_active "$wg_iface"; then
    wg_active=1
    wg_ip="$(runtime_wireguard_ip "$wg_iface")"
  fi

  response_file="$(mktemp)"
  payload_file="$(mktemp)"
  curl_bin="$(runtime_curl_bin)"
  runtime_device_sync_payload "$device_id" "$hostname_value" "$wg_iface" "$wg_active" "$wg_ip" >"$payload_file"

  curl_args=("$curl_bin" -fsS --connect-timeout 8 --max-time 25 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "$sync_url" "$manager_pin" "$manager_ca_cert")
  local tls_arg
  for tls_arg in "${tls_args[@]}"; do
    [[ -n "$tls_arg" ]] || continue
    curl_args+=("$tls_arg")
  done
  http_status="$("${curl_args[@]}" --data-binary "@${payload_file}" "$sync_url" || true)"

  if [[ "$http_status" == "200" ]]; then
    apply_runtime_sync_response "$response_file" || true
    beagle_log_event "device.sync.ok" "device_id=${device_id} wg_active=${wg_active} status=200"
    rm -f "$payload_file" "$response_file"
    return 0
  fi

  beagle_log_event "device.sync.error" "device_id=${device_id} status=${http_status:-unknown}"
  rm -f "$payload_file" "$response_file"
  return 1
}

confirm_device_wiped_runtime() {
  local confirm_url manager_token manager_pin manager_ca_cert device_id response_file http_status curl_bin
  local -a curl_args tls_args

  confirm_url="$(runtime_manager_confirm_wiped_url)" || return 0
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  [[ -n "$manager_token" ]] || return 0
  device_id="${1:-$(runtime_device_id)}"
  [[ -n "$device_id" ]] || return 1
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  response_file="$(mktemp)"
  curl_bin="$(runtime_curl_bin)"

  curl_args=("$curl_bin" -fsS --connect-timeout 8 --max-time 20 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "$confirm_url" "$manager_pin" "$manager_ca_cert")
  local tls_arg
  for tls_arg in "${tls_args[@]}"; do
    [[ -n "$tls_arg" ]] || continue
    curl_args+=("$tls_arg")
  done
  http_status="$("${curl_args[@]}" --data '{}' "$confirm_url" || true)"

  if [[ "$http_status" == "200" ]]; then
    beagle_log_event "device.wipe.confirmed" "device_id=${device_id} status=200"
    rm -f "$response_file"
    return 0
  fi

  beagle_log_event "device.wipe.confirm-error" "device_id=${device_id} status=${http_status:-unknown}"
  rm -f "$response_file"
  return 1
}
