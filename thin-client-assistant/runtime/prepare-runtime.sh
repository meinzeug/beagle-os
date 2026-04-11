#!/usr/bin/env bash
set -euo pipefail

STATUS_DIR="${STATUS_DIR:-/var/lib/pve-thin-client}"
STATUS_FILE="$STATUS_DIR/runtime.status"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY_ENROLLMENT_CONFIG_PY="$SCRIPT_DIR/apply_enrollment_config.py"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config_with_retry() {
  local attempts interval attempt
  attempts="${PVE_THIN_CLIENT_CONFIG_RETRY_ATTEMPTS:-30}"
  interval="${PVE_THIN_CLIENT_CONFIG_RETRY_INTERVAL:-1}"

  for attempt in $(seq 1 "$attempts"); do
    if load_runtime_config >/dev/null 2>&1; then
      return 0
    fi
    sleep "$interval"
  done

  load_runtime_config
}

load_runtime_config_with_retry
BOOT_MODE="${PVE_THIN_CLIENT_BOOT_MODE:-$(/usr/local/bin/pve-thin-client-boot-mode 2>/dev/null || printf 'runtime')}"
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
  for file in thinclient.conf network.env credentials.env local-auth.env install-manifest.json; do
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
  chmod 0644 "$target_dir/thinclient.conf" "$target_dir/network.env" "$target_dir/install-manifest.json" >/dev/null 2>&1 || true
}

remount_live_state_writable() {
  local state_dir="${1:-}"
  local mount_target mount_opts

  [[ -n "$state_dir" ]] || return 1
  mount_target="$(findmnt -nro TARGET --target "$state_dir" 2>/dev/null | head -n1)"
  [[ -n "$mount_target" ]] || return 1
  mount_opts="$(findmnt -nro OPTIONS --target "$state_dir" 2>/dev/null || true)"
  if grep -qw rw <<<"$mount_opts" && ! grep -qw ro <<<"$mount_opts"; then
    return 0
  fi
  mount -o remount,rw "$mount_target" >/dev/null 2>&1
}

persist_runtime_config_to_live_state() {
  local source_dir="${CONFIG_DIR:-/etc/pve-thin-client}"
  local live_state_dir="" file="" copied=0

  [[ -d "$source_dir" ]] || return 0
  live_state_dir="$(find_live_state_dir || true)"
  [[ -n "$live_state_dir" ]] || return 0
  [[ "$live_state_dir" != "$source_dir" ]] || return 0
  remount_live_state_writable "$live_state_dir" || return 0

  install -d -m 0755 "$live_state_dir"
  for file in thinclient.conf network.env credentials.env local-auth.env install-manifest.json; do
    if [[ -f "$source_dir/$file" ]]; then
      install -m 0600 "$source_dir/$file" "$live_state_dir/$file"
      copied=1
    fi
  done

  if [[ "$copied" == "1" ]]; then
    chmod 0644 "$live_state_dir/thinclient.conf" "$live_state_dir/network.env" "$live_state_dir/install-manifest.json" >/dev/null 2>&1 || true
  fi
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
  local credentials_file response_file enroll_url enrollment_token endpoint_id hostname_value http_status manager_pin manager_ca_cert
  local -a curl_args tls_args

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
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  response_file="$(mktemp)"
  curl_args=(curl -fsS --connect-timeout 8 --max-time 20 --output "$response_file" --write-out '%{http_code}' -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "$enroll_url" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")
  http_status="$(
    "${curl_args[@]}" \
      --data "{\"enrollment_token\":\"${enrollment_token}\",\"endpoint_id\":\"${endpoint_id}\",\"hostname\":\"${hostname_value}\"}" \
      "${enroll_url%/}" || true
  )"
  if [[ "$http_status" != "201" ]]; then
    rm -f "$response_file"
    return 1
  fi
  python3 "$APPLY_ENROLLMENT_CONFIG_PY" \
    "$response_file" \
    "${CONFIG_FILE:-${CONFIG_DIR:-/etc/pve-thin-client}/thinclient.conf}" \
    "$credentials_file"
  rm -f "$response_file"
  # Reload freshly written credentials for subsequent steps.
  # shellcheck disable=SC1090
  source "${CONFIG_FILE:-${CONFIG_DIR:-/etc/pve-thin-client}/thinclient.conf}"
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
    systemctl reset-failed ssh.service >/dev/null 2>&1 || true
    systemctl restart ssh.service >/dev/null 2>&1 || true
  fi
}

ensure_runtime_ssh_host_keys() {
  local live_state_dir="" persistent_key_dir="" key_path="" base_name=""
  local have_valid_keys=0

  live_state_dir="$(find_live_state_dir || true)"
  if [[ -n "$live_state_dir" ]]; then
    remount_live_state_writable "$live_state_dir" || true
    persistent_key_dir="$live_state_dir/ssh-hostkeys"
    install -d -m 0700 "$persistent_key_dir"
  fi

  if [[ -n "$persistent_key_dir" ]]; then
    for key_path in "$persistent_key_dir"/ssh_host_*_key; do
      [[ -s "$key_path" ]] || continue
      base_name="$(basename "$key_path")"
      install -m 0600 "$key_path" "/etc/ssh/$base_name"
      if [[ -s "$key_path.pub" ]]; then
        install -m 0644 "$key_path.pub" "/etc/ssh/$base_name.pub"
      fi
    done
  fi

  for key_path in /etc/ssh/ssh_host_*_key /etc/ssh/ssh_host_*_key.pub; do
    [[ -e "$key_path" ]] || continue
    [[ -s "$key_path" ]] && continue
    rm -f "$key_path"
  done

  for key_path in /etc/ssh/ssh_host_*_key; do
    [[ -s "$key_path" ]] || continue
    have_valid_keys=1
    break
  done

  if [[ "$have_valid_keys" != "1" ]]; then
    ssh-keygen -A >/dev/null 2>&1 || true
  fi

  [[ -n "$persistent_key_dir" ]] || return 0

  for key_path in /etc/ssh/ssh_host_*_key; do
    [[ -s "$key_path" ]] || continue
    base_name="$(basename "$key_path")"
    install -m 0600 "$key_path" "$persistent_key_dir/$base_name"
    if [[ -s "$key_path.pub" ]]; then
      install -m 0644 "$key_path.pub" "$persistent_key_dir/$base_name.pub"
    fi
  done

  if command -v sshd >/dev/null 2>&1 && sshd -t -f "${PVE_THIN_CLIENT_SSHD_CONFIG:-/etc/ssh/sshd_config}" >/dev/null 2>&1; then
    systemctl reset-failed ssh.service >/dev/null 2>&1 || true
    systemctl start ssh.service >/dev/null 2>&1 || true
  fi
}

ensure_usb_tunnel_service() {
  if ! systemctl list-unit-files beagle-usb-tunnel.service >/dev/null 2>&1; then
    return 0
  fi
  systemctl enable beagle-usb-tunnel.service >/dev/null 2>&1 || true
  if [[ "${PVE_THIN_CLIENT_BEAGLE_USB_ENABLED:-0}" == "1" ]]; then
    systemctl restart --no-block beagle-usb-tunnel.service >/dev/null 2>&1 || true
  else
    systemctl stop --no-block beagle-usb-tunnel.service >/dev/null 2>&1 || true
  fi
}

ensure_kiosk_runtime() {
  [[ "$BOOT_MODE" == "runtime" ]] || return 0
  [[ "${PVE_THIN_CLIENT_MODE:-MOONLIGHT}" == "KIOSK" ]] || return 0
  command -v /usr/local/sbin/beagle-kiosk-install >/dev/null 2>&1 || return 0

  plymouth_status "Preparing Beagle OS Gaming..."
  if ! /usr/local/sbin/beagle-kiosk-install --ensure >/dev/null 2>&1; then
    beagle_log_event "prepare-runtime.kiosk-error" "kiosk installation/update failed"
    return 1
  fi

  beagle_log_event "prepare-runtime.kiosk-ready" "beagle-kiosk ensured"
}

unit_file_present() {
  local unit="${1:-}"
  [[ -n "$unit" ]] || return 1
  systemctl list-unit-files --full --no-legend "$unit" 2>/dev/null | awk '{print $1}' | grep -Fxq "$unit"
}

ensure_beagle_management_units() {
  local unit=""

  for unit in \
    beagle-endpoint-report.timer \
    beagle-endpoint-dispatch.timer \
    beagle-runtime-heartbeat.timer \
    beagle-update-scan.timer
  do
    if unit_file_present "$unit"; then
      systemctl enable "$unit" >/dev/null 2>&1 || true
      systemctl restart --no-block "$unit" >/dev/null 2>&1 || true
    fi
  done

  for unit in beagle-endpoint-report.service beagle-endpoint-dispatch.service; do
    if unit_file_present "$unit"; then
      systemctl start --no-block "$unit" >/dev/null 2>&1 || true
    fi
  done

  if unit_file_present "beagle-update-boot-scan.service"; then
    systemctl enable beagle-update-boot-scan.service >/dev/null 2>&1 || true
    systemctl start --no-block beagle-update-boot-scan.service >/dev/null 2>&1 || true
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

plymouth_status "Loading Beagle OS profile..."
sync_runtime_config_to_system
ensure_runtime_user
adjust_secret_permissions
persist_runtime_config_to_live_state
sync_local_hostname
apply_runtime_ssh_config
ensure_getty_overrides
normalize_boot_services

if [[ -x "$SCRIPT_DIR/apply-network-config.sh" ]]; then
  plymouth_status "Configuring network..."
  beagle_log_event "prepare-runtime.network" "applying network configuration"
  "$SCRIPT_DIR/apply-network-config.sh" || beagle_log_event "prepare-runtime.network-error" "network configuration failed"
fi

plymouth_status "Connecting device to Beagle Manager..."
enroll_endpoint_if_needed || beagle_log_event "prepare-runtime.enroll-error" "endpoint enrollment failed"
adjust_secret_permissions
ensure_runtime_ssh_host_keys
persist_runtime_config_to_live_state
ensure_beagle_management_units
ensure_usb_tunnel_service
ensure_kiosk_runtime || true
if [[ -x /usr/local/sbin/beagle-identity-apply ]]; then
  plymouth_status "Applying system identity..."
  /usr/local/sbin/beagle-identity-apply >/dev/null 2>&1 || true
fi
if [[ -x /usr/local/sbin/beagle-egress-apply ]]; then
  plymouth_status "Preparing secure connection..."
  /usr/local/sbin/beagle-egress-apply >/dev/null 2>&1 || true
fi
beagle_log_event "prepare-runtime.system" "runtime_user=${PVE_THIN_CLIENT_RUNTIME_USER:-UNSET} hostname=${PVE_THIN_CLIENT_HOSTNAME:-UNSET}"

mkdir -p "$STATUS_DIR"
chmod 0755 "$STATUS_DIR"

required_binary=""
binary_available="0"
if [[ "$BOOT_MODE" == "installer" ]]; then
  required_binary="installer-mode"
  binary_available="1"
else
  case "${PVE_THIN_CLIENT_MODE:-MOONLIGHT}" in
    MOONLIGHT)
      required_binary="${PVE_THIN_CLIENT_MOONLIGHT_BIN:-moonlight}"
      ;;
    KIOSK)
      required_binary="/usr/local/sbin/beagle-kiosk-launch"
      ;;
    GFN)
      required_binary="flatpak"
      ;;
    *)
      echo "Unsupported mode for Beagle OS: ${PVE_THIN_CLIENT_MODE:-UNSET}" >&2
      exit 1
      ;;
  esac
fi

{
  echo "timestamp=$(date -Iseconds)"
  echo "boot_mode=$BOOT_MODE"
  echo "mode=${PVE_THIN_CLIENT_MODE:-UNSET}"
  echo "runtime_user=${PVE_THIN_CLIENT_RUNTIME_USER:-UNSET}"
  echo "connection_method=${PVE_THIN_CLIENT_CONNECTION_METHOD:-UNSET}"
  echo "profile_name=${PVE_THIN_CLIENT_PROFILE_NAME:-UNSET}"
  echo "required_binary=$required_binary"
  echo "moonlight_host=${PVE_THIN_CLIENT_MOONLIGHT_HOST:-UNSET}"
  echo "moonlight_app=${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}"
  if [[ "$BOOT_MODE" == "installer" ]]; then
    echo "binary_available=1"
  elif [[ "$required_binary" == */* ]]; then
    if [[ -x "$required_binary" ]]; then
      binary_available="1"
      echo "binary_available=1"
    else
      echo "binary_available=0"
    fi
  elif command -v "$required_binary" >/dev/null 2>&1; then
    binary_available="1"
    echo "binary_available=1"
  else
    echo "binary_available=0"
  fi
} > "$STATUS_FILE"

chmod 0644 "$STATUS_FILE"
beagle_log_event "prepare-runtime.ready" "binary=${required_binary} binary_available=${binary_available}"
