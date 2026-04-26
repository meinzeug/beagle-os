#!/usr/bin/env bash
# beagle-cluster-ssh-setup.sh
#
# Sets up bidirectional SSH trust between beagle-manager on this node and all
# peer nodes, so that virsh qemu+ssh:// live-migration works without password
# prompts or host-key verification errors.
#
# Usage (run as root on every cluster node):
#   ./beagle-cluster-ssh-setup.sh <peer-host> [<peer-host2> ...]
#
# What it does:
#   1. Ensures beagle-manager has an SSH key + config (idempotent, see
#      setup_beagle_manager_migration_ssh in install-beagle-host-services.sh).
#   2. Adds the SSH host keys of each peer to /var/lib/beagle/.ssh/known_hosts
#      (unhashed, IPv4 only, idempotent).
#   3. Copies the local beagle-manager public key to each peer's
#      root authorized_keys so virsh can connect as root via the
#      beagle-manager identity.
#
# Example — on srv1:
#   ./beagle-cluster-ssh-setup.sh srv2.beagle-os.com
# Then on srv2:
#   ./beagle-cluster-ssh-setup.sh srv1.beagle-os.com
#
# After running on both nodes, test with:
#   su -s /bin/bash beagle-manager -c \
#     "ssh -i /var/lib/beagle/.ssh/id_ed25519 root@<peer> hostname"
# ---------------------------------------------------------------------------
set -euo pipefail

BEAGLE_CONTROL_USER="${BEAGLE_CONTROL_USER:-beagle-manager}"
SSH_HOME="/var/lib/beagle/.ssh"
KEY_FILE="$SSH_HOME/id_ed25519"
CONFIG_FILE="$SSH_HOME/config"
KNOWN_HOSTS="$SSH_HOME/known_hosts"

# --- helpers ----------------------------------------------------------------

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "==> $*" >&2; }

require_root() {
  [[ $EUID -eq 0 ]] || die "Must be run as root."
}

# --- Step 1: ensure beagle-manager SSH key + config exist -------------------

setup_local_key() {
  install -d -m 0700 -o "$BEAGLE_CONTROL_USER" -g "$BEAGLE_CONTROL_USER" "$SSH_HOME"

  if [[ ! -f "$KEY_FILE" ]]; then
    info "Generating beagle-manager SSH key..."
    ssh-keygen -t ed25519 -N '' \
      -f "$KEY_FILE" \
      -C "beagle-manager@$(hostname -s)-migration" \
      >/dev/null
    chown "$BEAGLE_CONTROL_USER:$BEAGLE_CONTROL_USER" "$KEY_FILE" "${KEY_FILE}.pub"
    chmod 0600 "$KEY_FILE"
    chmod 0644 "${KEY_FILE}.pub"
  else
    info "beagle-manager SSH key already exists: $KEY_FILE"
  fi

  if [[ ! -f "$CONFIG_FILE" ]]; then
    info "Writing SSH client config for beagle-manager..."
    cat > "$CONFIG_FILE" <<'SSHCFG'
# Managed by beagle-cluster-ssh-setup.sh — do not edit manually.
# Used by beagle-manager for virsh qemu+ssh:// live-migration connections.
Host *
    IdentityFile /var/lib/beagle/.ssh/id_ed25519
    AddressFamily inet
    StrictHostKeyChecking accept-new
    BatchMode yes
    ConnectTimeout 10
SSHCFG
    chown "$BEAGLE_CONTROL_USER:$BEAGLE_CONTROL_USER" "$CONFIG_FILE"
    chmod 0600 "$CONFIG_FILE"
  else
    info "SSH client config already exists: $CONFIG_FILE"
  fi

  touch "$KNOWN_HOSTS"
  chown "$BEAGLE_CONTROL_USER:$BEAGLE_CONTROL_USER" "$KNOWN_HOSTS"
  chmod 0600 "$KNOWN_HOSTS"
}

# --- Step 2: add peer host keys to known_hosts (idempotent) -----------------

add_peer_host_keys() {
  local peer="$1"
  info "Fetching SSH host keys from $peer..."

  # Resolve to IPv4 to avoid IPv6 mismatch
  local ipv4
  ipv4="$(getent ahostsv4 "$peer" 2>/dev/null | awk '{print $1; exit}')" || true
  if [[ -z "$ipv4" ]]; then
    # fallback: try plain DNS
    ipv4="$(dig +short A "$peer" 2>/dev/null | head -1)" || true
  fi

  local scan_targets=("$peer")
  [[ -n "$ipv4" && "$ipv4" != "$peer" ]] && scan_targets+=("$ipv4")

  for target in "${scan_targets[@]}"; do
    # Remove stale entries, then append fresh ones
    ssh-keygen -R "$target" -f "$KNOWN_HOSTS" >/dev/null 2>&1 || true
    ssh-keyscan -4 -T 10 "$target" 2>/dev/null >> "$KNOWN_HOSTS" || true
  done

  chown "$BEAGLE_CONTROL_USER:$BEAGLE_CONTROL_USER" "$KNOWN_HOSTS"
  chmod 0600 "$KNOWN_HOSTS"
  info "Host keys for $peer added to $KNOWN_HOSTS"
}

# --- Step 3: distribute local pubkey to peer's root authorized_keys ---------

distribute_pubkey() {
  local peer="$1"
  local pubkey
  pubkey="$(cat "${KEY_FILE}.pub")"

  info "Distributing beagle-manager public key to root@$peer ..."
  # ssh-copy-id equivalent — append only if not already present
  ssh -o AddressFamily=inet \
      -o StrictHostKeyChecking=accept-new \
      -o ConnectTimeout=15 \
      "root@$peer" \
      "mkdir -p /root/.ssh && chmod 700 /root/.ssh && \
       grep -qxF '${pubkey}' /root/.ssh/authorized_keys 2>/dev/null || \
       echo '${pubkey}' >> /root/.ssh/authorized_keys && \
       chmod 600 /root/.ssh/authorized_keys && \
       echo 'pubkey added to root@\$(hostname -s)'"
}

# --- Step 4: smoke-test as beagle-manager -----------------------------------

smoke_test() {
  local peer="$1"
  info "Smoke-testing SSH as beagle-manager to root@$peer..."
  if su -s /bin/bash "$BEAGLE_CONTROL_USER" -c \
      "ssh -o AddressFamily=inet \
           -o StrictHostKeyChecking=accept-new \
           -o BatchMode=yes \
           -o ConnectTimeout=10 \
           -i '$KEY_FILE' \
           root@$peer 'hostname'" 2>/dev/null; then
    info "SSH test to $peer: OK"
  else
    echo "WARNING: SSH test to $peer failed — check connectivity and authorized_keys on $peer" >&2
  fi
}

# --- main -------------------------------------------------------------------

require_root

[[ $# -ge 1 ]] || die "Usage: $0 <peer-host> [<peer-host2> ...]"

setup_local_key

for peer in "$@"; do
  add_peer_host_keys "$peer"
  distribute_pubkey "$peer"
  smoke_test "$peer"
done

info "Done. beagle-manager public key:"
cat "${KEY_FILE}.pub"
info "Run this script on each peer node pointing back to this host to establish bidirectional trust."
