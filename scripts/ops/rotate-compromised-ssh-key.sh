#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  rotate-compromised-ssh-key.sh \
    --host <host> \
    --remote-user <user> \
    --auth-priv <path-to-current-auth-private-key> \
    --old-pub <path-to-compromised.pub> \
    --new-pub <path-to-new.pub> \
    --new-priv <path-to-new-private-key> \
    [--old-priv <path-to-compromised-private-key>] \
    [--port <ssh-port>] \
    [--authorized-file <remote-authorized_keys-path>] \
    [--known-hosts <known_hosts-file>] \
    [--evidence-out <local-json-path>]

Notes:
  - The script never writes private key material into the repository.
  - The old key is removed by public-key blob match (comment-independent).
  - If --old-priv is provided, a negative login test is enforced.
USAGE
  exit 2
}

HOST=""
REMOTE_USER="root"
AUTH_PRIV=""
OLD_PUB=""
OLD_PRIV=""
NEW_PUB=""
NEW_PRIV=""
SSH_PORT="22"
AUTHORIZED_FILE=".ssh/authorized_keys"
KNOWN_HOSTS_FILE="${HOME}/.ssh/known_hosts"
EVIDENCE_OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --remote-user)
      REMOTE_USER="${2:-}"
      shift 2
      ;;
    --auth-priv)
      AUTH_PRIV="${2:-}"
      shift 2
      ;;
    --old-pub)
      OLD_PUB="${2:-}"
      shift 2
      ;;
    --old-priv)
      OLD_PRIV="${2:-}"
      shift 2
      ;;
    --new-pub)
      NEW_PUB="${2:-}"
      shift 2
      ;;
    --new-priv)
      NEW_PRIV="${2:-}"
      shift 2
      ;;
    --port)
      SSH_PORT="${2:-}"
      shift 2
      ;;
    --authorized-file)
      AUTHORIZED_FILE="${2:-}"
      shift 2
      ;;
    --known-hosts)
      KNOWN_HOSTS_FILE="${2:-}"
      shift 2
      ;;
    --evidence-out)
      EVIDENCE_OUT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      ;;
  esac
done

[[ -n "$HOST" && -n "$AUTH_PRIV" && -n "$OLD_PUB" && -n "$NEW_PUB" && -n "$NEW_PRIV" ]] || usage
[[ -r "$AUTH_PRIV" ]] || { echo "auth private key not readable: $AUTH_PRIV" >&2; exit 1; }
[[ -r "$OLD_PUB" ]] || { echo "old pub key not readable: $OLD_PUB" >&2; exit 1; }
[[ -r "$NEW_PUB" ]] || { echo "new pub key not readable: $NEW_PUB" >&2; exit 1; }
[[ -r "$NEW_PRIV" ]] || { echo "new private key not readable: $NEW_PRIV" >&2; exit 1; }
[[ -r "$KNOWN_HOSTS_FILE" ]] || { echo "known_hosts not readable: $KNOWN_HOSTS_FILE" >&2; exit 1; }
if [[ -n "$OLD_PRIV" && ! -r "$OLD_PRIV" ]]; then
  echo "old private key not readable: $OLD_PRIV" >&2
  exit 1
fi

old_blob="$(awk '{print $2}' "$OLD_PUB" | head -n 1)"
new_blob="$(awk '{print $2}' "$NEW_PUB" | head -n 1)"
[[ -n "$old_blob" && -n "$new_blob" ]] || {
  echo "failed to parse public key blobs" >&2
  exit 1
}

old_fp="$(ssh-keygen -lf "$OLD_PUB" | awk '{print $2}')"
new_fp="$(ssh-keygen -lf "$NEW_PUB" | awk '{print $2}')"
new_pub_b64="$(base64 <"$NEW_PUB" | tr -d '\n')"

ssh_common=(
  -p "$SSH_PORT"
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=yes
  -o UserKnownHostsFile="$KNOWN_HOSTS_FILE"
)

target="${REMOTE_USER}@${HOST}"
timestamp_utc="$(date -u +%FT%TZ)"

echo "=== BEAGLE SSH INCIDENT ROTATION ==="
echo "timestamp_utc=${timestamp_utc}"
echo "target=${target}"
echo "authorized_file=${AUTHORIZED_FILE}"
echo "auth_key_fingerprint=$(ssh-keygen -lf "$AUTH_PRIV" | awk '{print $2}')"
echo "old_fingerprint=${old_fp}"
echo "new_fingerprint=${new_fp}"

ssh -i "$AUTH_PRIV" "${ssh_common[@]}" "$target" \
  "OLD_BLOB='$old_blob' NEW_BLOB='$new_blob' NEW_PUB_B64='$new_pub_b64' AUTHORIZED_FILE='$AUTHORIZED_FILE' bash -s" <<'REMOTE'
set -euo pipefail

auth_path="${AUTHORIZED_FILE/#\~/$HOME}"
auth_dir="$(dirname "$auth_path")"
new_pub="$(printf '%s' "$NEW_PUB_B64" | base64 -d)"
install -d -m 700 "$auth_dir"
touch "$auth_path"
chmod 600 "$auth_path"

tmp="$(mktemp)"
awk -v old="$OLD_BLOB" -v neu="$NEW_BLOB" '
  BEGIN { removed=0 }
  {
    if (NF >= 2 && $2 == old) {
      removed++
      next
    }
    print
  }
  END { printf("removed_from_main=%d\n", removed) > "/dev/stderr" }
' "$auth_path" >"$tmp"
cat "$tmp" >"$auth_path"
rm -f "$tmp"

if ! awk -v neu="$NEW_BLOB" 'NF >= 2 && $2 == neu {found=1} END {exit(found?0:1)}' "$auth_path"; then
  printf '%s\n' "$new_pub" >>"$auth_path"
  echo "added_new_key=1" >&2
else
  echo "added_new_key=0 (already present)" >&2
fi

if [[ -d "${auth_path}.d" ]]; then
  while IFS= read -r -d '' file; do
    tmp_d="$(mktemp)"
    awk -v old="$OLD_BLOB" '
      { if (NF >= 2 && $2 == old) next; print }
    ' "$file" >"$tmp_d"
    cat "$tmp_d" >"$file"
    rm -f "$tmp_d"
  done < <(find "${auth_path}.d" -type f -print0)
fi

chmod 600 "$auth_path"
echo "remote_rotation=OK"
REMOTE

echo "check_new_key_login=START"
ssh -i "$NEW_PRIV" "${ssh_common[@]}" "$target" 'echo NEW_KEY_LOGIN_OK'

old_key_check_status="not_verified"
if [[ -n "$OLD_PRIV" ]]; then
  echo "check_old_key_rejected=START"
  if ssh -i "$OLD_PRIV" "${ssh_common[@]}" "$target" 'echo OLD_KEY_STILL_WORKS' >/dev/null 2>&1; then
    echo "old key still accepted (rotation incomplete)" >&2
    exit 1
  fi
  old_key_check_status="rejected"
  echo "OLD_KEY_REJECTED_OK"
else
  echo "OLD_KEY_REJECTION_NOT_VERIFIED (no --old-priv provided)"
fi

if [[ -n "$EVIDENCE_OUT" ]]; then
  mkdir -p "$(dirname "$EVIDENCE_OUT")"
  cat >"$EVIDENCE_OUT" <<EOF
{
  "incident": "BEA-18",
  "timestamp_utc": "$timestamp_utc",
  "host": "$HOST",
  "remote_user": "$REMOTE_USER",
  "authorized_file": "$AUTHORIZED_FILE",
  "old_fingerprint": "$old_fp",
  "new_fingerprint": "$new_fp",
  "new_key_login": "ok",
  "old_key_check": "$old_key_check_status",
  "rotation_status": "PASS"
}
EOF
  chmod 600 "$EVIDENCE_OUT" || true
  echo "evidence_out=$EVIDENCE_OUT"
fi

echo "rotation_status=PASS"
