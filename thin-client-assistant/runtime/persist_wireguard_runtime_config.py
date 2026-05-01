#!/usr/bin/env python3
"""Persist WireGuard enrollment data into thin-client runtime env files."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _load_env_file(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    if not path.exists():
        return payload
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        payload[key.strip()] = value.strip()
    return payload


def _write_env_file(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{key}={value}\n" for key, value in payload.items()), encoding="utf-8")


def _json_env(value: Any) -> str:
    return json.dumps(str(value or ""))


def persist_wireguard_runtime_config(
    *,
    config_path: Path,
    credentials_path: Path,
    interface_ip: str,
    dns: str,
    server_public_key: str,
    server_endpoint: str,
    allowed_ips: str,
    private_key: str,
    preshared_key: str,
    keepalive: str,
) -> None:
    config_payload = _load_env_file(config_path)
    for key, value in (
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_ADDRESS", interface_ip),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_DNS", dns),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PUBLIC_KEY", server_public_key),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_ENDPOINT", server_endpoint),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE", keepalive),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_ALLOWED_IPS", allowed_ips),
    ):
        config_payload[key] = _json_env(value)
    _write_env_file(config_path, config_payload)

    credentials_payload = _load_env_file(credentials_path)
    for key, value in (
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PRIVATE_KEY", private_key),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PRESHARED_KEY", preshared_key),
    ):
        credentials_payload[key] = _json_env(value)
    _write_env_file(credentials_path, credentials_payload)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 10:
        raise SystemExit(
            "usage: persist_wireguard_runtime_config.py "
            "<thinclient_conf> <credentials_env> <interface_ip> <dns> "
            "<server_public_key> <server_endpoint> <allowed_ips> "
            "<private_key> <preshared_key> <keepalive>"
        )
    persist_wireguard_runtime_config(
        config_path=Path(args[0]),
        credentials_path=Path(args[1]),
        interface_ip=args[2],
        dns=args[3],
        server_public_key=args[4],
        server_endpoint=args[5],
        allowed_ips=args[6],
        private_key=args[7],
        preshared_key=args[8],
        keepalive=args[9],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
