#!/usr/bin/env bash
set -euo pipefail

BEAGLE_STREAM_CLIENT_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [[ ! -d "$BEAGLE_STREAM_CLIENT_RUNTIME_DIR" ]]; then
  if command -v sudo >/dev/null 2>&1 && [[ -x /usr/local/sbin/beagle-ensure-xdg-runtime-dir ]]; then
    sudo /usr/local/sbin/beagle-ensure-xdg-runtime-dir "$(id -u)" >/dev/null 2>&1 || true
  fi
  mkdir -p "$BEAGLE_STREAM_CLIENT_RUNTIME_DIR" >/dev/null 2>&1 || true
fi
if [[ ! -d "$BEAGLE_STREAM_CLIENT_RUNTIME_DIR" || ! -w "$BEAGLE_STREAM_CLIENT_RUNTIME_DIR" || ! -x "$BEAGLE_STREAM_CLIENT_RUNTIME_DIR" ]]; then
  BEAGLE_STREAM_CLIENT_RUNTIME_DIR="/tmp/pve-thin-client-runtime-$(id -u)"
  mkdir -p "$BEAGLE_STREAM_CLIENT_RUNTIME_DIR" >/dev/null 2>&1 || true
  chmod 0700 "$BEAGLE_STREAM_CLIENT_RUNTIME_DIR" >/dev/null 2>&1 || true
fi
export XDG_RUNTIME_DIR="$BEAGLE_STREAM_CLIENT_RUNTIME_DIR"
BEAGLE_STREAM_CLIENT_LOCK_FILE="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCK_FILE:-/tmp/beagle-stream-client-launch.lock}"
exec 9>"$BEAGLE_STREAM_CLIENT_LOCK_FILE"
flock -n 9 || exit 0

SCRIPT_DIR="${RUNTIME_SCRIPT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
if [[ "$SCRIPT_DIR" == /var/local/* ]]; then
  SCRIPT_DIR="/usr/local/${SCRIPT_DIR#/var/local/}"
fi
BEAGLE_STREAM_CLIENT_TARGETING_SH="${BEAGLE_STREAM_CLIENT_TARGETING_SH:-$SCRIPT_DIR/beagle_stream_client_targeting.sh}"
BEAGLE_STREAM_CLIENT_PAIRING_SH="${BEAGLE_STREAM_CLIENT_PAIRING_SH:-$SCRIPT_DIR/beagle_stream_client_pairing.sh}"
BEAGLE_STREAM_CLIENT_RUNTIME_EXEC_SH="${BEAGLE_STREAM_CLIENT_RUNTIME_EXEC_SH:-$SCRIPT_DIR/beagle_stream_client_runtime_exec.sh}"
BEAGLE_STREAM_CLIENT_CLI_SH="${BEAGLE_STREAM_CLIENT_CLI_SH:-$SCRIPT_DIR/beagle_stream_client_cli.sh}"
BEAGLE_STREAM_CLIENT_HOST_SYNC_SH="${BEAGLE_STREAM_CLIENT_HOST_SYNC_SH:-$SCRIPT_DIR/beagle_stream_client_host_sync.sh}"
BEAGLE_STREAM_CLIENT_REMOTE_API_SH="${BEAGLE_STREAM_CLIENT_REMOTE_API_SH:-$SCRIPT_DIR/beagle_stream_client_remote_api.sh}"
BEAGLE_STREAM_CLIENT_MANAGER_REGISTRATION_SH="${BEAGLE_STREAM_CLIENT_MANAGER_REGISTRATION_SH:-$SCRIPT_DIR/beagle_stream_client_manager_registration.sh}"
BEAGLE_STREAM_CLIENT_STREAM_PROFILE_SH="${BEAGLE_STREAM_CLIENT_STREAM_PROFILE_SH:-$SCRIPT_DIR/beagle_stream_client_stream_profile.sh}"
RUNTIME_ENDPOINT_ENROLLMENT_SH="${RUNTIME_ENDPOINT_ENROLLMENT_SH:-$SCRIPT_DIR/runtime_endpoint_enrollment.sh}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_TARGETING_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_CLI_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_HOST_SYNC_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_REMOTE_API_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_MANAGER_REGISTRATION_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_PAIRING_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_RUNTIME_EXEC_SH"

load_runtime_config
# Runtime config comes from the installer defaults. Re-apply the manager/local
# stream profile afterwards so live tuning and auto-quality overrides win.
if [[ -r "$BEAGLE_STREAM_CLIENT_STREAM_PROFILE_SH" ]]; then
  # shellcheck disable=SC1090
  source "$BEAGLE_STREAM_CLIENT_STREAM_PROFILE_SH"
fi
beagle_log_event "beagle-stream-client.start" "profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default} host=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST:-UNSET} app=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_APP:-Desktop}"

BEAGLE_STREAM_CLIENT_LOG_DIR="${PVE_THIN_CLIENT_LOG_DIR:-${XDG_RUNTIME_DIR:-/tmp}/pve-thin-client}"
BEAGLE_STREAM_CLIENT_LIST_LOG="$BEAGLE_STREAM_CLIENT_LOG_DIR/beagle-stream-client-list.log"
BEAGLE_STREAM_CLIENT_PAIR_LOG="$BEAGLE_STREAM_CLIENT_LOG_DIR/beagle-stream-client-pair.log"
BEAGLE_STREAM_CLIENT_STREAM_LOG="$BEAGLE_STREAM_CLIENT_LOG_DIR/beagle-stream-client-stream.log"
BEAGLE_STREAM_CLIENT_STARTUP_STATE_FILE="$BEAGLE_STREAM_CLIENT_LOG_DIR/beagle-stream-client-startup.state"
BEAGLE_STREAM_CLIENT_STARTUP_JSON_FILE="$BEAGLE_STREAM_CLIENT_LOG_DIR/beagle-stream-client-startup.json"
BEAGLE_STREAM_CLIENT_STARTUP_HTML_FILE="$BEAGLE_STREAM_CLIENT_LOG_DIR/beagle-stream-client-startup.html"
BEAGLE_STREAM_CLIENT_STARTUP_WALLPAPER_FILE="$BEAGLE_STREAM_CLIENT_LOG_DIR/beagle-stream-client-wallpaper.png"
BEAGLE_STREAM_CLIENT_STARTUP_BROWSER_PROFILE="$BEAGLE_STREAM_CLIENT_LOG_DIR/browser-profile"
BEAGLE_STREAM_CLIENT_STARTUP_UI_PID=""

mkdir -p "$BEAGLE_STREAM_CLIENT_LOG_DIR" 2>/dev/null || true

beagle_stream_startup_status_enabled() {
  [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_STARTUP_STATUS_ENABLED:-1}" == "1" ]]
}

beagle_stream_startup_wallpaper_source() {
  local candidate
  local -a candidates=(
    "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_STARTUP_WALLPAPER:-}"
    "$SCRIPT_DIR/../assets/branding/beagle-cyberpunk-wallpaper.png"
    "/usr/local/lib/pve-thin-client/assets/branding/beagle-cyberpunk-wallpaper.png"
    "/run/pve-thin-client/assets/branding/beagle-cyberpunk-wallpaper.png"
    "$SCRIPT_DIR/../usb/assets/grub-background.jpg"
    "/usr/local/lib/pve-thin-client/usb/assets/grub-background.jpg"
  )

  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" && -r "$candidate" ]] || continue
    printf '%s\n' "$candidate"
    return 0
  done
  return 1
}

beagle_stream_startup_prepare_wallpaper() {
  local source
  if [[ -s "$BEAGLE_STREAM_CLIENT_STARTUP_WALLPAPER_FILE" ]]; then
    printf '%s\n' "$BEAGLE_STREAM_CLIENT_STARTUP_WALLPAPER_FILE"
    return 0
  fi
  source="$(beagle_stream_startup_wallpaper_source 2>/dev/null || true)"
  [[ -n "$source" ]] || return 0
  cp -f "$source" "$BEAGLE_STREAM_CLIENT_STARTUP_WALLPAPER_FILE" >/dev/null 2>&1 || return 0
  printf '%s\n' "$BEAGLE_STREAM_CLIENT_STARTUP_WALLPAPER_FILE"
}

beagle_stream_startup_browser_bin() {
  local candidate
  for candidate in chromium chromium-browser google-chrome-stable google-chrome; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

beagle_stream_startup_status_start() {
  local browser_bin title

  beagle_stream_startup_status_enabled || return 0
  [[ -n "${DISPLAY:-}" ]] || return 0

  title="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_STARTUP_TITLE:-Beagle OS verbindet Stream}"
  beagle_stream_startup_status_render "1" "active" "Runtime initialisieren" "Launcher startet"

  if browser_bin="$(beagle_stream_startup_browser_bin 2>/dev/null)"; then
    mkdir -p "$BEAGLE_STREAM_CLIENT_STARTUP_BROWSER_PROFILE" >/dev/null 2>&1 || true
    "$browser_bin" \
      --kiosk "file://${BEAGLE_STREAM_CLIENT_STARTUP_HTML_FILE}" \
      --user-data-dir="$BEAGLE_STREAM_CLIENT_STARTUP_BROWSER_PROFILE" \
      --allow-file-access-from-files \
      --window-position=0,0 \
      --start-fullscreen \
      --no-first-run \
      --no-default-browser-check \
      --noerrdialogs \
      --disable-infobars \
      --disable-session-crashed-bubble \
      --disable-translate \
      --disable-features=Translate \
      >/dev/null 2>&1 &
    BEAGLE_STREAM_CLIENT_STARTUP_UI_PID="$!"
  elif command -v firefox >/dev/null 2>&1; then
    firefox --kiosk "file://${BEAGLE_STREAM_CLIENT_STARTUP_HTML_FILE}" >/dev/null 2>&1 &
    BEAGLE_STREAM_CLIENT_STARTUP_UI_PID="$!"
  elif command -v zenity >/dev/null 2>&1; then
    beagle_stream_startup_status_zenity "$title"
  fi
}

beagle_stream_startup_status_zenity() {
  local title="$1"

  (
    local frames='|/-\\'
    local idx=0 frame step
    while :; do
      step="$(cat "$BEAGLE_STREAM_CLIENT_STARTUP_STATE_FILE" 2>/dev/null || printf 'Starte Stream...')"
      frame="${frames:$((idx % 4)):1}"
      printf '# [%s] %s\n' "$frame" "$step"
      printf '50\n'
      sleep 0.25
      idx=$((idx + 1))
    done
  ) | zenity --progress \
      --pulsate \
      --auto-close \
      --no-cancel \
      --title "$title" \
      --text "Starte Stream..." \
      --width "560" \
      >/dev/null 2>&1 &
  BEAGLE_STREAM_CLIENT_STARTUP_UI_PID="$!"
}

beagle_stream_startup_status_render() {
  local active_step="$1" status="$2" label="$3" detail="$4"
  local wallpaper_path=""

  beagle_stream_startup_status_enabled || return 0
  wallpaper_path="$(beagle_stream_startup_prepare_wallpaper 2>/dev/null || true)"
  python3 - "$BEAGLE_STREAM_CLIENT_STARTUP_HTML_FILE" "$BEAGLE_STREAM_CLIENT_STARTUP_STATE_FILE" "$BEAGLE_STREAM_CLIENT_STARTUP_JSON_FILE" "$active_step" "$status" "$label" "$detail" "$wallpaper_path" <<'PY' || true
import html
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

html_path = Path(sys.argv[1])
state_path = Path(sys.argv[2])
json_path = Path(sys.argv[3])
active_step = int(sys.argv[4])
status = sys.argv[5]
label = sys.argv[6]
detail = sys.argv[7]
wallpaper_path = sys.argv[8]

steps = [
    "Runtime initialisieren",
    "WireGuard und Audio vorbereiten",
    "Grafik und Decoder konfigurieren",
    "Session-Ziel vom Manager laden",
    "Host-Konfiguration synchronisieren",
    "Pairing-Status pruefen",
    "Ziel-App aufloesen",
    "Stream am Manager vorbereiten",
    "Stream-Prozess starten",
    "Mit VM-Desktop verbinden",
]

now = time.time()
state = {"started_at": now, "steps": []}
if json_path.exists():
    try:
        state = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        pass
state.setdefault("started_at", now)
known = {int(item.get("index", 0)): item for item in state.get("steps", []) if isinstance(item, dict)}
for index, name in enumerate(steps, 1):
    item = known.get(index, {"index": index, "name": name, "status": "pending", "detail": "wartet", "started_at": None, "finished_at": None})
    item["name"] = name
    if index < active_step and item.get("status") in {"pending", "active"}:
        item["status"] = "ok"
        item["detail"] = item.get("detail") if item.get("detail") not in {"wartet", "laeuft"} else "ok"
        item["finished_at"] = item.get("finished_at") or now
    elif index == active_step:
        item["status"] = status
        item["detail"] = detail or status
        item["started_at"] = item.get("started_at") or now
        if status in {"ok", "skip", "warn", "error"}:
            item["finished_at"] = now
    known[index] = item
state["steps"] = [known[index] for index in range(1, len(steps) + 1)]
state["active_step"] = active_step
state["active_label"] = label
state["active_detail"] = detail
state["updated_at"] = now
json_path.write_text(json.dumps(state, ensure_ascii=True), encoding="utf-8")
state_path.write_text(f"Schritt {active_step}/10: {label} - {detail}\n", encoding="utf-8")

def icon_for(value):
    return {"ok": "OK", "active": "...", "skip": "SKIP", "warn": "!", "error": "ERR"}.get(value, "--")

rows = []
for item in state["steps"]:
    cls = html.escape(item.get("status", "pending"))
    rows.append(
        f'<li class="{cls}"><span class="idx">{item["index"]:02d}</span>'
        f'<span class="name">{html.escape(item["name"])}</span>'
        f'<span class="result">{html.escape(icon_for(item.get("status", "pending")))}</span>'
        f'<small>{html.escape(str(item.get("detail") or "wartet"))}</small></li>'
    )

elapsed = int(now - float(state.get("started_at", now)))
wallpaper_url = ""
json_url = "file://" + quote(str(json_path.resolve()), safe="/:")
if wallpaper_path:
  wallpaper_url = "file://" + quote(str(Path(wallpaper_path).resolve()), safe="/:")
initial_state = html.escape(json.dumps(state, ensure_ascii=True))
doc = f'''<!doctype html><html><head><meta charset="utf-8"><title>Beagle OS Streamstart</title>
<style>
html,body{{margin:0;height:100%;overflow:hidden;font-family:Inter,Segoe UI,Arial,sans-serif;background:#05070d;color:#eef6ff;}}
body{{display:grid;place-items:center;background-image:linear-gradient(90deg,rgba(0,0,0,.72),rgba(0,0,0,.36) 44%,rgba(0,0,0,.64)),url('{html.escape(wallpaper_url)}');background-size:cover;background-position:center;background-repeat:no-repeat;}}
.panel{{width:min(820px,92vw);padding:28px 32px;border:1px solid rgba(82,214,255,.28);background:rgba(5,10,18,.70);box-shadow:0 28px 90px rgba(0,0,0,.56);backdrop-filter:blur(12px);}}
.head{{display:flex;align-items:center;gap:18px;margin-bottom:22px;}}
.spinner{{width:44px;height:44px;border:3px solid rgba(82,214,255,.25);border-top-color:#00e5ff;border-right-color:#ff2aaa;border-radius:50%;animation:spin .9s linear infinite;box-shadow:0 0 28px rgba(0,229,255,.25);}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
h1{{font-size:24px;line-height:1.15;margin:0;font-weight:700;letter-spacing:0;}}
.meta{{color:#b5d7e9;font-size:14px;margin-top:6px;}}
ol{{list-style:none;margin:0;padding:0;display:grid;gap:8px;}}
li{{display:grid;grid-template-columns:46px 1fr 62px;grid-template-rows:auto auto;gap:2px 12px;align-items:center;padding:10px 12px;border:1px solid rgba(52,92,116,.72);background:rgba(7,18,30,.76);}}
.idx{{grid-row:1/3;color:#8dddf6;font-variant-numeric:tabular-nums;}}
.name{{font-weight:650;}}
.result{{justify-self:end;font-size:12px;color:#bad7e6;border:1px solid rgba(82,214,255,.25);padding:3px 8px;background:rgba(0,0,0,.22);}}
small{{grid-column:2/4;color:#b0c7d5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
li.ok{{border-color:rgba(63,238,158,.58);background:rgba(7,37,25,.72);}} li.ok .result{{color:#a8f8ca;border-color:rgba(63,238,158,.58);}}
li.active{{border-color:rgba(0,229,255,.75);background:rgba(11,38,58,.82);}} li.active .result{{color:#9eeeff;border-color:rgba(0,229,255,.75);}}
li.warn{{border-color:#d49d32;background:rgba(43,31,7,.78);}} li.error{{border-color:#df5151;background:rgba(50,11,14,.80);}}
</style></head><body><main class="panel"><div class="head"><div class="spinner"></div><div><h1>VM-Desktop wird verbunden</h1><div class="meta" id="meta">{html.escape(label)} - {html.escape(detail)} · {elapsed}s</div></div></div><ol id="steps">{''.join(rows)}</ol></main>
<script>
const startupStateUrl = {json.dumps(json_url)};
const initialState = {initial_state};
const metaNode = document.getElementById('meta');
const stepsNode = document.getElementById('steps');
function iconFor(status) {{
  return {{ok: 'OK', active: '...', skip: 'SKIP', warn: '!', error: 'ERR'}}[status] || '--';
}}
function escapeHtml(value) {{
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
}}
function render(state) {{
  if (!state || !Array.isArray(state.steps)) return;
  const startedAt = Number(state.started_at || 0);
  const updatedAt = Number(state.updated_at || Date.now() / 1000);
  const elapsed = startedAt > 0 ? Math.max(0, Math.round(updatedAt - startedAt)) : 0;
  metaNode.textContent = `${{state.active_label || 'Streamstart'}} - ${{state.active_detail || 'wartet'}} · ${{elapsed}}s`;
  stepsNode.innerHTML = state.steps.map((item) => `
    <li class="${{escapeHtml(item.status || 'pending')}}">
      <span class="idx">${{String(item.index || 0).padStart(2, '0')}}</span>
      <span class="name">${{escapeHtml(item.name || '')}}</span>
      <span class="result">${{escapeHtml(iconFor(item.status || 'pending'))}}</span>
      <small>${{escapeHtml(item.detail || 'wartet')}}</small>
    </li>`).join('');
}}
async function refreshState() {{
  try {{
    const response = await fetch(`${{startupStateUrl}}?ts=${{Date.now()}}`, {{cache: 'no-store'}});
    if (!response.ok) return;
    render(await response.json());
  }} catch (_error) {{
    // ignore transient file-read errors while launcher rewrites the state file
  }}
}}
render(initialState);
setInterval(refreshState, 400);
</script></body></html>'''
html_path.write_text(doc, encoding="utf-8")
PY
  beagle_log_event "beagle-stream-client.startup-step" "step=${active_step}/10 status=${status} label=${label} detail=${detail}"
}

beagle_stream_startup_status_step() {
  local step="$1" label="$2" detail="${3:-laeuft}"

  beagle_stream_startup_status_render "$step" "active" "$label" "$detail"
}

beagle_stream_startup_status_stop() {
  [[ -n "$BEAGLE_STREAM_CLIENT_STARTUP_UI_PID" ]] && kill "$BEAGLE_STREAM_CLIENT_STARTUP_UI_PID" >/dev/null 2>&1 || true
  BEAGLE_STREAM_CLIENT_STARTUP_UI_PID=""
  rm -rf "$BEAGLE_STREAM_CLIENT_STARTUP_STATE_FILE" "$BEAGLE_STREAM_CLIENT_STARTUP_JSON_FILE" "$BEAGLE_STREAM_CLIENT_STARTUP_HTML_FILE" "$BEAGLE_STREAM_CLIENT_STARTUP_WALLPAPER_FILE" "$BEAGLE_STREAM_CLIENT_STARTUP_BROWSER_PROFILE" >/dev/null 2>&1 || true
}

have_binary() {
  command -v "$1" >/dev/null 2>&1
}

wireguard_peer_restore_state_file() {
  printf '%s\n' "${BEAGLE_WG_PEER_RESTORE_STATE_FILE:-/run/beagle/wg-beagle-peer.env}"
}

wireguard_peer_state_value() {
  local key state_file
  key="$1"
  state_file="$2"
  awk -F= -v key="$key" '$1 == key {print substr($0, index($0, "=") + 1); exit}' "$state_file"
}

wireguard_conf_value() {
  local key conf_file
  key="$1"
  conf_file="$2"
  sudo awk -v key="$key" '
    /^\[Peer\]/{p=1; next}
    /^\[/{p=0}
    p && index($0, "=") {
      lhs=substr($0, 1, index($0, "=") - 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", lhs)
      if (lhs == key) {
        value=substr($0, index($0, "=") + 1)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
        print value
        exit
      }
    }
  ' "$conf_file"
}

# After a forced restart (ENet/control-channel disconnect), poll the Sunshine HTTP
# endpoint until it accepts connections or the timeout expires. This prevents
# "Connection refused (Error 1)" on restart attempt 2 caused by Sunshine briefly
# being unavailable while cleaning up the previous session or restarting.
wait_for_stream_server_ready() {
  local host port target max_wait elapsed
  host="${1:-}"
  port="${2:-}"
  max_wait="${3:-15}"
  if [[ -z "$host" ]]; then
    host="$(beagle_stream_client_connect_host 2>/dev/null || true)"
  fi
  if [[ -z "$port" ]]; then
    port="$(beagle_stream_client_port 2>/dev/null || true)"
  fi
  [[ -n "$host" && -n "$port" ]] || return 0
  target="http://${host}:${port}/serverinfo"
  elapsed=0
  while [[ "$elapsed" -lt "$max_wait" ]]; do
    if curl -fsS --connect-timeout 2 --max-time 3 "$target" >/dev/null 2>&1; then
      beagle_log_event "beagle-stream-client.server-ready" "host=${host} port=${port} wait=${elapsed}s"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  beagle_log_event "beagle-stream-client.server-ready-timeout" "host=${host} port=${port} wait=${elapsed}s"
  return 1
}

# Workaround: beagle-stream skips activatePeer() when wg-beagle interface exists,
# even if the peer was removed by a previous deactivatePeer() call.
# Ensure the peer is always configured before launching beagle-stream.
ensure_wg_interface() {
  local iface="wg-beagle"
  local wg_conf="/etc/wireguard/wg-beagle.conf"
  local allowed_ips endpoint endpoint_host
  local default_route default_gw default_dev route_count route

  sudo test -f "$wg_conf" 2>/dev/null || return 0
  if ip link show "$iface" &>/dev/null; then
    sudo ip link set up dev "$iface" >/dev/null 2>&1 || true
  else
    beagle_log_event "beagle-stream-client.wg-interface-up" "iface=${iface} conf=${wg_conf}"
    sudo systemctl start "wg-quick@${iface}.service" >/dev/null 2>&1 || \
      sudo wg-quick up "$iface" >/dev/null 2>&1 || true

    # Fallback for minimal live images where wg-quick fails due missing resolvconf.
    # Recreate enough of wg-quick behavior for this runtime path: interface,
    # address/mtu, endpoint exception route, and AllowedIPs routes.
    if ! ip link show "$iface" &>/dev/null; then
      local tmp_conf addr mtu
      tmp_conf="$(mktemp)"
      if sudo awk '
        BEGIN{in_iface=0;in_peer=0}
        /^\[Interface\]/{in_iface=1;in_peer=0;print;next}
        /^\[Peer\]/{in_peer=1;in_iface=0;print;next}
        /^\[/{in_iface=0;in_peer=0;print;next}
        {
          if (in_iface==1) {
            if ($0 ~ /^[[:space:]]*(Address|DNS|MTU|Table|PreUp|PostUp|PreDown|PostDown|SaveConfig)[[:space:]]*=/) next
            print; next
          }
          print
        }
      ' "$wg_conf" >"$tmp_conf" 2>/dev/null; then
        sudo ip link delete "$iface" >/dev/null 2>&1 || true
        if sudo ip link add "$iface" type wireguard >/dev/null 2>&1 && \
           sudo wg setconf "$iface" "$tmp_conf" >/dev/null 2>&1; then
          addr="$(sudo awk -F= '/^[[:space:]]*Address[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); split($2, a, ","); print a[1]; exit}' "$wg_conf" 2>/dev/null || true)"
          mtu="$(sudo awk -F= '/^[[:space:]]*MTU[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); print $2; exit}' "$wg_conf" 2>/dev/null || true)"
          [[ -n "$addr" ]] && sudo ip address add "$addr" dev "$iface" >/dev/null 2>&1 || true
          [[ -n "$mtu" ]] || mtu="1420"
          sudo ip link set mtu "$mtu" up dev "$iface" >/dev/null 2>&1 || true
          beagle_log_event "beagle-stream-client.wg-interface-fallback" "iface=${iface} mtu=${mtu}"
        fi
      fi
      rm -f "$tmp_conf" >/dev/null 2>&1 || true
    fi
  fi

  allowed_ips="$(sudo awk -F= '/^[[:space:]]*AllowedIPs[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); print $2; exit}' "$wg_conf" 2>/dev/null || true)"
  endpoint="$(sudo awk -F= '/^[[:space:]]*Endpoint[[:space:]]*=/{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}' "$wg_conf" 2>/dev/null || true)"
  endpoint_host="${endpoint%%:*}"
  endpoint_host="${endpoint_host#[}"
  endpoint_host="${endpoint_host%]}"
  default_route="$(ip route show default 2>/dev/null | head -n1 || true)"
  default_gw="$(awk '/default/{for (i=1;i<=NF;i++) if ($i=="via") {print $(i+1); exit}}' <<<"$default_route")"
  default_dev="$(awk '/default/{for (i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}' <<<"$default_route")"
  if [[ -n "$endpoint_host" && -n "$default_dev" ]]; then
    if [[ -n "$default_gw" ]]; then
      sudo ip route replace "$endpoint_host" via "$default_gw" dev "$default_dev" >/dev/null 2>&1 || true
    else
      sudo ip route replace "$endpoint_host" dev "$default_dev" >/dev/null 2>&1 || true
    fi
  fi

  route_count=0
  IFS=',' read -r -a routes <<<"$allowed_ips"
  for route in "${routes[@]}"; do
    [[ -n "$route" ]] || continue
    sudo ip route replace "$route" dev "$iface" >/dev/null 2>&1 || true
    route_count=$((route_count + 1))
  done
  beagle_log_event "beagle-stream-client.wg-routes-fallback" "iface=${iface} routes=${route_count} endpoint=${endpoint_host:-none}"

  if ! ip link show "$iface" &>/dev/null; then
    beagle_log_event "beagle-stream-client.wg-interface-missing" "iface=${iface}"
  fi
}

ensure_wg_peer() {
  local iface="wg-beagle"
  local wg_conf="/etc/wireguard/wg-beagle.conf"
  local peer_state
  peer_state="$(wireguard_peer_restore_state_file)"
  # The root-owned wg-quick config contains the private key. The root prepare
  # step publishes only public peer restore values for this sandboxed launcher.
  [[ -r "$peer_state" ]] || sudo test -f "$wg_conf" 2>/dev/null || return 0
  ensure_wg_interface
  ip link show "$iface" &>/dev/null || return 0
  # If no peers are configured, restore peer from the persisted conf file.
  # NOTE: wg addconf fails on wg-quick configs (Address/DNS fields are not
  # recognized by the low-level wg tool), so we parse and call wg set directly.
  if ! wg show "$iface" peers 2>/dev/null | grep -q .; then
    beagle_log_event "beagle-stream-client.wg-peer-restore" "iface=${iface} conf=${wg_conf}"
    local pubkey endpoint allowed_ips keepalive
    if [[ -r "$peer_state" ]]; then
      pubkey="$(wireguard_peer_state_value WG_PEER_PUBLIC_KEY "$peer_state")"
      endpoint="$(wireguard_peer_state_value WG_PEER_ENDPOINT "$peer_state")"
      allowed_ips="$(wireguard_peer_state_value WG_PEER_ALLOWED_IPS "$peer_state")"
      keepalive="$(wireguard_peer_state_value WG_PEER_KEEPALIVE "$peer_state")"
    else
      pubkey="$(wireguard_conf_value PublicKey "$wg_conf")"
      endpoint="$(wireguard_conf_value Endpoint "$wg_conf")"
      allowed_ips="$(wireguard_conf_value AllowedIPs "$wg_conf" | tr -d '[:space:]')"
      keepalive="$(wireguard_conf_value PersistentKeepalive "$wg_conf")"
    fi
    [[ -n "$pubkey" ]] || return 0
    local -a wg_args=("$iface" peer "$pubkey")
    [[ -n "$endpoint" ]]    && wg_args+=(endpoint "$endpoint")
    [[ -n "$allowed_ips" ]] && wg_args+=(allowed-ips "$allowed_ips")
    [[ -n "$keepalive" ]]   && wg_args+=(persistent-keepalive "$keepalive")
    wg set "${wg_args[@]}" 2>/dev/null || sudo wg set "${wg_args[@]}" 2>/dev/null || true
  fi
}

beagle_stream_wireguard_required() {
  local mode egress_type
  mode="${PVE_THIN_CLIENT_BEAGLE_EGRESS_MODE:-full}"
  egress_type="${PVE_THIN_CLIENT_BEAGLE_EGRESS_TYPE:-}"
  [[ "$mode" != "direct" && "$egress_type" == "wireguard" ]]
}

ensure_beagle_stream_wireguard_ready() {
  local iface wg_conf saved_script_dir saved_runtime_script_dir

  beagle_stream_wireguard_required || return 0

  iface="${PVE_THIN_CLIENT_BEAGLE_EGRESS_INTERFACE:-wg-beagle}"
  wg_conf="${WG_CONF:-/etc/wireguard/${iface}.conf}"

  if ! sudo test -f "$wg_conf" 2>/dev/null; then
    if [[ -r "$RUNTIME_ENDPOINT_ENROLLMENT_SH" ]]; then
      saved_script_dir="$SCRIPT_DIR"
      saved_runtime_script_dir="${RUNTIME_SCRIPT_DIR-}"
      RUNTIME_SCRIPT_DIR="$SCRIPT_DIR"
      # shellcheck disable=SC1090
      source "$RUNTIME_ENDPOINT_ENROLLMENT_SH"
      SCRIPT_DIR="$saved_script_dir"
      if [[ -n "$saved_runtime_script_dir" ]]; then
        RUNTIME_SCRIPT_DIR="$saved_runtime_script_dir"
      else
        unset RUNTIME_SCRIPT_DIR
      fi
      if declare -F enroll_wireguard_if_needed >/dev/null 2>&1; then
        enroll_wireguard_if_needed || beagle_log_event "beagle-stream-client.wireguard-enroll-error" "conf=${wg_conf}"
      fi
    fi
  fi

  if ! sudo test -f "$wg_conf" 2>/dev/null; then
    beagle_log_event "beagle-stream-client.wireguard-required-missing" "conf=${wg_conf}"
    echo "WireGuard is required for Beagle Stream, but '$wg_conf' is missing." >&2
    return 1
  fi

  ensure_wg_peer
  if ! ip link show "$iface" >/dev/null 2>&1; then
    beagle_log_event "beagle-stream-client.wireguard-required-down" "iface=${iface} conf=${wg_conf}"
    echo "WireGuard is required for Beagle Stream, but interface '$iface' is not up." >&2
    return 1
  fi
}

stop_stale_beagle_stream_processes() {
  if ! command -v pkill >/dev/null 2>&1; then
    return 0
  fi
  # A stale process from a previous failed run can reconnect before the launcher
  # reaches pairing checks. Kill only stream-mode client processes for this uid.
  if pkill -u "$(id -u)" -f '^/opt/beagle-stream-client/usr/bin/beagle-stream stream ' >/dev/null 2>&1; then
    beagle_log_event "beagle-stream-client.stale-process" "action=terminated"
  fi
}

wait_for_beagle_stream_client_manager_registration() {
  local attempt max_attempts retry_sleep host port

  host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"
  [[ -n "$(beagle_stream_client_manager_url 2>/dev/null || true)" && -n "${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}" ]] || return 0
  max_attempts="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_REGISTER_WAIT_ATTEMPTS:-30}"
  retry_sleep="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_REGISTER_WAIT_SLEEP:-2}"
  attempt=1
  while [[ "$attempt" -le "$max_attempts" ]]; do
    if ! extract_beagle_stream_client_certificate_pem >/dev/null 2>&1; then
      bootstrap_beagle_stream_client >/dev/null 2>&1 || true
      seed_beagle_stream_client_host_from_runtime_config >/dev/null 2>&1 || true
      retarget_beagle_stream_client_host_from_runtime_config >/dev/null 2>&1 || true
    fi
    if register_beagle_stream_client_via_manager; then
      beagle_log_event "beagle-stream-client.registered" "host=${host} port=${port:-default} attempt=${attempt}/${max_attempts}"
      return 0
    fi
    beagle_stream_client_stream_ready >/dev/null 2>&1 || true
    beagle_log_event "beagle-stream-client.register-wait" "host=${host} port=${port:-default} attempt=${attempt}/${max_attempts}"
    sleep "$retry_sleep"
    attempt=$((attempt + 1))
  done
  return 1
}

main() {
  local bin host connect_host app resolved_app audio_driver port
  local hostless_beagle_stream=0
  local hostless_fast_launch=0
  local session_response_file=""
  local -a args=()

  bin="$(beagle_stream_client_bin)"
  host="$(beagle_stream_client_host)"
  connect_host=""
  port="$(beagle_stream_client_port)"
  app="$(beagle_stream_client_app)"

  if beagle_stream_hostless_enabled; then
    hostless_beagle_stream=1
  fi

  [[ -n "$host" || "$hostless_beagle_stream" == "1" ]] || {
    echo "Missing Beagle Stream Client host." >&2
    exit 1
  }

  stop_stale_beagle_stream_processes

  beagle_stream_startup_status_start
  trap 'beagle_stream_startup_status_stop' EXIT
  beagle_stream_startup_status_step "1" "Runtime initialisieren" "Launcher und Runtime-Konfiguration laden"

  have_binary "$bin" || {
    echo "Beagle Stream Client binary not found: $bin" >&2
    exit 1
  }

  beagle_stream_startup_status_step "2" "WireGuard und Audio vorbereiten" "Netzwerkroute und Sound-Stack vorbereiten"
  ensure_beagle_stream_wireguard_ready || exit 1
  ensure_wg_peer
  connect_host="$(beagle_stream_client_connect_host)"

  if command -v /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1; then
    if pgrep -f '^bash /usr/local/bin/pve-thin-client-audio-init --watch' >/dev/null 2>&1; then
      beagle_log_event "beagle-stream-client.audio-init" "mode=skip-sync reason=watcher-active"
    elif [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUDIO_INIT_MODE:-sync}" == "sync" ]]; then
      /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1 || true
    fi
    if ! pgrep -f '^bash /usr/local/bin/pve-thin-client-audio-init --watch' >/dev/null 2>&1; then
      /usr/local/bin/pve-thin-client-audio-init --watch "${PVE_THIN_CLIENT_AUDIO_WATCH_LOOPS:-0}" >/dev/null 2>&1 &
    fi
  fi

  configure_audio_runtime

  # Prefer the canonical /run/user/<uid> runtime once it becomes available.
  # During early live boots we may start with a /tmp fallback, which can leave
  # the stream process disconnected from the active Pulse/PipeWire socket.
  local preferred_audio_runtime="/run/user/$(id -u)"
  if [[ "$XDG_RUNTIME_DIR" != "$preferred_audio_runtime" && -d "$preferred_audio_runtime" && -w "$preferred_audio_runtime" && -x "$preferred_audio_runtime" ]]; then
    export XDG_RUNTIME_DIR="$preferred_audio_runtime"
    beagle_log_event "beagle-stream-client.audio-runtime" "runtime_dir=${XDG_RUNTIME_DIR}"
  fi

  audio_driver="$(beagle_stream_client_audio_driver)"
  if [[ -n "$audio_driver" && "$audio_driver" != "auto" ]]; then
    export SDL_AUDIODRIVER="$audio_driver"
  elif [[ -S "$XDG_RUNTIME_DIR/pulse/native" ]]; then
    # When PulseAudio-over-PipeWire socket is present, prefer pulse backend.
    # This avoids intermittent ALSA host-down failures during first session boot.
    export SDL_AUDIODRIVER="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUDIO_AUTO_DRIVER:-pulse}"
  fi

  configure_graphics_runtime
  # configure_graphics_runtime may recover runtime dirs during early boot.
  # Re-run audio binding so PULSE_SERVER points to the final active socket.
  configure_audio_runtime
  record_decoder_choice "$(beagle_stream_client_video_decoder)"
  beagle_stream_startup_status_step "3" "Grafik und Decoder konfigurieren" "X11, Renderer und Decoder pruefen"

  if [[ "$hostless_beagle_stream" == "1" && -z "${SDL_RENDER_DRIVER:-}" ]]; then
    export SDL_RENDER_DRIVER="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RENDER_DRIVER:-opengl}"
    beagle_log_event "beagle-stream-client.renderer" "driver=${SDL_RENDER_DRIVER} mode=hostless"
  fi

  if [[ "$hostless_beagle_stream" == "1" || "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISABLE_VULKAN:-1}" == "1" ]]; then
    if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISABLE_VULKAN:-1}" == "1" && -z "${SDL_RENDER_DRIVER:-}" ]]; then
      export SDL_RENDER_DRIVER="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RENDER_DRIVER:-opengl}"
      beagle_log_event "beagle-stream-client.renderer" "driver=${SDL_RENDER_DRIVER} mode=disable-vulkan"
    fi
    export PREFER_VULKAN="${PREFER_VULKAN:-0}"
    export VULKAN_IS_SLOW="${VULKAN_IS_SLOW:-1}"
    export PLVK_ALLOW_SOFTWARE="${PLVK_ALLOW_SOFTWARE:-0}"
  fi

  if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISABLE_VULKAN:-1}" == "1" ]]; then
    export VK_ICD_FILENAMES="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VK_ICD_FILENAMES:-/dev/null}"
    if [[ "$hostless_beagle_stream" == "1" ]]; then
      beagle_log_event "beagle-stream-client.vulkan" "disabled=1 icd=${VK_ICD_FILENAMES} mode=hostless"
    else
      beagle_log_event "beagle-stream-client.vulkan" "disabled=1 icd=${VK_ICD_FILENAMES} mode=direct"
    fi
  fi

  if [[ "$hostless_beagle_stream" != "1" ]]; then
    # In direct mode the endpoint is operator-controlled and must not be overwritten
    # by manager session broker responses that may prefer public routing.
    if beagle_stream_broker_connection; then
      session_response_file="$(mktemp)"
      if fetch_beagle_stream_client_current_session_via_manager "$session_response_file"; then
        if retarget_beagle_stream_client_host_from_session_broker_response "$session_response_file"; then
          host="$(beagle_stream_client_host)"
          connect_host="$(beagle_stream_client_connect_host)"
          port="$(beagle_stream_client_port)"
          beagle_log_event "beagle-stream-client.session-broker" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} current_node=${PVE_THIN_CLIENT_SESSION_CURRENT_NODE:-unknown}"
        fi
      fi
      rm -f "$session_response_file"
    else
      beagle_log_event "beagle-stream-client.session-broker" "mode=direct-skip host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
    fi
  elif beagle_stream_broker_connection; then
    beagle_stream_startup_status_step "4" "Session-Ziel vom Manager laden" "Aktuelle VM-Session abfragen"
    session_response_file="$(mktemp)"
    if fetch_beagle_stream_client_current_session_via_manager "$session_response_file"; then
      if retarget_beagle_stream_client_host_from_session_broker_response "$session_response_file"; then
        host="$(beagle_stream_client_host)"
        connect_host="$(beagle_stream_client_connect_host)"
        port="$(beagle_stream_client_port)"
        beagle_log_event "beagle-stream-client.session-broker" "mode=hostless host=${host} connect_host=${connect_host:-$host} port=${port:-default} current_node=${PVE_THIN_CLIENT_SESSION_CURRENT_NODE:-unknown}"
      fi
    fi
    rm -f "$session_response_file"
    if [[ -z "${host:-}" ]]; then
      host="$(beagle_stream_client_local_host 2>/dev/null || true)"
      if [[ -n "$host" ]]; then
        export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BROKER_HOST="$host"
        connect_host="$(beagle_stream_client_connect_host)"
        port="$(beagle_stream_client_port)"
        beagle_log_event "beagle-stream-client.session-broker" "mode=hostless-fallback host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
      fi
    fi
  fi

  if [[ "$hostless_beagle_stream" != "1" ]]; then
    wait_for_stream_target || {
      beagle_log_event "beagle-stream-client.unreachable" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
      echo "Beagle Stream Client host '$host' is unreachable from this network." >&2
      exit 1
    }
  fi

  if command -v /usr/local/bin/pve-thin-client-display-init >/dev/null 2>&1; then
    /usr/local/bin/pve-thin-client-display-init >/dev/null 2>&1 || true
  fi

  if [[ "$hostless_beagle_stream" != "1" ]]; then
    beagle_stream_startup_status_step "5" "Host-Konfiguration synchronisieren" "Client-Zertifikat und Host-Registry pruefen"
    if ensure_beagle_stream_client_local_host_route; then
      beagle_log_event "beagle-stream-client.local-route" "local_host=$(beagle_stream_client_local_host) via=${connect_host:-$host}"
    fi

    if seed_beagle_stream_client_host_from_runtime_config; then
      beagle_log_event "beagle-stream-client.seeded-config" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} source=runtime-credentials"
    fi

    bootstrap_beagle_stream_client || true
    if ! beagle_stream_client_host_configured; then
      if seed_beagle_stream_client_host_from_runtime_config; then
        beagle_log_event "beagle-stream-client.seeded-config" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
      elif retarget_beagle_stream_client_host_from_runtime_config; then
        beagle_log_event "beagle-stream-client.retargeted-config" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
      fi
    fi

    if beagle_stream_client_host_configured; then
      beagle_log_event "beagle-stream-client.cached-config" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
    fi

    if register_beagle_stream_client_via_manager; then
      beagle_log_event "beagle-stream-client.register-refresh" "host=${host} port=${port:-default}"
    fi

    beagle_stream_startup_status_step "6" "Pairing-Status pruefen" "Client-Zugriff auf BeagleStream pruefen"
    if beagle_stream_client_stream_ready; then
      beagle_log_event "beagle-stream-client.ready" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
    else
      ensure_paired || {
        beagle_log_event "beagle-stream-client.pairing-failed" "host=${host} port=${port:-default} auth=manager-token"
        echo "Beagle Stream Client pairing failed for host '$host'." >&2
        exit 1
      }
    fi
    wait_for_beagle_stream_client_manager_registration || {
      beagle_log_event "beagle-stream-client.register-wait-timeout" "host=${host} port=${port:-default}"
      echo "Beagle Stream Client registration did not become ready for host '$host'." >&2
      exit 1
    }
  else
    beagle_stream_startup_status_step "5" "Hostless-Konfiguration synchronisieren" "Broker-Ziel lokal zwischenspeichern"
    if [[ -n "${host:-}" ]]; then
      if seed_beagle_stream_client_host_from_runtime_config; then
        beagle_log_event "beagle-stream-client.seeded-config" "mode=hostless host=${host} connect_host=${connect_host:-$host} port=${port:-default} source=runtime-credentials"
      fi

      # In broker/hostless mode, endpoint reachability can be transient or firewalled.
      # Skip blocking preflight checks and launch broker-direct immediately.
      beagle_log_event "beagle-stream-client.hostless-preflight-skip" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"

      if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOSTLESS_FAST_LAUNCH:-1}" == "1" ]]; then
        if seed_beagle_stream_client_host_from_runtime_config; then
          beagle_log_event "beagle-stream-client.seeded-config" "mode=hostless-fast host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
        else
          retarget_beagle_stream_client_host_from_runtime_config >/dev/null 2>&1 || true
        fi
        if sync_beagle_stream_client_host_from_serverinfo_probe; then
          beagle_log_event "beagle-stream-client.serverinfo-refresh" "mode=hostless-fast host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
        elif register_beagle_stream_client_via_manager; then
          beagle_log_event "beagle-stream-client.register-refresh" "mode=hostless-fast host=${host} port=${port:-default}"
        fi
        hostless_fast_launch=1
        beagle_stream_startup_status_render "5" "ok" "Hostless-Konfiguration synchronisieren" "fast-path aktiv"
      else
        bootstrap_beagle_stream_client || true
        if ! beagle_stream_client_host_configured; then
          if seed_beagle_stream_client_host_from_runtime_config; then
            beagle_log_event "beagle-stream-client.seeded-config" "mode=hostless host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
          elif retarget_beagle_stream_client_host_from_runtime_config; then
            beagle_log_event "beagle-stream-client.retargeted-config" "mode=hostless host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
          fi
        fi
      fi

      if beagle_stream_client_host_configured; then
        beagle_log_event "beagle-stream-client.cached-config" "mode=hostless host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
      fi

      if [[ "$hostless_fast_launch" != "1" ]] && register_beagle_stream_client_via_manager; then
        beagle_log_event "beagle-stream-client.register-refresh" "mode=hostless host=${host} port=${port:-default}"
      fi

      beagle_stream_startup_status_step "6" "Pairing-Status pruefen" "Schnellcheck der Stream-Berechtigung"
      if beagle_stream_client_stream_ready; then
        beagle_log_event "beagle-stream-client.ready" "mode=hostless host=${host} connect_host=${connect_host:-$host} port=${port:-default} fast_launch=${hostless_fast_launch}"
      else
        # Fast-launch keeps manager preflights minimal, but a stale or missing client
        # certificate still needs an explicit pairing recovery before stream start.
        ensure_paired || {
          beagle_log_event "beagle-stream-client.pairing-failed" "mode=hostless host=${host} port=${port:-default} auth=manager-token fast_launch=${hostless_fast_launch}"
          echo "Beagle Stream Client pairing failed for host '$host'." >&2
          exit 1
        }
      fi
      wait_for_beagle_stream_client_manager_registration || {
        beagle_log_event "beagle-stream-client.register-wait-timeout" "mode=hostless host=${host} port=${port:-default} fast_launch=${hostless_fast_launch}"
        echo "Beagle Stream Client registration did not become ready for host '$host'." >&2
        exit 1
      }
    fi
    beagle_log_event "beagle-stream-client.beagle-stream-hostless" "app=${app} enrollment=$(beagle_stream_enrollment_config)"
  fi

  # Resolve the requested app name even in hostless mode so we do not keep
  # sending a stale default like "Desktop" when the server exposes a different
  # desktop entry.
  beagle_stream_startup_status_step "7" "Ziel-App aufloesen" "Desktop-Eintrag im App-Katalog pruefen"
  resolved_app="$(resolve_stream_app_name "$app" 2>/dev/null || printf '%s' "$app")"
  if [[ -n "$resolved_app" && "$resolved_app" != "$app" ]]; then
    beagle_log_event "beagle-stream-client.app-fallback" "requested=${app} resolved=${resolved_app}"
    PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_APP="$resolved_app"
    app="$resolved_app"
  fi

  local requested_resolution
  beagle_stream_startup_status_step "8" "Stream am Manager vorbereiten" "Aufloesung und VM-Desktop vorbereiten"
  requested_resolution="$(beagle_stream_client_resolution)"
  if [[ "$hostless_beagle_stream" != "1" ]]; then
    if prepare_beagle_stream_client_stream_via_manager "$requested_resolution" "$app"; then
      beagle_log_event "beagle-stream-client.prepare-stream.ok" "resolution=${requested_resolution} app=${app}"
    else
      beagle_log_event "beagle-stream-client.prepare-stream.skip" "resolution=${requested_resolution} app=${app}"
    fi
  elif [[ -n "${host:-}" ]]; then
    if prepare_beagle_stream_client_stream_via_manager "$requested_resolution" "$app"; then
      beagle_log_event "beagle-stream-client.prepare-stream.ok" "mode=hostless resolution=${requested_resolution} app=${app}"
    else
      beagle_log_event "beagle-stream-client.prepare-stream.skip" "mode=hostless resolution=${requested_resolution} app=${app}"
    fi
  fi

  build_stream_args args
  beagle_stream_startup_status_step "9" "Stream-Prozess starten" "BeagleStream Client starten"
  if [[ "$hostless_beagle_stream" == "1" ]]; then
    echo "Starting BeagleStream brokered stream: host=${host:-broker} connect_host=${connect_host:-${host:-broker}} port=${port:-default} app=$app resolution=$(beagle_stream_client_resolution) fps=$(beagle_stream_client_fps)" >&2
  elif [[ -n "$connect_host" && "$connect_host" != "$host" ]]; then
    echo "Starting Beagle Stream Client stream: host=$host resolved_ipv4=$connect_host port=${port:-default} app=$app resolution=$(beagle_stream_client_resolution) fps=$(beagle_stream_client_fps)" >&2
  else
    echo "Starting Beagle Stream Client stream: host=$host port=${port:-default} app=$app resolution=$(beagle_stream_client_resolution) fps=$(beagle_stream_client_fps)" >&2
  fi
  if [[ "$hostless_beagle_stream" == "1" ]]; then
    beagle_log_event "beagle-stream-client.exec" "mode=beagle-stream-hostless host=${host:-broker} connect_host=${connect_host:-${host:-broker}} port=${port:-default} app=${app} resolution=$(beagle_stream_client_resolution) fps=$(beagle_stream_client_fps)"
  else
    beagle_log_event "beagle-stream-client.exec" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} app=${app} resolution=$(beagle_stream_client_resolution) fps=$(beagle_stream_client_fps)"
  fi
  {
    printf '=== %s ===\n' "$(date -Iseconds)"
    printf 'command: '
    printf '%q ' "${args[@]}"
    printf '\n'
  } >>"$BEAGLE_STREAM_CLIENT_STREAM_LOG"

  # Remove the fullscreen startup UI before the actual stream window appears,
  # otherwise Chromium can stay visually on top of the desktop session.
  beagle_stream_startup_status_stop

  # GTK hint overlays can crash on minimal live images with broken icon caches.
  # Keep this disabled by default and allow explicit opt-in via env.
  if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_HINT_ENABLED:-0}" == "1" ]] && command -v /usr/local/bin/beagle-stream-hint >/dev/null 2>&1; then
    /usr/local/bin/beagle-stream-hint >/dev/null 2>&1 &
  fi

  local stream_exit=0 stream_attempt=1 max_attempts retry_delay stream_pid stream_start_line stream_forced_restart stream_unpaired_detected
  local app_lookup_port_fallback_used=0
  local stream_cert_repair_attempted=0
  local stream_unpaired_repair_attempted=0
  local connect_host_fallback_used=0
  local stream_audio_repair_attempted=0
  local stream_audio_driver_fallback_used=0
  max_attempts="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_MAX_RESTARTS:-3}"
  retry_delay="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESTART_DELAY:-3}"
  # Background watchdog: restores wg peer if binary's deactivatePeer() removes it mid-session.
  wg_peer_watchdog() {
    while sleep 8; do
      ensure_wg_peer 2>/dev/null || true
    done
  }
  local wg_watchdog_pid=""
  wg_peer_watchdog &
  wg_watchdog_pid=$!
  while :; do
    beagle_stream_startup_status_step "10" "Mit VM-Desktop verbinden" "RTSP/Video-Session wird aufgebaut"
    build_stream_args args
    if [[ "$stream_attempt" -gt 1 ]]; then
      beagle_log_event "beagle-stream-client.restart" "attempt=${stream_attempt}/${max_attempts} app=${app}"
      printf '=== restart attempt %s/%s %s ===\n' "$stream_attempt" "$max_attempts" "$(date -Iseconds)" >>"$BEAGLE_STREAM_CLIENT_STREAM_LOG"
    fi
    # Restore wg peer before every attempt (binary's deactivatePeer() may have removed it).
    ensure_wg_peer
    stream_start_line="$(wc -l <"$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>/dev/null || printf '0')"
    stream_forced_restart=0
    "${args[@]}" >>"$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>&1 &
    stream_pid=$!
    while kill -0 "$stream_pid" >/dev/null 2>&1; do
      if tail -n +"$((stream_start_line + 1))" "$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>/dev/null | grep -Eq 'Qt Critical: Connection terminated|Connection terminated|Error code: -1'; then
        beagle_log_event "beagle-stream-client.connection-terminated" "attempt=${stream_attempt}/${max_attempts} pid=${stream_pid}"
        kill -TERM "$stream_pid" >/dev/null 2>&1 || true
        sleep 1
        kill -KILL "$stream_pid" >/dev/null 2>&1 || true
        stream_forced_restart=1
        break
      fi
      sleep 2
    done
    if [[ "$stream_forced_restart" -eq 1 ]]; then
      wait "$stream_pid" >/dev/null 2>&1 || true
      stream_exit=124
    elif wait "$stream_pid"; then
      stream_exit=0
    else
      stream_exit=$?
    fi

    stream_unpaired_detected=0
    if tail -n +"$((stream_start_line + 1))" "$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>/dev/null | grep -Eqi 'has not been paired|not been paired|please open moonlight to pair|unauthorized|not paired'; then
      stream_unpaired_detected=1
    fi

    if [[ "$stream_attempt" -lt "$max_attempts" && ( "$stream_exit" -ne 0 || "$stream_unpaired_detected" -eq 1 ) ]]; then
      if [[ "$stream_unpaired_detected" -eq 1 ]]; then
        if [[ "$stream_unpaired_repair_attempted" -eq 0 ]]; then
          local pairing_token
          pairing_token=""
          beagle_log_event "beagle-stream-client.repair" "attempt=${stream_attempt}/${max_attempts} action=unpaired-recovery reason=server-reported-unpaired"
          if request_beagle_stream_client_pairing_token_via_manager; then
            pairing_token="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TOKEN:-}"
            if [[ -n "$pairing_token" ]] && exchange_beagle_stream_client_pairing_token_via_manager "$pairing_token"; then
              if complete_beagle_stream_client_pairing_handshake; then
                beagle_log_event "beagle-stream-client.pairing-recovered" "attempt=${stream_attempt}/${max_attempts} method=manager-token-exchange"
              else
                beagle_log_event "beagle-stream-client.pairing-recovery-failed" "attempt=${stream_attempt}/${max_attempts} reason=client-certificate-handshake"
              fi
            elif [[ -n "$pairing_token" ]] && submit_beagle_stream_server_pairing_token; then
              beagle_log_event "beagle-stream-client.pairing-recovered" "attempt=${stream_attempt}/${max_attempts} method=direct-token-submit"
            else
              beagle_log_event "beagle-stream-client.pairing-recovery-failed" "attempt=${stream_attempt}/${max_attempts}"
            fi
          else
            beagle_log_event "beagle-stream-client.pairing-recovery-failed" "attempt=${stream_attempt}/${max_attempts} reason=pair-token-request"
          fi
          stream_unpaired_repair_attempted=1
        fi
      fi

      if tail -n +"$((stream_start_line + 1))" "$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>/dev/null | grep -Eqi "Failed to open audio device|Couldn't open audio device: Host is down"; then
        if [[ "$stream_audio_repair_attempted" -eq 0 ]] && command -v /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1; then
          beagle_log_event "beagle-stream-client.repair" "attempt=${stream_attempt}/${max_attempts} action=audio-runtime-reinit reason=audio-device-host-down"
          if pgrep -f '^bash /usr/local/bin/pve-thin-client-audio-init --watch' >/dev/null 2>&1; then
            beagle_log_event "beagle-stream-client.audio-init" "mode=skip-sync reason=watcher-active attempt=${stream_attempt}/${max_attempts}"
          else
            /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1 || true
          fi
          if ! pgrep -f '^bash /usr/local/bin/pve-thin-client-audio-init --watch' >/dev/null 2>&1; then
            /usr/local/bin/pve-thin-client-audio-init --watch "${PVE_THIN_CLIENT_AUDIO_WATCH_LOOPS:-0}" >/dev/null 2>&1 &
          fi
          stream_audio_repair_attempted=1
        elif [[ "$stream_audio_driver_fallback_used" -eq 0 ]]; then
          export SDL_AUDIODRIVER="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUDIO_DRIVER_FALLBACK:-dummy}"
          beagle_log_event "beagle-stream-client.audio-fallback" "attempt=${stream_attempt}/${max_attempts} driver=${SDL_AUDIODRIVER} reason=audio-device-host-down"
          stream_audio_driver_fallback_used=1
        fi
      fi

      if tail -n +"$((stream_start_line + 1))" "$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>/dev/null | grep -Eqi 'Server certificate mismatch|"applist" request failed|Failed to find application|Failed to load application'; then
        if [[ "$stream_cert_repair_attempted" -eq 0 ]]; then
          beagle_log_event "beagle-stream-client.repair" "attempt=${stream_attempt}/${max_attempts} action=pairing-and-app-resolve reason=applist-or-cert-mismatch"
          seed_beagle_stream_client_host_from_runtime_config >/dev/null 2>&1 || true
          if sync_beagle_stream_client_host_from_serverinfo_probe >/dev/null 2>&1; then
            beagle_log_event "beagle-stream-client.serverinfo-refresh" "attempt=${stream_attempt}/${max_attempts} reason=applist-or-cert-mismatch"
          fi
          register_beagle_stream_client_via_manager >/dev/null 2>&1 || true
          ensure_paired >/dev/null 2>&1 || true
          resolved_app="$(resolve_stream_app_name "$app" 2>/dev/null || printf '%s' "$app")"
          if [[ -n "$resolved_app" && "$resolved_app" != "$app" ]]; then
            beagle_log_event "beagle-stream-client.app-fallback" "requested=${app} resolved=${resolved_app} reason=repair"
            PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_APP="$resolved_app"
            app="$resolved_app"
          fi
          stream_cert_repair_attempted=1
        elif [[ "$app_lookup_port_fallback_used" -eq 0 && "$port" =~ ^[0-9]+$ ]]; then
          local fallback_port
          fallback_port="$((port + 1))"
          if [[ "$fallback_port" -gt 0 ]]; then
            export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PORT="$fallback_port"
            port="$fallback_port"
            retarget_beagle_stream_client_host_from_runtime_config || true
            beagle_log_event "beagle-stream-client.port-fallback" "from=$((fallback_port - 1)) to=${fallback_port} reason=applist-or-cert-mismatch"
            app_lookup_port_fallback_used=1
          fi
        fi
      fi
    fi

    if [[ "$stream_exit" -eq 0 || "$stream_attempt" -ge "$max_attempts" ]]; then
      break
    fi
    # After a forced restart (ENet disconnect), wait for Sunshine to finish session
    # cleanup before retrying — avoids "Connection refused (Error 1)" on attempt 2+.
    if [[ "$stream_forced_restart" -eq 1 ]]; then
      ensure_wg_peer
      wait_for_stream_server_ready "${connect_host:-$host}" "$port" 15 || true
    fi
    sleep "$retry_delay"
    stream_attempt=$((stream_attempt + 1))
  done
  [[ -n "$wg_watchdog_pid" ]] && kill "$wg_watchdog_pid" 2>/dev/null || true
  beagle_stream_startup_status_stop
  if [[ "$hostless_beagle_stream" == "1" ]]; then
    beagle_log_event "beagle-stream-client.exit" "code=${stream_exit} mode=beagle-stream-hostless app=${app}"
  else
    beagle_log_event "beagle-stream-client.exit" "code=${stream_exit} host=${host} connect_host=${connect_host:-$host} port=${port:-default} app=${app}"
  fi
  if [[ "$stream_exit" -ne 0 ]]; then
    beagle_log_event "beagle-stream-client.error" "code=${stream_exit} log=${BEAGLE_STREAM_CLIENT_STREAM_LOG}"
  fi
  return "$stream_exit"
}

main "$@"
