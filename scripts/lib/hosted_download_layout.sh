#!/usr/bin/env bash

beagle_url_strip_trailing_slash() {
  printf '%s\n' "${1%/}"
}

beagle_host_origin_url() {
  local server_name="$1"
  local listen_port="$2"

  printf 'https://%s:%s\n' "$server_name" "$listen_port"
}

beagle_host_downloads_base_url() {
  local server_name="$1"
  local listen_port="$2"
  local downloads_path="$3"

  printf '%s%s\n' \
    "$(beagle_host_origin_url "$server_name" "$listen_port")" \
    "$downloads_path"
}

beagle_public_artifact_base_url() {
  local downloads_base_url="$1"
  local explicit_public_base_url="${2:-}"

  if [[ -n "$explicit_public_base_url" ]]; then
    beagle_url_strip_trailing_slash "$explicit_public_base_url"
    return 0
  fi

  beagle_url_strip_trailing_slash "$downloads_base_url"
}

beagle_hosted_download_url() {
  local downloads_base_url="$1"
  local filename="$2"

  printf '%s/%s\n' "$(beagle_url_strip_trailing_slash "$downloads_base_url")" "$filename"
}

beagle_public_release_artifact_url() {
  local public_artifact_base_url="$1"
  local filename="$2"

  printf '%s/%s\n' "$(beagle_url_strip_trailing_slash "$public_artifact_base_url")" "$filename"
}

beagle_vm_api_url_template() {
  local server_name="$1"
  local listen_port="$2"
  local suffix="$3"

  printf '%s/beagle-api/api/v1/vms/{vmid}/%s\n' \
    "$(beagle_host_origin_url "$server_name" "$listen_port")" \
    "$suffix"
}
