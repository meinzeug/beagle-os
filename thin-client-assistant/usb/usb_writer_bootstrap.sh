#!/usr/bin/env bash

allocate_bootstrap_dir() {
  local bases=()
  local base=""
  local candidate=""

  [[ -n "${PVE_DCV_BOOTSTRAP_BASE:-}" ]] && bases+=("${PVE_DCV_BOOTSTRAP_BASE}")
  [[ -n "${TMPDIR:-}" ]] && bases+=("${TMPDIR}")
  bases+=("/var/tmp" "/tmp")

  for base in "${bases[@]}"; do
    [[ -d "$base" && -w "$base" ]] || continue
    candidate="$(mktemp -d "$base/pve-dcv-usb.XXXXXX" 2>/dev/null || true)"
    if [[ -n "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  mktemp -d
}

bootstrap_repo_root() {
  local tarball extracted checksum_file payload_name checksum_url checksum_log bootstrap_url
  local cache_dir cached_tarball download_target used_cached checksum_entry_found checksum_ok
  local -a checksum_curl_args download_curl_args
  if [[ -d "$REPO_ROOT/thin-client-assistant" && -x "$REPO_ROOT/scripts/build-thin-client-installer.sh" ]]; then
    return 0
  fi

  require_tool curl
  require_tool tar

  BOOTSTRAP_DIR="$(allocate_bootstrap_dir)"
  extracted="$BOOTSTRAP_DIR/extracted"
  mkdir -p "$extracted"
  chmod 0755 "$BOOTSTRAP_DIR" "$extracted"

  bootstrap_url="${RELEASE_BOOTSTRAP_URL:-${RELEASE_PAYLOAD_URL:-}}"
  [[ -n "$bootstrap_url" ]] || {
    echo "Standalone mode requires RELEASE_BOOTSTRAP_URL to point at a hosted thin-client USB bootstrap tarball." >&2
    echo "Use the host-provided installer from https://<beagle-host>/beagle-downloads/ or export RELEASE_BOOTSTRAP_URL manually." >&2
    exit 1
  }

  payload_name="$(basename "${bootstrap_url%%\?*}")"
  tarball="$BOOTSTRAP_DIR/$payload_name"
  cache_dir="$BOOTSTRAP_CACHE_DIR"
  cached_tarball=""
  used_cached="0"
  checksum_entry_found="0"
  checksum_ok="0"

  checksum_curl_args=(--fail --silent --location --retry 2 --retry-delay 1)
  download_curl_args=(--fail --show-error --location --retry 3 --retry-delay 2)
  if [[ "$BOOTSTRAP_DISABLE_CACHE" == "1" ]]; then
    cache_dir=""
    checksum_curl_args+=(-H 'Cache-Control: no-cache' -H 'Pragma: no-cache')
    download_curl_args+=(-H 'Cache-Control: no-cache' -H 'Pragma: no-cache')
  else
    download_curl_args+=(--continue-at -)
  fi

  if [[ -n "$cache_dir" ]]; then
    if mkdir -p "$cache_dir" 2>/dev/null; then
      cached_tarball="$cache_dir/$payload_name"
    fi
  fi

  checksum_file="$BOOTSTRAP_DIR/SHA256SUMS"
  checksum_url="${bootstrap_url%/*}/SHA256SUMS"
  checksum_log="$BOOTSTRAP_DIR/checksum-download.log"

  if [[ -n "$cached_tarball" && -f "$cached_tarball" ]]; then
    echo "Using cached bootstrap candidate: $cached_tarball"
    cp -f "$cached_tarball" "$tarball"
    used_cached="1"
  fi

  if curl "${checksum_curl_args[@]}" "$checksum_url" -o "$checksum_file" 2>"$checksum_log"; then
    if grep -F " ${payload_name}" "$checksum_file" >"$BOOTSTRAP_DIR/payload.sha256"; then
      checksum_entry_found="1"
      if [[ "$used_cached" == "1" ]]; then
        if (
          cd "$BOOTSTRAP_DIR"
          sha256sum -c payload.sha256 >/dev/null
        ); then
          checksum_ok="1"
        else
          checksum_ok="0"
        fi
      fi
    else
      if [[ "$REQUIRE_CHECKSUMS" == "1" ]]; then
        echo "Checksum verification is required but SHA256SUMS has no entry for $payload_name." >&2
        exit 1
      fi
      echo "Warning: no checksum entry found for $payload_name, continuing without SHA256 verification." >&2
    fi
  else
    if [[ "$REQUIRE_CHECKSUMS" == "1" ]]; then
      echo "Checksum verification is required but companion SHA256SUMS could not be downloaded from $checksum_url." >&2
      if [[ -s "$checksum_log" ]]; then
        cat "$checksum_log" >&2
      fi
      exit 1
    fi
    echo "Warning: unable to download companion SHA256SUMS, continuing without payload verification." >&2
  fi

  if [[ "$used_cached" == "1" ]]; then
    if [[ "$checksum_entry_found" == "1" && "$checksum_ok" == "1" ]]; then
      echo "Cached bootstrap verified successfully."
    elif [[ "$checksum_entry_found" == "1" ]]; then
      echo "Cached bootstrap checksum failed, re-downloading..." >&2
      used_cached="0"
    else
      echo "Proceeding with unverified cached bootstrap (no checksum entry)." >&2
    fi
  fi

  if [[ "$used_cached" != "1" ]]; then
    download_target="$tarball"
    if [[ -n "$cached_tarball" ]]; then
      download_target="$cached_tarball"
    fi
    echo "Downloading thin-client bootstrap bundle from $bootstrap_url ..."
    curl "${download_curl_args[@]}" "$bootstrap_url" -o "$download_target"
    if [[ "$download_target" != "$tarball" ]]; then
      cp -f "$download_target" "$tarball"
    fi
    if [[ -n "$cached_tarball" ]]; then
      cp -f "$tarball" "$cached_tarball"
    fi

    if [[ "$checksum_entry_found" == "1" ]]; then
      (
        cd "$BOOTSTRAP_DIR"
        sha256sum -c payload.sha256 >/dev/null
      )
    fi
  fi

  tar -xzf "$tarball" -C "$extracted"
  REPO_ROOT="$extracted"
  DIST_DIR="$REPO_ROOT/dist/pve-thin-client-installer"
  ASSET_DIR="$DIST_DIR/live"
  BOOTSTRAPPED_STANDALONE="1"
  PROJECT_VERSION="$(project_version_from_root)"
  GRUB_BACKGROUND_SRC="$REPO_ROOT/thin-client-assistant/usb/assets/grub-background.jpg"
}

payload_has_live_assets() {
  [[ -f "$ASSET_DIR/filesystem.squashfs" && -f "$ASSET_DIR/vmlinuz" && -f "$ASSET_DIR/initrd.img" && -f "$ASSET_DIR/SHA256SUMS" ]]
}

download_installer_iso() {
  local iso_url iso_name iso_path cache_dir cached_iso checksum_file checksum_url download_target
  local checksum_entry_found used_cached checksum_ok
  local -a checksum_curl_args download_curl_args

  iso_url="${RELEASE_ISO_URL:-}"
  [[ -n "$iso_url" ]] || return 1

  require_tool curl
  require_tool xorriso

  [[ -n "$BOOTSTRAP_DIR" && -d "$BOOTSTRAP_DIR" ]] || BOOTSTRAP_DIR="$(allocate_bootstrap_dir)"

  iso_name="$(basename "${iso_url%%\?*}")"
  [[ -n "$iso_name" ]] || iso_name="beagle-os-installer-amd64.iso"
  iso_path="$BOOTSTRAP_DIR/$iso_name"
  cache_dir="$BOOTSTRAP_CACHE_DIR/iso"
  cached_iso=""
  used_cached="0"
  checksum_entry_found="0"
  checksum_ok="0"

  checksum_curl_args=(--fail --silent --location --retry 2 --retry-delay 1)
  download_curl_args=(--fail --show-error --location --retry 3 --retry-delay 2)
  if [[ "$BOOTSTRAP_DISABLE_CACHE" == "1" ]]; then
    cache_dir=""
    checksum_curl_args+=(-H 'Cache-Control: no-cache' -H 'Pragma: no-cache')
    download_curl_args+=(-H 'Cache-Control: no-cache' -H 'Pragma: no-cache')
  else
    download_curl_args+=(--continue-at -)
  fi

  if [[ -n "$cache_dir" ]] && mkdir -p "$cache_dir" 2>/dev/null; then
    cached_iso="$cache_dir/$iso_name"
  fi

  checksum_file="$BOOTSTRAP_DIR/${iso_name}.sha256sums"
  checksum_url="${iso_url%/*}/SHA256SUMS"
  if [[ -n "$cached_iso" && -f "$cached_iso" ]]; then
    cp -f "$cached_iso" "$iso_path"
    used_cached="1"
  fi

  if curl "${checksum_curl_args[@]}" "$checksum_url" -o "$checksum_file" 2>/dev/null; then
    if grep -F " ${iso_name}" "$checksum_file" >"$BOOTSTRAP_DIR/${iso_name}.sha256"; then
      checksum_entry_found="1"
      if [[ "$used_cached" == "1" ]]; then
        if (
          cd "$BOOTSTRAP_DIR"
          sha256sum -c "${iso_name}.sha256" >/dev/null
        ); then
          checksum_ok="1"
        else
          checksum_ok="0"
        fi
      fi
    fi
  fi

  if [[ "$used_cached" == "1" && "$checksum_entry_found" == "1" && "$checksum_ok" != "1" ]]; then
    used_cached="0"
  fi

  if [[ "$used_cached" != "1" ]]; then
    download_target="$iso_path"
    if [[ -n "$cached_iso" ]]; then
      download_target="$cached_iso"
    fi
    echo "Downloading Beagle installer ISO from $iso_url ..." >&2
    curl "${download_curl_args[@]}" "$iso_url" -o "$download_target"
    if [[ "$download_target" != "$iso_path" ]]; then
      cp -f "$download_target" "$iso_path"
    fi
    if [[ "$checksum_entry_found" == "1" ]]; then
      (
        cd "$BOOTSTRAP_DIR"
        sha256sum -c "${iso_name}.sha256" >/dev/null
      )
    fi
  fi

  printf '%s\n' "$iso_path"
}

populate_live_assets_from_iso() {
  local iso_path

  [[ -n "${RELEASE_ISO_URL:-}" ]] || return 1

  iso_path="$(download_installer_iso)"
  install -d -m 0755 "$ASSET_DIR"
  rm -f "$ASSET_DIR"/vmlinuz "$ASSET_DIR"/initrd.img "$ASSET_DIR"/filesystem.squashfs "$ASSET_DIR"/SHA256SUMS
  xorriso -osirrox on -indev "$iso_path" -extract /live/vmlinuz "$ASSET_DIR/vmlinuz" >/dev/null 2>&1
  xorriso -osirrox on -indev "$iso_path" -extract /live/initrd.img "$ASSET_DIR/initrd.img" >/dev/null 2>&1
  xorriso -osirrox on -indev "$iso_path" -extract /live/filesystem.squashfs "$ASSET_DIR/filesystem.squashfs" >/dev/null 2>&1
  xorriso -osirrox on -indev "$iso_path" -extract /live/SHA256SUMS "$ASSET_DIR/SHA256SUMS" >/dev/null 2>&1
}

ensure_live_assets() {
  if payload_has_live_assets; then
    return 0
  fi

  if [[ -n "${RELEASE_ISO_URL:-}" ]]; then
    populate_live_assets_from_iso
    return 0
  fi

  if [[ "$BOOTSTRAPPED_STANDALONE" == "1" ]]; then
    echo "Hosted payload bundle is incomplete: missing live installer assets under $ASSET_DIR" >&2
    echo "Refresh host artifacts on the Beagle server and download a fresh installer." >&2
    exit 1
  fi

  "$REPO_ROOT/scripts/build-thin-client-installer.sh"
}

validate_live_assets() {
  if [[ ! -f "$ASSET_DIR/SHA256SUMS" ]]; then
    echo "Missing live asset checksum file: $ASSET_DIR/SHA256SUMS" >&2
    exit 1
  fi

  (
    cd "$ASSET_DIR"
    sha256sum -c SHA256SUMS
  )
}
