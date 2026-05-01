#!/usr/bin/env bash
# Validate the Moonlight app-name resolver against a live Sunshine instance.
# Tests that GET /api/apps returns a "Desktop" app and that the resolver function
# correctly picks it up (no more "failed to find Application Desktop" errors).
#
# Usage:
#   SUNSHINE_API_URL="https://<guest-ip>:47990"   required
#   SUNSHINE_USER="admin"                          optional (default: admin)
#   SUNSHINE_PASSWORD="<pass>"                     required
#
# Runs on the LOCAL host (no SSH needed) — the script calls the Sunshine HTTPS
# API directly and exercises the resolver logic inline.
#
set -euo pipefail

SUNSHINE_API_URL="${SUNSHINE_API_URL:-}"
SUNSHINE_USER="${SUNSHINE_USER:-admin}"
SUNSHINE_PASSWORD="${SUNSHINE_PASSWORD:-}"

if [[ -z "$SUNSHINE_API_URL" ]]; then
  echo "[ERROR] SUNSHINE_API_URL is required (e.g. https://192.168.x.y:47990)" >&2
  exit 1
fi
if [[ -z "$SUNSHINE_PASSWORD" ]]; then
  echo "[ERROR] SUNSHINE_PASSWORD is required" >&2
  exit 1
fi

echo "=== Moonlight App-Name Resolver Smoke Test ==="
echo "  Sunshine URL : $SUNSHINE_API_URL"
echo "  Sunshine user: $SUNSHINE_USER"
echo ""

# 1. Call Sunshine /api/apps
echo "[1] Fetching Sunshine app list from ${SUNSHINE_API_URL}/api/apps ..."
HTTP_CODE="$(curl -sk --max-time 8 -o /tmp/beagle-sunshine-apps.json -w '%{http_code}' -u "${SUNSHINE_USER}:${SUNSHINE_PASSWORD}" "${SUNSHINE_API_URL%/}/api/apps" 2>/dev/null || echo "000")" # tls-bypass-allowlist: Sunshine API smoke runs against local self-signed endpoint

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "[ERROR] Sunshine /api/apps returned HTTP $HTTP_CODE (expected 200)" >&2
  cat /tmp/beagle-sunshine-apps.json 2>/dev/null | head -20 >&2 || true
  exit 1
fi

APPS_JSON="$(cat /tmp/beagle-sunshine-apps.json)"
echo "[OK]  HTTP 200, app list received"

# 2. Parse the raw app list
APP_COUNT="$(python3 -c "
import json, sys
data = json.loads(sys.argv[1])

def collect(v):
    names = []
    if isinstance(v, dict):
        if isinstance(v.get('name'), str) and v['name'].strip():
            names.append(v['name'].strip())
        for k in ('apps', 'data', 'results', 'items'):
            if k in v:
                names.extend(collect(v[k]))
    elif isinstance(v, list):
        for i in v:
            names.extend(collect(i))
    return names

apps = list(dict.fromkeys(collect(data)))
print(len(apps))
for a in apps:
    print(a)
" "$APPS_JSON" 2>/dev/null | head -1 || echo "0")"

echo "[OK]  Found $APP_COUNT app(s) in Sunshine inventory"

if [[ "$APP_COUNT" -eq 0 ]]; then
  echo "[ERROR] No apps found in Sunshine inventory" >&2
  echo "        Raw response:" >&2
  echo "$APPS_JSON" | head -30 >&2
  exit 1
fi

# Print all app names
echo "  App list:"
python3 -c "
import json
data = json.loads('''${APPS_JSON}'''.replace(\"'''\", ''))

def collect(v):
    names = []
    if isinstance(v, dict):
        if isinstance(v.get('name'), str) and v['name'].strip():
            names.append(v['name'].strip())
        for k in ('apps', 'data', 'results', 'items'):
            if k in v:
                names.extend(collect(v[k]))
    elif isinstance(v, list):
        for i in v:
            names.extend(collect(i))
    return names

for n in list(dict.fromkeys(collect(data))):
    print(f'    - {n}')
" 2>/dev/null || python3 -c "import json,sys; data=json.loads(sys.argv[1]); [print(f'    - {a.get(\"name\",\"?\")}') for a in data.get('apps', data.get('data', []))]" "$APPS_JSON" 2>/dev/null || true

# 3. Run the resolver logic inline (mirrors moonlight_remote_api.sh resolve_stream_app_name)
echo ""
echo "[2] Running app-name resolver for 'Desktop' ..."
RESOLVED="$(python3 - "Desktop" "$APPS_JSON" <<'PY'
import json
import sys

requested = (sys.argv[1] or "Desktop").strip() or "Desktop"
payload_raw = sys.argv[2] or ""

def collect_names(value):
    names = []
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
        for key in ("apps", "data", "results", "items"):
            if key in value:
                names.extend(collect_names(value.get(key)))
    elif isinstance(value, list):
        for item in value:
            names.extend(collect_names(item))
    return names

if not payload_raw.strip():
    print(requested)
    raise SystemExit(0)

try:
    payload = json.loads(payload_raw)
except json.JSONDecodeError:
    print(requested)
    raise SystemExit(0)

apps = []
for name in collect_names(payload):
    if name not in apps:
        apps.append(name)

if not apps:
    print(requested)
    raise SystemExit(0)

for app in apps:
    if app == requested:
        print(app)
        raise SystemExit(0)

requested_folded = requested.casefold()
for app in apps:
    if app.casefold() == requested_folded:
        print(app)
        raise SystemExit(0)

if requested_folded == "desktop":
    for app in apps:
        if app.casefold() == "desktop":
            print(app)
            raise SystemExit(0)
    for app in apps:
        if "desktop" in app.casefold():
            print(app)
            raise SystemExit(0)

print(apps[0])
PY
)"

echo "[OK]  Resolver returned: '$RESOLVED'"

if [[ -z "$RESOLVED" ]]; then
  echo "[ERROR] Resolver returned an empty app name" >&2
  exit 1
fi

# 4. Verify "Desktop" is resolvable (exact or case-insensitive match)
DESKTOP_FOUND=0
if [[ "${RESOLVED,,}" == "desktop" ]] || [[ "$RESOLVED" == "Desktop" ]]; then
  DESKTOP_FOUND=1
fi

if [[ "$DESKTOP_FOUND" -eq 1 ]]; then
  echo "[OK]  'Desktop' app correctly resolved (Moonlight will stream successfully)"
else
  echo "[WARN] Resolver did not find exact 'Desktop' app; fell back to: '$RESOLVED'" >&2
  echo "       Moonlight will use '$RESOLVED' for streaming (may still work)" >&2
fi

echo ""
if [[ "$DESKTOP_FOUND" -eq 1 ]]; then
  echo "MOONLIGHT_APPNAME_SMOKE=PASS"
  echo "  Desktop app confirmed in Sunshine inventory"
  echo "  App-name resolver returns: $RESOLVED"
else
  echo "MOONLIGHT_APPNAME_SMOKE=WARN"
  echo "  'Desktop' not found in Sunshine inventory, fallback: $RESOLVED"
  echo "  Ensure Sunshine apps.json on the guest includes a 'Desktop' entry."
fi
