#!/usr/bin/env python3
"""Repair persisted BeagleStream client metadata for existing Beagle VMs."""

from __future__ import annotations

import argparse
import sys

import service_registry as sr


DEFAULTS = {
    "beagle-stream-client-resolution": "1920x1080",
    "beagle-stream-client-fps": "60",
    "beagle-stream-client-bitrate": "32000",
    "beagle-stream-client-video-codec": "H.264",
    "beagle-stream-client-video-decoder": "software",
    "beagle-stream-client-audio-config": "stereo",
}


def _rewrite_description(description: str, updates: dict[str, str]) -> tuple[str, bool]:
    lines: list[str] = []
    seen: set[str] = set()

    for raw_line in str(description or "").splitlines():
        if ":" not in raw_line:
            lines.append(raw_line)
            continue
        key, _value = raw_line.split(":", 1)
        normalized_key = key.strip().lower()
        if normalized_key in updates:
            lines.append(f"{normalized_key}: {updates[normalized_key]}")
            seen.add(normalized_key)
            continue
        lines.append(raw_line)

    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}: {value}")

    new_description = "\n".join(lines).rstrip() + "\n"
    return new_description, new_description != str(description or "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vmid", type=int, required=True)
    parser.add_argument("--resolution", default=DEFAULTS["beagle-stream-client-resolution"])
    parser.add_argument("--fps", default=DEFAULTS["beagle-stream-client-fps"])
    parser.add_argument("--bitrate", default=DEFAULTS["beagle-stream-client-bitrate"])
    parser.add_argument("--video-codec", default=DEFAULTS["beagle-stream-client-video-codec"])
    parser.add_argument("--video-decoder", default=DEFAULTS["beagle-stream-client-video-decoder"])
    parser.add_argument("--audio-config", default=DEFAULTS["beagle-stream-client-audio-config"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    vm = sr.find_vm(args.vmid, refresh=True)
    if vm is None:
        print(f"VM {args.vmid} not found", file=sys.stderr)
        return 1

    updates = {
        "beagle-stream-client-resolution": args.resolution,
        "beagle-stream-client-fps": args.fps,
        "beagle-stream-client-bitrate": args.bitrate,
        "beagle-stream-client-video-codec": args.video_codec,
        "beagle-stream-client-video-decoder": args.video_decoder,
        "beagle-stream-client-audio-config": args.audio_config,
    }
    config = sr.get_vm_config(vm.node, vm.vmid)
    new_description, changed = _rewrite_description(str(config.get("description") or ""), updates)

    if changed and not args.dry_run:
        sr.HOST_PROVIDER.set_vm_description(vm.vmid, new_description)
        sr.invalidate_vm_cache(vm.vmid)

    profile = sr.vm_profile_service().build_profile(sr.find_vm(args.vmid, refresh=True))
    summary = {
        "vmid": vm.vmid,
        "changed": changed,
        "dry_run": bool(args.dry_run),
        "resolution": profile.get("beagle_stream_client_resolution"),
        "fps": profile.get("beagle_stream_client_fps"),
        "bitrate": profile.get("beagle_stream_client_bitrate"),
        "video_decoder": profile.get("beagle_stream_client_video_decoder"),
    }
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
