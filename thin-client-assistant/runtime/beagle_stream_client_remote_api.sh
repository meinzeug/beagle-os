#!/usr/bin/env bash

beagle_stream_client_curl_bin() {
	printf '%s\n' "${BEAGLE_CURL_BIN:-curl}"
}

beagle_stream_client_hostname_value() {
	local hostname_bin="${BEAGLE_HOSTNAME_BIN:-hostname}"

	if [[ -n "${PVE_THIN_CLIENT_HOSTNAME:-}" ]]; then
		printf '%s\n' "${PVE_THIN_CLIENT_HOSTNAME}"
		return 0
	fi

	"$hostname_bin"
}

beagle_stream_client_device_name() {
	printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_NAME:-$(beagle_stream_client_hostname_value)}"
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

submit_beagle_stream_server_pairing_token() {
 local api_url username password token name response payload
	local curl_bin
	local -a curl_args tls_args

	api_url="$(selected_beagle_stream_server_api_url)"
	username="${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_USERNAME:-}"
	password="${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PASSWORD:-}"
	 token="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TOKEN:-}"
	name="$(beagle_stream_client_device_name)"

	 [[ -n "$api_url" && -n "$username" && -n "$password" && -n "$token" ]] || return 1

	curl_bin="$(beagle_stream_client_curl_bin)"
	curl_args=("$curl_bin" -fsS --connect-timeout 2 --max-time 4 --user "${username}:${password}" -H 'Content-Type: application/json')
	mapfile -t tls_args < <(beagle_curl_tls_args "$api_url" "${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PINNED_PUBKEY:-}" "${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_CA_CERT:-}")
	curl_args+=("${tls_args[@]}")
	payload="$(
		python3 - "$token" "$name" <<'PY'
import json
import sys

secret = sys.argv[1]
name = sys.argv[2]
print(json.dumps({"access_token": secret, "token": secret, "name": name}, separators=(",", ":")))
PY
	)"

	response="$(
		"${curl_args[@]}" \
			--data "$payload" \
		 "${api_url%/}/api/pair-token"
	)" || return 1

	[[ "$(json_bool "$response")" == "1" ]]
}

	submit_beagle_stream_server_pin() {
	 submit_beagle_stream_server_pairing_token "$@"
	}

beagle_stream_server_apps_json() {
	local api_url username password host connect_host port api_port candidate
	local curl_bin
	local -a curl_args tls_args candidates

	api_url="$(selected_beagle_stream_server_api_url)"
	username="${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_USERNAME:-}"
	password="${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PASSWORD:-}"

	[[ -n "$username" && -n "$password" ]] || return 1

	if [[ -n "$api_url" ]]; then
		candidates+=("$api_url")
	fi

	host="$(beagle_stream_client_host 2>/dev/null || true)"
	connect_host="$(beagle_stream_client_connect_host 2>/dev/null || true)"
	port="$(beagle_stream_client_port 2>/dev/null || true)"
	api_port="50001"
	if [[ "$port" =~ ^[0-9]+$ ]] && [[ "$port" -gt 0 ]]; then
		api_port="$((port + 1))"
	fi

	for candidate in "$connect_host" "$host"; do
		[[ -n "$candidate" ]] || continue
		candidates+=("https://${candidate}:${api_port}")
		candidates+=("https://${candidate}:50001")
	done

	curl_bin="$(beagle_stream_client_curl_bin)"
	curl_args=("$curl_bin" -fsS --connect-timeout 2 --max-time 5 --user "${username}:${password}")

	for candidate in "${candidates[@]}"; do
		[[ -n "$candidate" ]] || continue
		mapfile -t tls_args < <(beagle_curl_tls_args "$candidate" "${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PINNED_PUBKEY:-}" "${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_CA_CERT:-}")
		if "${curl_args[@]}" "${tls_args[@]}" "${candidate%/}/api/apps"; then
			return 0
		fi
	done

	return 1
}

resolve_stream_app_name() {
	local requested apps_json

	requested="${1:-Desktop}"
	apps_json="$(beagle_stream_server_apps_json 2>/dev/null || true)"

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
