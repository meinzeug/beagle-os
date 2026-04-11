#!/usr/bin/env bash

prepare_geforcenow_environment() {
  local runtime_home="${1:-/home/$(runtime_user_name)}"
  local storage_root medium home_dir data_dir cache_dir config_dir tmp_dir

  storage_root="${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-}"
  if [[ -z "$storage_root" ]]; then
    medium="$(live_medium_dir 2>/dev/null || true)"
    if [[ -n "$medium" ]]; then
      storage_root="$medium/pve-thin-client/state/gfn"
    else
      storage_root="$(beagle_state_dir)/gfn"
    fi
  fi

  home_dir="$storage_root/home"
  data_dir="$home_dir/.local/share"
  cache_dir="$home_dir/.cache"
  config_dir="$home_dir/.config"
  tmp_dir="$storage_root/tmp"

  for dir in \
    "$storage_root" \
    "$home_dir" \
    "$home_dir/.local" \
    "$data_dir" \
    "$home_dir/.var/app" \
    "$cache_dir" \
    "$config_dir" \
    "$tmp_dir"
  do
    ensure_runtime_owned_dir "$dir" 0700 || return 1
  done

  ensure_runtime_owned_tree "$storage_root" || true

  export PVE_THIN_CLIENT_GFN_STORAGE_ROOT="$storage_root"
  export PVE_THIN_CLIENT_GFN_RUNTIME_HOME="$runtime_home"
  export HOME="$home_dir"
  export XDG_DATA_HOME="$data_dir"
  export XDG_CACHE_HOME="$cache_dir"
  export XDG_CONFIG_HOME="$config_dir"
  export FLATPAK_USER_DIR="$data_dir/flatpak"
  export FLATPAK_DOWNLOAD_TMPDIR="$tmp_dir"

  ensure_runtime_owned_dir "$FLATPAK_USER_DIR" 0700 || return 1
  ensure_runtime_owned_dir "$XDG_CACHE_HOME" 0700 || return 1
  ensure_runtime_owned_dir "$XDG_CONFIG_HOME" 0700 || return 1
  ensure_runtime_owned_dir "$HOME/.var/app" 0700 || return 1

  return 0
}
