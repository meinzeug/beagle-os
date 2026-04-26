#!/usr/bin/env bash
# scripts/lib/beagle_curl_safe.sh
# Reusable TLS-safe curl helpers for Beagle scripts.
#
# Usage:
#   source "$(dirname "$0")/lib/beagle_curl_safe.sh"
#   beagle_curl GET https://srv1.beagle-os.com/api/v1/health
#   beagle_curl_pinned GET https://... /etc/beagle/tls/ca.crt
#
# Environment variables (optional overrides):
#   BEAGLE_CA_CERT   — path to CA cert bundle  (default: /etc/beagle/tls/ca.crt)
#   BEAGLE_TLS_SKIP  — set to "1" ONLY in documented test scenarios (triggers warning)

set -euo pipefail

BEAGLE_CA_CERT="${BEAGLE_CA_CERT:-/etc/beagle/tls/ca.crt}"

# ---------------------------------------------------------------------------
# beagle_curl <method> <url> [extra curl args...]
#   Performs a curl request with TLS verification.
#   Uses system CA bundle if BEAGLE_CA_CERT doesn't exist.
# ---------------------------------------------------------------------------
beagle_curl() {
  local method="$1"
  local url="$2"
  shift 2

  local tls_args=()
  if [[ -f "$BEAGLE_CA_CERT" ]]; then
    tls_args+=(--cacert "$BEAGLE_CA_CERT")
  fi
  # Never add --insecure here; callers must use beagle_curl_insecure_test only

  curl --silent --show-error --fail \
    --request "$method" \
    "${tls_args[@]}" \
    "$@" \
    "$url"
}

# ---------------------------------------------------------------------------
# beagle_curl_pinned <method> <url> <ca_cert> [extra curl args...]
#   Like beagle_curl but with explicit CA cert (for internal services with
#   self-signed or private CA certs).
# ---------------------------------------------------------------------------
beagle_curl_pinned() {
  local method="$1"
  local url="$2"
  local ca_cert="$3"
  shift 3

  if [[ ! -f "$ca_cert" ]]; then
    echo "[beagle_curl_pinned] ERROR: CA cert not found: $ca_cert" >&2
    return 1
  fi

  curl --silent --show-error --fail \
    --request "$method" \
    --cacert "$ca_cert" \
    "$@" \
    "$url"
}

# ---------------------------------------------------------------------------
# beagle_curl_insecure_test <method> <url> [extra curl args...]
#   ONLY for automated test scripts where no real CA is available.
#   Prints a loud warning to stderr and requires BEAGLE_TLS_SKIP=1.
#   Must NOT be used in production code paths.
# ---------------------------------------------------------------------------
beagle_curl_insecure_test() {
  local method="$1"
  local url="$2"
  shift 2

  if [[ "${BEAGLE_TLS_SKIP:-0}" != "1" ]]; then
    echo "[beagle_curl_insecure_test] ERROR: BEAGLE_TLS_SKIP=1 required for TLS bypass" >&2
    echo "[beagle_curl_insecure_test] Do NOT use in production. Use beagle_curl_pinned instead." >&2
    return 1
  fi

  echo "[WARNING] TLS verification disabled for test call to: $url" >&2
  curl --silent --show-error --fail \
    --request "$method" \
    --insecure \
    "$@" \
    "$url"
}

# ---------------------------------------------------------------------------
# beagle_curl_tls_args
#   Outputs (via _BEAGLE_CURL_TLS_ARGS array) the reusable TLS curl args.
#   Use when you need to compose curl calls manually:
#
#     beagle_curl_tls_args
#     curl "${_BEAGLE_CURL_TLS_ARGS[@]}" ... "$url"
#
# Respects:
#   BEAGLE_CA_CERT          — path to CA bundle (default: /etc/beagle/tls/ca.crt)
#   BEAGLE_TLS_PINNED_PUBKEY — SHA-256 pubkey pin for --pinnedpubkey
#   BEAGLE_TLS_SKIP=1       — enables --insecure (test-only, warns loudly)
# ---------------------------------------------------------------------------
beagle_curl_tls_args() {
  _BEAGLE_CURL_TLS_ARGS=()

  if [[ "${BEAGLE_TLS_SKIP:-0}" == "1" ]]; then
    echo "[beagle_curl_tls_args][WARNING] TLS verification disabled via BEAGLE_TLS_SKIP — TEST USE ONLY" >&2
    _BEAGLE_CURL_TLS_ARGS=(--insecure)
    return 0
  fi

  if [[ -f "${BEAGLE_CA_CERT:-}" ]]; then
    _BEAGLE_CURL_TLS_ARGS+=(--cacert "$BEAGLE_CA_CERT")
  fi

  if [[ -n "${BEAGLE_TLS_PINNED_PUBKEY:-}" ]]; then
    _BEAGLE_CURL_TLS_ARGS+=(--pinnedpubkey "$BEAGLE_TLS_PINNED_PUBKEY")
  fi
}
