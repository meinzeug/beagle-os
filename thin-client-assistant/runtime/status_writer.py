#!/usr/bin/env python3
"""Shared runtime status writers for thin-client runtime scripts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_launch_status(
    *,
    path: Path,
    mode: str,
    method: str,
    binary: str,
    target: str,
    profile_name: str,
    runtime_user: str,
) -> None:
    payload = {
        "timestamp": _timestamp(),
        "mode": str(mode or ""),
        "launch_method": str(method or ""),
        "binary": str(binary or ""),
        "target": str(target or ""),
        "profile_name": str(profile_name or ""),
        "runtime_user": str(runtime_user or ""),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_runtime_status(
    *,
    path: Path,
    boot_mode: str,
    mode: str,
    runtime_user: str,
    connection_method: str,
    profile_name: str,
    required_binary: str,
    beagle_stream_client_host: str,
    beagle_stream_client_app: str,
    binary_available: bool,
) -> None:
    lines = [
        f"timestamp={_timestamp()}",
        f"boot_mode={str(boot_mode or '')}",
        f"mode={str(mode or '')}",
        f"runtime_user={str(runtime_user or '')}",
        f"connection_method={str(connection_method or '')}",
        f"profile_name={str(profile_name or '')}",
        f"required_binary={str(required_binary or '')}",
        f"beagle_stream_client_host={str(beagle_stream_client_host or '')}",
        f"beagle_stream_client_app={str(beagle_stream_client_app or '')}",
        f"binary_available={'1' if binary_available else '0'}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write thin-client runtime status payloads")
    subparsers = parser.add_subparsers(dest="command", required=True)

    launch_parser = subparsers.add_parser("launch-status")
    launch_parser.add_argument("--path", required=True)
    launch_parser.add_argument("--mode", required=True)
    launch_parser.add_argument("--method", required=True)
    launch_parser.add_argument("--binary", required=True)
    launch_parser.add_argument("--target", required=True)
    launch_parser.add_argument("--profile-name", required=True)
    launch_parser.add_argument("--runtime-user", default="")

    runtime_parser = subparsers.add_parser("runtime-status")
    runtime_parser.add_argument("--path", required=True)
    runtime_parser.add_argument("--boot-mode", required=True)
    runtime_parser.add_argument("--mode", required=True)
    runtime_parser.add_argument("--runtime-user", default="")
    runtime_parser.add_argument("--connection-method", default="")
    runtime_parser.add_argument("--profile-name", required=True)
    runtime_parser.add_argument("--required-binary", required=True)
    runtime_parser.add_argument("--beagle-stream-client-host", default="")
    runtime_parser.add_argument("--beagle-stream-client-app", default="")
    runtime_parser.add_argument("--binary-available", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "launch-status":
        write_launch_status(
            path=Path(args.path),
            mode=args.mode,
            method=args.method,
            binary=args.binary,
            target=args.target,
            profile_name=args.profile_name,
            runtime_user=args.runtime_user,
        )
        return 0
    if args.command == "runtime-status":
        write_runtime_status(
            path=Path(args.path),
            boot_mode=args.boot_mode,
            mode=args.mode,
            runtime_user=args.runtime_user,
            connection_method=args.connection_method,
            profile_name=args.profile_name,
            required_binary=args.required_binary,
            beagle_stream_client_host=args.beagle_stream_client_host,
            beagle_stream_client_app=args.beagle_stream_client_app,
            binary_available=str(args.binary_available).strip() in {"1", "true", "yes", "on"},
        )
        return 0
    parser.error(f"unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
