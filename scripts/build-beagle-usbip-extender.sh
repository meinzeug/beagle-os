#!/usr/bin/env bash
# Rebuild the evaluated USB/IP userspace server from pinned upstream sources.
# The binary is experimental and is NOT installed/enabled by this script.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
revision=52eeb5a84fa0c9e99fe178848c98bf2021a07512
expected=5940cc10e505529eff51582ecb27dfd33cae23b8d481fc3a27302cad4774ca2c
output="${1:-$root/dist/beagle-usbip-extender}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
if [[ -n "${BEAGLE_EXTENDER_ARCHIVE:-}" ]]; then
  cp -- "$BEAGLE_EXTENDER_ARCHIVE" "$tmp/source.tar.gz"
else
  curl --fail --silent --show-error --location --max-time 120 \
    "https://codeload.github.com/calibrae/extender/tar.gz/$revision" -o "$tmp/source.tar.gz"
fi
printf '%s  %s\n' "$expected" "$tmp/source.tar.gz" | sha256sum --check --status || {
  echo 'USB/IP source archive checksum does not match the pinned version' >&2
  exit 1
}
tar -xzf "$tmp/source.tar.gz" -C "$tmp"
src="$tmp/extender-$revision"
git -C "$src" apply --unidiff-zero --check "$root/third_party/usbip-extender/0001-preserve-active-configuration.patch"
git -C "$src" apply --unidiff-zero "$root/third_party/usbip-extender/0001-preserve-active-configuration.patch"
cargo build --manifest-path "$src/extender/Cargo.toml" --release --locked -p extender-cli
target_dir="${CARGO_TARGET_DIR:-$src/extender/target}"
install -D -m 0755 "$target_dir/release/extender" "$output"
printf 'Built experimental server: %s\n' "$output"
