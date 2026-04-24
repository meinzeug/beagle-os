#!/usr/bin/env bash
# Runtime value helpers: template expansion and related utilities.

# render_template: return the given value, printing it to stdout.
# Arguments are already expanded by the caller's shell, so this is a
# simple passthrough that makes the call-site intent explicit.
render_template() {
  printf '%s\n' "${1:-}"
}

# beagle_curl_tls_args: emit curl TLS flags to stdout, one per line.
#   $1 - URL (used only to determine if https is needed)
#   $2 - pinned pubkey fingerprint (sha256//... format), optional
#   $3 - path to CA cert file, optional
#
# Output (captured via mapfile) becomes an array of curl args.
# Precedence: pinned pubkey > CA cert file > accept self-signed (-k).
beagle_curl_tls_args() {
  local _url="${1:-}"
  local _pinned="${2:-}"
  local _ca_cert="${3:-}"

  # Only emit TLS flags for https URLs
  if [[ "$_url" != https://* ]]; then
    return 0
  fi

  if [[ -n "$_pinned" ]]; then
    # -k bypasses CA chain verification (needed for self-signed certs); 
    # --pinnedpubkey still enforces the expected public key as security guarantee
    printf '%s\n' "-k" "--pinnedpubkey" "$_pinned"
  elif [[ -n "$_ca_cert" && -f "$_ca_cert" ]]; then
    printf '%s\n' "--cacert" "$_ca_cert"
  else
    # No pin/CA configured – accept self-signed certificates
    printf '%s\n' "-k"
  fi
}
