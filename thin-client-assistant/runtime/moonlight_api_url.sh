#!/usr/bin/env bash

rewrite_url_host() {
  python3 - "$1" "$2" <<'PY'
from urllib.parse import urlsplit, urlunsplit
import sys

url = (sys.argv[1] or "").strip()
host = (sys.argv[2] or "").strip()
if not url or not host:
    raise SystemExit(1)

parts = urlsplit(url)
if not parts.scheme or not parts.netloc:
    raise SystemExit(1)

userinfo = ""
if "@" in parts.netloc:
    userinfo, _, _ = parts.netloc.rpartition("@")
    userinfo = f"{userinfo}@"

port = f":{parts.port}" if parts.port else ""
netloc = f"{userinfo}{host}{port}"
print(urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)))
PY
}

sunshine_api_url() {
  local configured host
  configured="$(render_template "${PVE_THIN_CLIENT_SUNSHINE_API_URL:-}" 2>/dev/null || true)"
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi

  host="$(moonlight_host)"
  if [[ -n "$host" ]]; then
    printf 'https://%s:47990\n' "$host"
  fi
}

effective_sunshine_api_url() {
  local api_url host connect_host rewritten

  api_url="$1"
  host="$2"
  connect_host="${3:-}"

  [[ -n "$api_url" ]] || return 1
  [[ -n "$host" ]] || {
    printf '%s\n' "$api_url"
    return 0
  }

  if prefer_ipv4 && [[ -n "$connect_host" ]] && [[ "$connect_host" != "$host" ]]; then
    rewritten="$(rewrite_url_host "$api_url" "$connect_host" 2>/dev/null || true)"
    if [[ -n "$rewritten" ]]; then
      printf '%s\n' "$rewritten"
      return 0
    fi
  fi

  printf '%s\n' "$api_url"
}

selected_sunshine_api_url() {
  local api_url host connect_host effective_api_url

  api_url="$(sunshine_api_url)"
  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  effective_api_url="$(effective_sunshine_api_url "$api_url" "$host" "$connect_host" 2>/dev/null || printf '%s\n' "$api_url")"
  printf '%s\n' "$effective_api_url"
}
