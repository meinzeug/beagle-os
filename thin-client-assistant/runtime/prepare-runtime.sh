#!/usr/bin/env bash
set -euo pipefail

STATUS_DIR="${STATUS_DIR:-/var/lib/pve-thin-client}"
STATUS_FILE="$STATUS_DIR/runtime.status"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config
beagle_log_event "prepare-runtime.start" "profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default} mode=${PVE_THIN_CLIENT_MODE:-UNSET}"

plymouth_status() {
  local message="$1"
  command -v plymouth >/dev/null 2>&1 || return 0
  plymouth --ping >/dev/null 2>&1 || return 0
  plymouth display-message --text="$message" >/dev/null 2>&1 || true
}

sync_runtime_config_to_system() {
  local target_dir="/etc/pve-thin-client"
  local source_dir="${CONFIG_DIR:-}"
  local file=""
  local copied=0

  [[ -n "$source_dir" ]] || return 0
  [[ "$source_dir" != "$target_dir" ]] || return 0
  [[ -d "$source_dir" ]] || return 0

  install -d -m 0755 "$target_dir"
  for file in thinclient.conf network.env credentials.env local-auth.env; do
    if [[ -f "$source_dir/$file" ]]; then
      install -m 0600 "$source_dir/$file" "$target_dir/$file"
      copied=1
    fi
  done

  if [[ "$copied" == "1" ]]; then
    CONFIG_DIR="$target_dir"
    CONFIG_FILE="$target_dir/thinclient.conf"
    NETWORK_FILE="$target_dir/network.env"
    CREDENTIALS_FILE="$target_dir/credentials.env"
    LOCAL_AUTH_FILE="$target_dir/local-auth.env"
  fi
  chmod 0644 "$target_dir/thinclient.conf" "$target_dir/network.env" >/dev/null 2>&1 || true
}

ensure_runtime_user() {
  local runtime_user shell_path runtime_password

  runtime_user="${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}"
  if [[ -x /usr/local/bin/beagle-login-shell ]]; then
    shell_path="/usr/local/bin/beagle-login-shell"
  elif [[ -x /usr/local/bin/pve-thin-client-login-shell ]]; then
    shell_path="/usr/local/bin/pve-thin-client-login-shell"
  else
    shell_path="/bin/bash"
  fi

  if ! id "$runtime_user" >/dev/null 2>&1; then
    useradd -m -s "$shell_path" -G audio,video,input,render,plugdev,users,netdev "$runtime_user" >/dev/null 2>&1 || true
  fi

  usermod -s "$shell_path" "$runtime_user" >/dev/null 2>&1 || true
  usermod -a -G audio,video,input,render,plugdev,users,netdev "$runtime_user" >/dev/null 2>&1 || true

  runtime_password=""
  if [[ -r "${LOCAL_AUTH_FILE:-${CONFIG_DIR:-/etc/pve-thin-client}/local-auth.env}" ]]; then
    # shellcheck disable=SC1090
    source "${LOCAL_AUTH_FILE:-${CONFIG_DIR:-/etc/pve-thin-client}/local-auth.env}"
    runtime_password="${PVE_THIN_CLIENT_RUNTIME_PASSWORD:-}"
  fi
  if [[ -n "$runtime_password" ]]; then
    printf '%s:%s\n' "$runtime_user" "$runtime_password" | chpasswd >/dev/null 2>&1 || true
  fi
}

adjust_secret_permissions() {
  local runtime_user credentials_file
  runtime_user="${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}"
  credentials_file="${CREDENTIALS_FILE:-${CONFIG_DIR:-/etc/pve-thin-client}/credentials.env}"
  [[ -f "$credentials_file" ]] || return 0
  chown root:"$runtime_user" "$credentials_file" >/dev/null 2>&1 || true
  chmod 0640 "$credentials_file" >/dev/null 2>&1 || true
  if [[ -f "${LOCAL_AUTH_FILE:-${CONFIG_DIR:-/etc/pve-thin-client}/local-auth.env}" ]]; then
    chmod 0600 "${LOCAL_AUTH_FILE:-${CONFIG_DIR:-/etc/pve-thin-client}/local-auth.env}" >/dev/null 2>&1 || true
  fi
}

enroll_endpoint_if_needed() {
  local credentials_file response_file enroll_url enrollment_token endpoint_id hostname_value http_status manager_pin
  local -a curl_args

  credentials_file="${CREDENTIALS_FILE:-${CONFIG_DIR:-/etc/pve-thin-client}/credentials.env}"
  [[ -f "$credentials_file" ]] || return 0
  enrollment_token="${PVE_THIN_CLIENT_BEAGLE_ENROLLMENT_TOKEN:-}"
  [[ -n "$enrollment_token" ]] || return 0
  [[ -z "${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}" ]] || return 0

  enroll_url="${PVE_THIN_CLIENT_BEAGLE_ENROLLMENT_URL:-${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}/api/v1/endpoints/enroll}"
  [[ -n "$enroll_url" ]] || return 1
  endpoint_id="${PVE_THIN_CLIENT_HOSTNAME:-$(hostname)}-${PVE_THIN_CLIENT_PROXMOX_VMID:-0}"
  hostname_value="${PVE_THIN_CLIENT_HOSTNAME:-$(hostname)}"
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  response_file="$(mktemp)"
  curl_args=(curl -fsS --connect-timeout 8 --max-time 20 --output "$response_file" --write-out '%{http_code}' -H 'Content-Type: application/json')
  if [[ "$enroll_url" == https://* ]]; then
    if [[ -n "$manager_pin" ]]; then
      curl_args+=(--pinnedpubkey "$manager_pin")
    elif [[ "${PVE_THIN_CLIENT_ALLOW_INSECURE_TLS:-0}" == "1" ]]; then
      curl_args+=(-k)
    else
      beagle_log_event "prepare-runtime.enroll-skip" "missing manager tls pin"
      rm -f "$response_file"
      return 1
    fi
  fi
  http_status="$(
    "${curl_args[@]}" \
      --data "{\"enrollment_token\":\"${enrollment_token}\",\"endpoint_id\":\"${endpoint_id}\",\"hostname\":\"${hostname_value}\"}" \
      "${enroll_url%/}" || true
  )"
  if [[ "$http_status" != "201" ]]; then
    rm -f "$response_file"
    return 1
  fi
  python3 - "$response_file" "${CONFIG_FILE:-${CONFIG_DIR:-/etc/pve-thin-client}/thinclient.conf}" "$credentials_file" <<'PY'
import json, sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
config_path = Path(sys.argv[2])
cred_path = Path(sys.argv[3])
config = payload.get("config", {}) if isinstance(payload, dict) else {}
existing = {}
if cred_path.exists():
    for raw_line in cred_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        existing[key.strip()] = value.strip()
for key, value in (
    ("PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN", config.get("beagle_manager_token", "")),
    ("PVE_THIN_CLIENT_SUNSHINE_USERNAME", config.get("sunshine_username", "")),
    ("PVE_THIN_CLIENT_SUNSHINE_PASSWORD", config.get("sunshine_password", "")),
    ("PVE_THIN_CLIENT_SUNSHINE_PIN", config.get("sunshine_pin", "")),
    ("PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY", config.get("sunshine_pinned_pubkey", "")),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PRIVATE_KEY", config.get("egress_wg_private_key", "")),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PRESHARED_KEY", config.get("egress_wg_preshared_key", "")),
):
    existing[key] = json.dumps(str(value))
existing["PVE_THIN_CLIENT_BEAGLE_ENROLLMENT_TOKEN"] = json.dumps("")
cred_path.write_text("".join(f"{key}={value}\n" for key, value in existing.items()), encoding="utf-8")

config_existing = {}
if config_path.exists():
    for raw_line in config_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        config_existing[key.strip()] = value.strip()

for key, value in (
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_MODE", config.get("egress_mode", "direct")),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_TYPE", config.get("egress_type", "")),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_INTERFACE", config.get("egress_interface", "beagle-egress")),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_DOMAINS", " ".join(config.get("egress_domains", []) or [])),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_RESOLVERS", " ".join(config.get("egress_resolvers", []) or [])),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_ALLOWED_IPS", " ".join(config.get("egress_allowed_ips", []) or [])),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_ADDRESS", config.get("egress_wg_address", "")),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_DNS", config.get("egress_wg_dns", "")),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PUBLIC_KEY", config.get("egress_wg_public_key", "")),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_ENDPOINT", config.get("egress_wg_endpoint", "")),
    ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE", config.get("egress_wg_persistent_keepalive", "25")),
    ("PVE_THIN_CLIENT_IDENTITY_HOSTNAME", config.get("identity_hostname", "")),
    ("PVE_THIN_CLIENT_IDENTITY_TIMEZONE", config.get("identity_timezone", "")),
    ("PVE_THIN_CLIENT_IDENTITY_LOCALE", config.get("identity_locale", "")),
    ("PVE_THIN_CLIENT_IDENTITY_KEYMAP", config.get("identity_keymap", "")),
    ("PVE_THIN_CLIENT_IDENTITY_CHROME_PROFILE", config.get("identity_chrome_profile", "default")),
):
    config_existing[key] = json.dumps(str(value))

config_path.write_text("".join(f"{key}={value}\n" for key, value in config_existing.items()), encoding="utf-8")
PY
  rm -f "$response_file"
  # Reload freshly written credentials for subsequent steps.
  # shellcheck disable=SC1090
  source "$credentials_file"
}

sync_local_hostname() {
  local desired_hostname hosts_file temp_file

  desired_hostname="${PVE_THIN_CLIENT_HOSTNAME_VALUE:-${PVE_THIN_CLIENT_HOSTNAME:-}}"
  [[ -n "$desired_hostname" ]] || return 0

  printf '%s\n' "$desired_hostname" >/etc/hostname
  hostname "$desired_hostname" >/dev/null 2>&1 || true

  hosts_file="/etc/hosts"
  [[ -f "$hosts_file" ]] || return 0

  temp_file="$(mktemp)"
  awk '
    $1 == "127.0.1.1" {next}
    {print}
  ' "$hosts_file" >"$temp_file"
  {
    cat "$temp_file"
    printf '127.0.1.1 %s\n' "$desired_hostname"
  } >"$hosts_file"
  rm -f "$temp_file"
}

strip_managed_ssh_block() {
  local src_file="$1"
  local begin_marker="$2"
  local end_marker="$3"

  awk -v begin="$begin_marker" -v end="$end_marker" '
    $0 == begin {skip = 1; next}
    $0 == end {skip = 0; next}
    !skip {print}
  ' "$src_file"
}

apply_runtime_ssh_config() {
  local sshd_config begin_marker end_marker temp_file

  sshd_config="${PVE_THIN_CLIENT_SSHD_CONFIG:-/etc/ssh/sshd_config}"
  begin_marker="# --- pve-thin-client managed ssh begin ---"
  end_marker="# --- pve-thin-client managed ssh end ---"

  [[ -f "$sshd_config" ]] || return 0

  temp_file="$(mktemp)"
  strip_managed_ssh_block "$sshd_config" "$begin_marker" "$end_marker" >"$temp_file" || cp -f "$sshd_config" "$temp_file"

  {
    cat "$temp_file"
    printf '\n%s\n' "$begin_marker"
    printf 'PasswordAuthentication yes\n'
    printf 'KbdInteractiveAuthentication yes\n'
    printf 'PermitEmptyPasswords no\n'
    printf 'PermitRootLogin no\n'
    printf '%s\n' "$end_marker"
  } >"$sshd_config"

  rm -f "$temp_file"
  chmod 0600 "$sshd_config" >/dev/null 2>&1 || true

  if command -v sshd >/dev/null 2>&1 && sshd -t -f "$sshd_config" >/dev/null 2>&1; then
    systemctl restart ssh.service >/dev/null 2>&1 || true
  fi
}

ensure_getty_overrides() {
  local tty1_dir="/etc/systemd/system/getty@tty1.service.d"
  local default_dir="/etc/systemd/system/getty@.service.d"

  install -d -m 0755 "$tty1_dir" "$default_dir"

  cat >"$default_dir/zz-beagle-default.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty -o '-p -- \u' --noclear - $TERM
EOF

  cat >"$tty1_dir/zz-beagle-autologin.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/usr/local/bin/pve-thin-client-tty-login %I $TERM
EOF

  rm -f "$tty1_dir/autologin.conf" >/dev/null 2>&1 || true
  systemctl daemon-reload >/dev/null 2>&1 || true
}

normalize_boot_services() {
  local boot_mode
  boot_mode="$(/usr/local/bin/pve-thin-client-boot-mode 2>/dev/null || printf 'runtime')"

  case "$boot_mode" in
    runtime)
      systemctl list-unit-files pve-thin-client-prepare.service >/dev/null 2>&1 && \
        systemctl enable pve-thin-client-prepare.service >/dev/null 2>&1 || true
      systemctl list-unit-files pve-thin-client-runtime.service >/dev/null 2>&1 && \
        systemctl enable pve-thin-client-runtime.service >/dev/null 2>&1 || true
      systemctl list-unit-files pve-thin-client-installer-menu.service >/dev/null 2>&1 && \
        systemctl disable pve-thin-client-installer-menu.service >/dev/null 2>&1 || true
      systemctl disable getty@tty1.service >/dev/null 2>&1 || true
      ;;
    installer)
      systemctl list-unit-files pve-thin-client-prepare.service >/dev/null 2>&1 && \
        systemctl enable pve-thin-client-prepare.service >/dev/null 2>&1 || true
      systemctl list-unit-files pve-thin-client-installer-menu.service >/dev/null 2>&1 && \
        systemctl enable pve-thin-client-installer-menu.service >/dev/null 2>&1 || true
      systemctl list-unit-files pve-thin-client-runtime.service >/dev/null 2>&1 && \
        systemctl disable pve-thin-client-runtime.service >/dev/null 2>&1 || true
      systemctl disable getty@tty1.service >/dev/null 2>&1 || true
      ;;
    *)
      systemctl enable getty@tty1.service >/dev/null 2>&1 || true
      ;;
  esac
}

if [[ -x "$SCRIPT_DIR/apply-network-config.sh" ]]; then
  plymouth_status "Configuring network..."
  beagle_log_event "prepare-runtime.network" "applying network configuration"
  "$SCRIPT_DIR/apply-network-config.sh"
fi

plymouth_status "Loading Beagle OS profile..."
sync_runtime_config_to_system
ensure_runtime_user
adjust_secret_permissions
plymouth_status "Connecting device to Beagle Manager..."
enroll_endpoint_if_needed || beagle_log_event "prepare-runtime.enroll-error" "endpoint enrollment failed"
adjust_secret_permissions
sync_local_hostname
apply_runtime_ssh_config
ensure_getty_overrides
normalize_boot_services
if [[ -x /usr/local/sbin/beagle-identity-apply ]]; then
  plymouth_status "Applying system identity..."
  /usr/local/sbin/beagle-identity-apply >/dev/null 2>&1 || true
fi
if [[ -x /usr/local/sbin/beagle-egress-apply ]]; then
  plymouth_status "Preparing secure connection..."
  /usr/local/sbin/beagle-egress-apply >/dev/null 2>&1 || true
fi
beagle_log_event "prepare-runtime.system" "runtime_user=${PVE_THIN_CLIENT_RUNTIME_USER:-UNSET} hostname=${PVE_THIN_CLIENT_HOSTNAME_VALUE:-UNSET}"

mkdir -p "$STATUS_DIR"
chmod 0755 "$STATUS_DIR"

required_binary=""
binary_available="0"
case "${PVE_THIN_CLIENT_MODE:-MOONLIGHT}" in
  MOONLIGHT)
    required_binary="${PVE_THIN_CLIENT_MOONLIGHT_BIN:-moonlight}"
    ;;
  *)
    echo "Unsupported mode for Beagle OS: ${PVE_THIN_CLIENT_MODE:-UNSET}" >&2
    exit 1
    ;;
esac

{
  echo "timestamp=$(date -Iseconds)"
  echo "mode=${PVE_THIN_CLIENT_MODE:-UNSET}"
  echo "runtime_user=${PVE_THIN_CLIENT_RUNTIME_USER:-UNSET}"
  echo "connection_method=${PVE_THIN_CLIENT_CONNECTION_METHOD:-UNSET}"
  echo "profile_name=${PVE_THIN_CLIENT_PROFILE_NAME:-UNSET}"
  echo "required_binary=$required_binary"
  echo "moonlight_host=${PVE_THIN_CLIENT_MOONLIGHT_HOST:-UNSET}"
  echo "moonlight_app=${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}"
  if command -v "$required_binary" >/dev/null 2>&1; then
    binary_available="1"
    echo "binary_available=1"
  else
    echo "binary_available=0"
  fi
} > "$STATUS_FILE"

chmod 0644 "$STATUS_FILE"
beagle_log_event "prepare-runtime.ready" "binary=${required_binary} binary_available=${binary_available}"
