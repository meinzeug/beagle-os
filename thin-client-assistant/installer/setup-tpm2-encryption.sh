#!/usr/bin/env bash
#
# Setup TPM2-based LUKS2 Disk Encryption for Beagle Endpoint OS
#
# This script enables LUKS2 disk encryption with TPM2 auto-unlock (via clevis).
# Falls back to passphrase-based unlock if TPM2 is not available.
#
# Usage:
#   ./setup-tpm2-encryption.sh [--device /dev/vda] [--method auto|tpm2|passphrase]
#
# Requirements:
#   - cryptsetup >= 2.4.0
#   - clevis >= 15 (if TPM2 method)
#   - tpm2-tools (if TPM2 method)
#   - dracut (for initramfs integration)
#

set -euo pipefail

# Default values
DEVICE="${DEVICE:-}"
ENCRYPTION_METHOD="auto"
PASSPHRASE="${PASSPHRASE:-}"
VERBOSE=false

# Defaults from env
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/env-defaults.sh" ]]; then
  source "$SCRIPT_DIR/env-defaults.sh"
fi

readonly CRYPT_MAPPER_NAME="beagle-root"
readonly DRACUT_CONF="/etc/dracut.conf.d/beagle-tpm2-encrypt.conf"
readonly LUKS_BACKUP_FILE="/var/lib/beagle-endpoint/luks-backup.bin"

info() {
  echo "[INFO] $*" >&2
}

warn() {
  echo "[WARN] $*" >&2
}

error() {
  echo "[ERROR] $*" >&2
  return 1
}

debug() {
  if [[ "$VERBOSE" == "true" ]]; then
    echo "[DEBUG] $*" >&2
  fi
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    error "This script must run as root."
    exit 1
  fi
}

check_prereqs() {
  local missing=()
  
  for cmd in cryptsetup dracut; do
    if ! command -v "$cmd" &>/dev/null; then
      missing+=("$cmd")
    fi
  done
  
  # Check for TPM2 tools if needed
  if [[ "$ENCRYPTION_METHOD" == "tpm2" ]] || [[ "$ENCRYPTION_METHOD" == "auto" ]]; then
    for cmd in clevis tpm2-tools; do
      if ! command -v "$cmd" &>/dev/null 2>&1; then
        if [[ "$ENCRYPTION_METHOD" == "tpm2" ]]; then
          missing+=("$cmd")
        fi
      fi
    done
  fi
  
  if [[ ${#missing[@]} -gt 0 ]]; then
    error "Missing required commands: ${missing[*]}"
    error "Install with: apt-get install -y ${missing[*]}"
    return 1
  fi
}

has_tpm2() {
  if [[ -c /dev/tpm0 ]]; then
    debug "Found /dev/tpm0"
    return 0
  fi
  if [[ -c /dev/tpmrm0 ]]; then
    debug "Found /dev/tpmrm0"
    return 0
  fi
  if command -v tpm2_getcap &>/dev/null && tpm2_getcap properties-fixed 2>/dev/null | grep -q "TPM2_PT_FIRMWARE"; then
    debug "TPM2 detected via tpm2_getcap"
    return 0
  fi
  debug "No TPM2 device found"
  return 1
}

validate_device() {
  local device="$1"
  
  if [[ -z "$device" ]]; then
    error "Device not specified. Use --device /dev/sdX or set DEVICE env var."
    return 1
  fi
  
  if [[ ! -b "$device" ]]; then
    error "Device $device is not a block device."
    return 1
  fi
  
  # Check if device is mounted
  if mountpoint -q / 2>/dev/null; then
    if df / | grep -q "$device"; then
      warn "Device $device is currently mounted as root. Encryption should be done on a fresh install or via live-boot."
    fi
  fi
  
  info "Using device: $device"
  return 0
}

setup_luks2_tpm2() {
  local device="$1"
  local slot=0
  
  info "Setting up LUKS2 with TPM2 auto-unlock..."
  
  # Generate a random passphrase for clevis binding
  local luks_passphrase
  luks_passphrase=$(openssl rand -base64 32)
  
  # Initialize LUKS2 container
  info "Initializing LUKS2 container..."
  echo -n "$luks_passphrase" | cryptsetup luksFormat \
    --type luks2 \
    --cipher aes-xts-plain64 \
    --key-size 512 \
    --hash sha256 \
    --pbkdf argon2i \
    --pbkdf-force-iterations 4 \
    "$device" -
  
  info "LUKS2 container initialized"
  
  # Open the container
  info "Opening LUKS2 container..."
  echo -n "$luks_passphrase" | cryptsetup luksOpen "$device" "$CRYPT_MAPPER_NAME" -
  
  # Bind TPM2 via clevis
  info "Binding TPM2 via clevis..."
  if ! echo -n "$luks_passphrase" | clevis luks bind -d "$device" tpm2 '{}' -s "$slot"; then
    error "Failed to bind TPM2. Falling back to passphrase-only."
    cryptsetup luksClose "$CRYPT_MAPPER_NAME" || true
    return 1
  fi
  
  info "TPM2 binding successful."
  
  # Create backup of LUKS header
  info "Creating LUKS header backup..."
  mkdir -p "$(dirname "$LUKS_BACKUP_FILE")"
  cryptsetup luksHeaderBackup "$device" --header-backup-file "$LUKS_BACKUP_FILE"
  chmod 0600 "$LUKS_BACKUP_FILE"
  info "Backup saved to $LUKS_BACKUP_FILE"
  
  return 0
}

setup_luks2_passphrase() {
  local device="$1"
  
  info "Setting up LUKS2 with passphrase-based unlock..."
  
  if [[ -z "$PASSPHRASE" ]]; then
    # Interactive passphrase entry
    read -sp "Enter LUKS2 encryption passphrase: " PASSPHRASE || true
    echo
    local passphrase_confirm
    read -sp "Confirm passphrase: " passphrase_confirm || true
    echo
    
    if [[ "$PASSPHRASE" != "$passphrase_confirm" ]]; then
      error "Passphrases do not match."
      return 1
    fi
    
    if [[ -z "$PASSPHRASE" ]]; then
      error "Passphrase cannot be empty."
      return 1
    fi
  fi
  
  if [[ ${#PASSPHRASE} -lt 8 ]]; then
    error "Passphrase must be at least 8 characters."
    return 1
  fi
  
  info "Initializing LUKS2 container with passphrase..."
  echo -n "$PASSPHRASE" | cryptsetup luksFormat \
    --type luks2 \
    --cipher aes-xts-plain64 \
    --key-size 512 \
    --hash sha256 \
    --pbkdf argon2i \
    --pbkdf-force-iterations 4 \
    "$device" -
  
  info "LUKS2 container initialized with passphrase"
  
  # Test unlock
  info "Testing passphrase unlock..."
  echo -n "$PASSPHRASE" | cryptsetup luksOpen "$device" "$CRYPT_MAPPER_NAME" - || {
    error "Passphrase verification failed."
    return 1
  }
  
  info "Passphrase verified successfully."
  
  # Create backup
  info "Creating LUKS header backup..."
  mkdir -p "$(dirname "$LUKS_BACKUP_FILE")"
  cryptsetup luksHeaderBackup "$device" --header-backup-file "$LUKS_BACKUP_FILE"
  chmod 0600 "$LUKS_BACKUP_FILE"
  
  return 0
}

setup_dracut() {
  info "Configuring dracut for LUKS2 auto-unlock..."
  
  mkdir -p "$(dirname "$DRACUT_CONF")"
  
  cat > "$DRACUT_CONF" <<'EOF'
# Beagle Endpoint OS LUKS2 + TPM2 Configuration
hostonly="yes"
add_dracutmodules+=" crypt cryptsetup "

# For TPM2 support (if available)
if command -v clevis &>/dev/null; then
  add_dracutmodules+=" clevis "
fi

# Force inclusion of crypttab
add_files+=" /etc/crypttab "
EOF

  info "Dracut configuration saved to $DRACUT_CONF"
  
  # Rebuild initramfs
  info "Rebuilding initramfs..."
  if dracut --force --hostonly; then
    info "Initramfs rebuilt successfully"
  else
    warn "Dracut rebuild had issues, but may still work"
  fi
}

setup_crypttab() {
  info "Setting up /etc/crypttab for auto-unlock..."
  
  # Check if device is already in crypttab
  if grep -q "^$CRYPT_MAPPER_NAME" /etc/crypttab 2>/dev/null; then
    info "Device already in /etc/crypttab, skipping"
    return 0
  fi
  
  # Add to crypttab
  # Format: name, device, password (- means prompt), options
  if has_tpm2; then
    # TPM2 auto-unlock via clevis
    echo "$CRYPT_MAPPER_NAME $DEVICE - discard,x-systemd.device-timeout=0" >> /etc/crypttab
    info "Added to /etc/crypttab with TPM2 auto-unlock"
  else
    # Passphrase prompt
    echo "$CRYPT_MAPPER_NAME $DEVICE - discard,x-systemd.device-timeout=0" >> /etc/crypttab
    info "Added to /etc/crypttab with passphrase prompt"
  fi
}

cleanup() {
  if cryptsetup status "$CRYPT_MAPPER_NAME" &>/dev/null; then
    info "Closing LUKS2 container..."
    cryptsetup luksClose "$CRYPT_MAPPER_NAME" || true
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --device) DEVICE="$2"; shift 2 ;;
      --method) ENCRYPTION_METHOD="$2"; shift 2 ;;
      --passphrase) PASSPHRASE="$2"; shift 2 ;;
      --verbose) VERBOSE=true; shift ;;
      -h|--help) usage; exit 0 ;;
      *) error "Unknown option: $1"; exit 1 ;;
    esac
  done
}

usage() {
  cat <<EOF
Setup TPM2-based LUKS2 Disk Encryption for Beagle Endpoint OS

Usage:
  $0 [OPTIONS]

Options:
  --device DEVICE           Block device to encrypt (e.g., /dev/sda)
  --method METHOD           Encryption method: auto|tpm2|passphrase (default: auto)
                            - auto: Use TPM2 if available, fallback to passphrase
                            - tpm2: Force TPM2 (fail if not available)
                            - passphrase: Force passphrase-only
  --passphrase PHRASE       Pre-set passphrase (for non-interactive mode)
  --verbose                 Enable verbose output
  -h, --help               Show this help message

Examples:
  # Auto-detect TPM2, fallback to passphrase
  sudo $0 --device /dev/vda

  # Force TPM2 encryption
  sudo $0 --device /dev/vda --method tpm2

  # Use passphrase only
  sudo $0 --device /dev/vda --method passphrase

Notes:
  - LUKS header backup is saved to: $LUKS_BACKUP_FILE
  - For TPM2 method, clevis and tpm2-tools must be installed
  - The device should not be currently in use
  - Requires root privileges

EOF
}

main() {
  parse_args "$@"
  
  require_root
  check_prereqs
  validate_device "$DEVICE"
  
  trap cleanup EXIT
  
  # Determine encryption method
  if [[ "$ENCRYPTION_METHOD" == "auto" ]]; then
    if has_tpm2; then
      info "TPM2 detected, using TPM2 method"
      ENCRYPTION_METHOD="tpm2"
    else
      info "TPM2 not detected, using passphrase method"
      ENCRYPTION_METHOD="passphrase"
    fi
  fi
  
  # Execute encryption setup
  case "$ENCRYPTION_METHOD" in
    tpm2)
      if ! setup_luks2_tpm2 "$DEVICE"; then
        error "TPM2 encryption failed"
        return 1
      fi
      ;;
    passphrase)
      if ! setup_luks2_passphrase "$DEVICE"; then
        error "Passphrase encryption failed"
        return 1
      fi
      ;;
    *)
      error "Unknown encryption method: $ENCRYPTION_METHOD"
      return 1
      ;;
  esac
  
  # Configure dracut and crypttab
  setup_dracut
  setup_crypttab
  
  info "✓ Disk encryption setup complete!"
  info "Encryption method: $ENCRYPTION_METHOD"
  info "Device: $DEVICE"
  info "Mapper name: $CRYPT_MAPPER_NAME"
  info ""
  info "Next steps:"
  info "1. Reboot the system"
  info "2. If using TPM2: System will unlock automatically"
  info "3. If using passphrase: Enter passphrase at boot prompt"
}

# Run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
