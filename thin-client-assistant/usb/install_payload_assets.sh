#!/usr/bin/env bash

resolve_payload_url_from_manifest() {
  local manifest_file=""

  if [[ -n "$LIVE_MEDIUM" ]]; then
    manifest_file="$(candidate_manifest_path "$LIVE_MEDIUM" 1 2>/dev/null || true)"
  fi
  if [[ -z "$manifest_file" && -f "$CACHED_MANIFEST_FILE" ]]; then
    manifest_file="$CACHED_MANIFEST_FILE"
  fi
  [[ -n "$manifest_file" && -f "$manifest_file" ]] || return 1

  python3 "$USB_MANIFEST_HELPER" read-payload-source --path "$manifest_file"
}

download_install_payload_from_server() {
  local payload_url=""
  local payload_name=""
  local tmp_dir=""
  local tarball=""
  local checksum_url=""
  local checksum_file=""
  local asset_dir=""
  local remote_root_dir=""

  payload_url="${PVE_THIN_CLIENT_INSTALL_PAYLOAD_URL:-}"
  if [[ -z "$payload_url" ]]; then
    payload_url="$(resolve_payload_url_from_manifest 2>/dev/null || true)"
  fi
  if [[ -z "$payload_url" ]]; then
    log_msg "download_install_payload_from_server: no http(s) payload URL available in manifest; using bundled USB payload"
    return 1
  fi

  payload_name="$(basename "$payload_url")"
  [[ -n "$payload_name" ]] || {
    log_msg "download_install_payload_from_server: invalid payload URL basename: $payload_url"
    return 1
  }

  tmp_dir="$(mktemp -d /tmp/pve-thin-client-install-payload.XXXXXX)"
  tarball="$tmp_dir/$payload_name"
  log_msg "download_install_payload_from_server: downloading $payload_url"
  if ! curl --fail --show-error --location --retry 3 --retry-delay 2 "$payload_url" -o "$tarball"; then
    log_msg "download_install_payload_from_server: payload download failed from $payload_url"
    rm -rf "$tmp_dir" >/dev/null 2>&1 || true
    return 1
  fi

  checksum_url="${payload_url%/*}/SHA256SUMS"
  checksum_file="$tmp_dir/SHA256SUMS"
  if curl --fail --silent --location --retry 2 --retry-delay 1 "$checksum_url" -o "$checksum_file"; then
    if grep -F " ${payload_name}" "$checksum_file" >"$tmp_dir/payload.sha256"; then
      if ! ( cd "$tmp_dir" && sha256sum -c payload.sha256 >/dev/null ); then
        log_msg "download_install_payload_from_server: payload checksum mismatch for $payload_name"
        rm -rf "$tmp_dir" >/dev/null 2>&1 || true
        return 1
      fi
    fi
  else
    log_msg "download_install_payload_from_server: unable to download companion SHA256SUMS from $checksum_url (continuing)"
  fi

  if ! tar -xzf "$tarball" -C "$tmp_dir" >>"$LOG_FILE" 2>&1; then
    log_msg "download_install_payload_from_server: failed to extract $tarball"
    rm -rf "$tmp_dir" >/dev/null 2>&1 || true
    return 1
  fi

  asset_dir="$tmp_dir/dist/pve-thin-client-installer/live"
  remote_root_dir="$tmp_dir/thin-client-assistant"
  if [[ ! -f "$asset_dir/vmlinuz" || ! -f "$asset_dir/initrd.img" || ! -f "$asset_dir/filesystem.squashfs" ]]; then
    log_msg "download_install_payload_from_server: extracted payload missing live assets in $asset_dir"
    rm -rf "$tmp_dir" >/dev/null 2>&1 || true
    return 1
  fi

  if [[ -f "$asset_dir/SHA256SUMS" ]]; then
    if ! ( cd "$asset_dir" && sha256sum -c SHA256SUMS >/dev/null ); then
      log_msg "download_install_payload_from_server: live asset checksum validation failed for extracted payload"
      rm -rf "$tmp_dir" >/dev/null 2>&1 || true
      return 1
    fi
  fi

  REMOTE_PAYLOAD_TMP_DIR="$tmp_dir"
  INSTALL_LIVE_ASSET_DIR="$asset_dir"
  INSTALL_PAYLOAD_SOURCE_URL="$payload_url"
  if [[ -x "$remote_root_dir/installer/write-config.sh" ]]; then
    INSTALL_ROOT_DIR="$remote_root_dir"
  else
    INSTALL_ROOT_DIR="$ROOT_DIR"
  fi
  log_msg "download_install_payload_from_server: using remote payload assets from $INSTALL_LIVE_ASSET_DIR"
  return 0
}

prepare_install_assets() {
  INSTALL_LIVE_ASSET_DIR="$LIVE_ASSET_DIR"
  INSTALL_ROOT_DIR="$ROOT_DIR"

  if [[ "${PVE_THIN_CLIENT_FORCE_REMOTE_PAYLOAD:-0}" != "1" \
        && -f "$LIVE_ASSET_DIR/vmlinuz" \
        && -f "$LIVE_ASSET_DIR/initrd.img" \
        && -f "$LIVE_ASSET_DIR/filesystem.squashfs" ]]; then
    INSTALL_PAYLOAD_SOURCE_URL="$(resolve_payload_url_from_manifest 2>/dev/null || true)"
    log_msg "prepare_install_assets: using bundled USB payload assets under $LIVE_ASSET_DIR"
    return 0
  fi

  if download_install_payload_from_server; then
    return 0
  fi

  INSTALL_PAYLOAD_SOURCE_URL="$(resolve_payload_url_from_manifest 2>/dev/null || true)"
  log_msg "prepare_install_assets: falling back to bundled USB payload assets under $LIVE_ASSET_DIR"
  return 0
}

resolve_install_manifest_file() {
  local manifest_file=""

  if [[ -n "$LIVE_MEDIUM" ]]; then
    manifest_file="$(candidate_manifest_path "$LIVE_MEDIUM" 1 2>/dev/null || true)"
  fi
  if [[ -z "$manifest_file" && -f "$CACHED_MANIFEST_FILE" ]]; then
    manifest_file="$CACHED_MANIFEST_FILE"
  fi
  [[ -n "$manifest_file" && -f "$manifest_file" ]] || return 1
  printf '%s\n' "$manifest_file"
}

read_manifest_project_version() {
  local manifest_file="$1"
  [[ -f "$manifest_file" ]] || return 1

  python3 "$USB_MANIFEST_HELPER" read-project-version --path "$manifest_file"
}

resolve_install_project_version() {
  local manifest_file=""
  local project_version=""

  if [[ -n "$REMOTE_PAYLOAD_TMP_DIR" && -f "$REMOTE_PAYLOAD_TMP_DIR/VERSION" ]]; then
    tr -d ' \n\r' <"$REMOTE_PAYLOAD_TMP_DIR/VERSION"
    return 0
  fi

  manifest_file="$(resolve_install_manifest_file 2>/dev/null || true)"
  if [[ -n "$manifest_file" ]]; then
    project_version="$(read_manifest_project_version "$manifest_file" 2>/dev/null || true)"
    if [[ -n "$project_version" ]]; then
      printf '%s\n' "$project_version"
      return 0
    fi
  fi

  printf 'unknown\n'
}

write_install_manifest() {
  local manifest_file=""
  local project_version=""
  local bootstrap_version=""
  local installed_at=""
  local source_kind=""
  local payload_url=""
  local vmlinuz_sha=""
  local initrd_sha=""
  local squashfs_sha=""

  project_version="$(resolve_install_project_version)"
  manifest_file="$(resolve_install_manifest_file 2>/dev/null || true)"
  if [[ -n "$manifest_file" ]]; then
    bootstrap_version="$(read_manifest_project_version "$manifest_file" 2>/dev/null || true)"
  fi
  installed_at="$(date -Iseconds)"
  payload_url="${INSTALL_PAYLOAD_SOURCE_URL:-}"
  source_kind="bundled-usb"
  if [[ -n "$REMOTE_PAYLOAD_TMP_DIR" ]]; then
    source_kind="remote-payload"
  fi

  vmlinuz_sha="$(sha256sum "$INSTALL_LIVE_ASSET_DIR/vmlinuz" | awk '{print $1}')"
  initrd_sha="$(sha256sum "$INSTALL_LIVE_ASSET_DIR/initrd.img" | awk '{print $1}')"
  squashfs_sha="$(sha256sum "$INSTALL_LIVE_ASSET_DIR/filesystem.squashfs" | awk '{print $1}')"

  python3 "$USB_MANIFEST_HELPER" write-install-manifest \
    --path "$STATE_DIR/install-manifest.json" \
    --project-version "$project_version" \
    --installed-at "$installed_at" \
    --source-kind "$source_kind" \
    --payload-source-url "$payload_url" \
    --vmlinuz-sha256 "$vmlinuz_sha" \
    --initrd-sha256 "$initrd_sha" \
    --filesystem-squashfs-sha256 "$squashfs_sha" \
    --bootstrap-manifest-version "$bootstrap_version" \
    --installed-slot "a"
}
