#!/usr/bin/env bash

moonlight_curl_bin() {
	printf '%s\n' "${BEAGLE_CURL_BIN:-curl}"
}

moonlight_hostname_value() {
	local hostname_bin="${BEAGLE_HOSTNAME_BIN:-hostname}"

	if [[ -n "${PVE_THIN_CLIENT_HOSTNAME:-}" ]]; then
		printf '%s\n' "${PVE_THIN_CLIENT_HOSTNAME}"
		return 0
	fi

	"$hostname_bin"
}

moonlight_client_device_name() {
	printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_CLIENT_NAME:-$(moonlight_hostname_value)}"
}

json_bool() {
	local payload="$1"
	python3 - "$payload" <<'PY'
import json
import sys

try:
		data = json.loads(sys.argv[1] or "{}")
except json.JSONDecodeError:
		raise SystemExit(1)

print("1" if bool(data.get("status")) else "0")
PY
}

submit_sunshine_pin() {
	local api_url username password pin name response
	local curl_bin
	local -a curl_args tls_args

	api_url="$(selected_sunshine_api_url)"
	username="${PVE_THIN_CLIENT_SUNSHINE_USERNAME:-}"
	password="${PVE_THIN_CLIENT_SUNSHINE_PASSWORD:-}"
	pin="${PVE_THIN_CLIENT_SUNSHINE_PIN:-}"
	name="$(moonlight_client_device_name)"

	[[ -n "$api_url" && -n "$username" && -n "$password" && -n "$pin" ]] || return 1

	curl_bin="$(moonlight_curl_bin)"
	curl_args=("$curl_bin" -fsS --connect-timeout 2 --max-time 4 --user "${username}:${password}" -H 'Content-Type: application/json')
	mapfile -t tls_args < <(beagle_curl_tls_args "$api_url" "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY:-}" "${PVE_THIN_CLIENT_SUNSHINE_CA_CERT:-}")
	curl_args+=("${tls_args[@]}")

	response="$(
		"${curl_args[@]}" \
			--data "{\"pin\":\"${pin}\",\"name\":\"${name}\"}" \
			"${api_url%/}/api/pin"
	)" || return 1

	[[ "$(json_bool "$response")" == "1" ]]
}

sunshine_apps_json() {
	local api_url username password
	local curl_bin
	local -a curl_args tls_args

	api_url="$(selected_sunshine_api_url)"
	username="${PVE_THIN_CLIENT_SUNSHINE_USERNAME:-}"
	password="${PVE_THIN_CLIENT_SUNSHINE_PASSWORD:-}"

	[[ -n "$api_url" && -n "$username" && -n "$password" ]] || return 1

	curl_bin="$(moonlight_curl_bin)"
	curl_args=("$curl_bin" -fsS --connect-timeout 2 --max-time 5 --user "${username}:${password}")
	mapfile -t tls_args < <(beagle_curl_tls_args "$api_url" "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY:-}" "${PVE_THIN_CLIENT_SUNSHINE_CA_CERT:-}")
	curl_args+=("${tls_args[@]}")

	"${curl_args[@]}" "${api_url%/}/api/apps"
}

resolve_stream_app_name() {
	local requested apps_json

	requested="${1:-Desktop}"
	apps_json="$(sunshine_apps_json 2>/dev/null || true)"

	python3 - "$requested" "$apps_json" <<'PY'
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
}
