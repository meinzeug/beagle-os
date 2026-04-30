#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-root@srv1.beagle-os.com}"
NEW_PASSWORD="${2:-}"

if [[ -z "$NEW_PASSWORD" ]]; then
  echo "usage: $0 [user@host] <new-password>" >&2
  exit 2
fi

ssh -4 -o BatchMode=yes "$TARGET" "NEW_PASSWORD='$NEW_PASSWORD' bash -s" <<'REMOTE'
set -euo pipefail

users_path=""
for candidate in \
  /var/lib/beagle/beagle-manager/auth/users.json \
  /var/lib/beagle-manager/auth/users.json \
  /var/lib/beagle/auth/users.json; do
  if [[ -f "$candidate" ]]; then
    users_path="$candidate"
    break
  fi
done
if [[ -z "$users_path" ]]; then
  users_path="$(find /var/lib -maxdepth 5 -path '*/auth/users.json' -print -quit 2>/dev/null || true)"
fi
if [[ -z "$users_path" || ! -f "$users_path" ]]; then
  echo "unable to locate auth users.json" >&2
  exit 1
fi
echo "users_path=$users_path"
export users_path

python3 - <<'PY'
import hashlib
import json
import os
import secrets
from pathlib import Path

users_path = Path(os.environ.get("users_path", ""))
new_password = os.environ.get("NEW_PASSWORD", "")
if not users_path.exists():
    raise SystemExit(f"users file missing: {users_path}")
if not new_password:
    raise SystemExit("NEW_PASSWORD missing")

obj = json.loads(users_path.read_text())
users = obj.get("users") or []
admin = None
for user in users:
    if isinstance(user, dict) and str(user.get("username", "")).strip().lower() == "admin":
        admin = user
        break
if admin is None:
    raise SystemExit("admin user missing")

iterations = 390000
salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac("sha256", new_password.encode("utf-8"), salt, iterations)
admin["password_hash"] = f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"
admin["enabled"] = True

users_path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
print("RESET_OK")
PY

systemctl restart beagle-control-plane.service
sleep 2

curl -sk -w "\nHTTP:%{http_code}\n" \
  -H "content-type: application/json" \
  -X POST https://localhost/beagle-api/api/v1/auth/login \
  --data "{\"username\":\"admin\",\"password\":\"$NEW_PASSWORD\"}" | head -c 700
REMOTE
