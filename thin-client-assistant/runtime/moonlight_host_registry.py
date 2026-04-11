#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path


def _load_config_lines(config_path: Path) -> list[str]:
    return config_path.read_text(encoding="utf-8", errors="ignore").splitlines()


def _find_hosts_section(lines: list[str]) -> tuple[int | None, int]:
    section_start = None
    section_end = len(lines)
    for idx, line in enumerate(lines):
        if line.strip() == "[hosts]":
            section_start = idx
            for next_idx in range(idx + 1, len(lines)):
                if lines[next_idx].startswith("[") and lines[next_idx].endswith("]"):
                    section_end = next_idx
                    break
            break
    return section_start, section_end


def _parse_entries(lines: list[str], section_start: int, section_end: int) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in lines[section_start + 1 : section_end]:
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        entries[key.strip()] = value.strip()
    return entries


def command_seed_response(args: argparse.Namespace) -> int:
    response_path = Path(args.output)
    uniqueid = (args.uniqueid or "").strip()
    cert_b64 = (args.cert_b64 or "").strip()
    sunshine_name = (args.sunshine_name or "").strip()
    stream_port = (args.stream_port or "").strip()

    try:
        server_cert_pem = base64.b64decode(cert_b64.encode("ascii"), validate=True).decode("utf-8")
    except Exception:
        return 1

    if not uniqueid or "BEGIN CERTIFICATE" not in server_cert_pem:
        return 1

    payload = {
        "sunshine_server": {
            "uniqueid": uniqueid,
            "server_cert_pem": server_cert_pem,
            "sunshine_name": sunshine_name,
            "stream_port": stream_port,
        }
    }
    response_path.write_text(json.dumps(payload), encoding="utf-8")
    return 0


def command_is_configured(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    host = (args.host or "").strip()
    connect_host = (args.connect_host or "").strip()
    port = (args.port or "").strip()

    lines = _load_config_lines(config_path)
    section_start, section_end = _find_hosts_section(lines)
    if section_start is None:
        return 1

    entries = _parse_entries(lines, section_start, section_end)
    try:
        size = int(entries.get("size", "0") or "0")
    except ValueError:
        size = 0

    expected_hosts = {value for value in (host, connect_host) if value}
    expected_ports = {value for value in (port, "47984", "50100") if value}

    for idx in range(1, size + 1):
        uuid_value = entries.get(f"{idx}\\uuid", "").strip()
        cert_value = entries.get(f"{idx}\\srvcert", "").strip()
        if not uuid_value or "BEGIN CERTIFICATE" not in cert_value:
            continue

        manual_host = entries.get(f"{idx}\\manualaddress", "").strip()
        local_host = entries.get(f"{idx}\\localaddress", "").strip()
        manual_port = entries.get(f"{idx}\\manualport", "").strip()
        local_port = entries.get(f"{idx}\\localport", "").strip()

        if expected_hosts and manual_host not in expected_hosts and local_host not in expected_hosts:
            continue

        if expected_ports and manual_port and manual_port not in expected_ports and local_port and local_port not in expected_ports:
            continue

        return 0

    return 1


def command_sync_config(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    response_path = Path(args.response)
    host = (args.host or "").strip()
    connect_host = (args.connect_host or "").strip()
    port = (args.port or "").strip()

    payload = json.loads(response_path.read_text(encoding="utf-8"))
    server = payload.get("sunshine_server") if isinstance(payload, dict) else None
    if not isinstance(server, dict):
        return 1

    uniqueid = str(server.get("uniqueid", "") or "").strip()
    server_cert_pem = str(server.get("server_cert_pem", "") or "")
    sunshine_name = str(server.get("sunshine_name", "") or "").strip() or host or connect_host
    stream_port = str(server.get("stream_port", "") or "").strip()
    manual_host = connect_host or host
    manual_port = port or stream_port or "47984"

    if not uniqueid or "BEGIN CERTIFICATE" not in server_cert_pem or not manual_host:
        return 1

    lines = _load_config_lines(config_path)
    section_start, section_end = _find_hosts_section(lines)
    if section_start is None:
        if lines and lines[-1] != "":
            lines.append("")
        section_start = len(lines)
        section_end = section_start + 1
        lines.append("[hosts]")

    entries = _parse_entries(lines, section_start, section_end)
    existing_local_address = entries.get("1\\localaddress", "").strip()
    existing_local_port = entries.get("1\\localport", "").strip()
    existing_mac = entries.get("1\\mac", "@ByteArray()").strip() or "@ByteArray()"
    existing_nvidiasw = entries.get("1\\nvidiasw", "false").strip() or "false"
    existing_remote_address = entries.get("1\\remoteaddress", "").strip()
    existing_remote_port = entries.get("1\\remoteport", "0").strip() or "0"
    existing_ipv6_address = entries.get("1\\ipv6address", "").strip()
    existing_ipv6_port = entries.get("1\\ipv6port", "0").strip() or "0"

    escaped_cert = server_cert_pem.replace("\\", "\\\\").replace("\n", "\\n")
    updated_host_lines = [
        "1\\customname=false",
        f"1\\hostname={sunshine_name}",
        f"1\\ipv6address={existing_ipv6_address}",
        f"1\\ipv6port={existing_ipv6_port}",
        f"1\\localaddress={existing_local_address}",
        f"1\\localport={existing_local_port or manual_port}",
        f"1\\mac={existing_mac}",
        f"1\\manualaddress={manual_host}",
        f"1\\manualport={manual_port}",
        f"1\\nvidiasw={existing_nvidiasw}",
        f"1\\remoteaddress={existing_remote_address}",
        f"1\\remoteport={existing_remote_port}",
        f"1\\srvcert=@ByteArray({escaped_cert})",
        f"1\\uuid={uniqueid}",
        "size=1",
    ]

    lines = lines[: section_start + 1] + updated_host_lines + lines[section_end:]
    config_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed_response = subparsers.add_parser("seed-response")
    seed_response.add_argument("--output", required=True)
    seed_response.add_argument("--uniqueid", required=True)
    seed_response.add_argument("--cert-b64", required=True)
    seed_response.add_argument("--sunshine-name", default="")
    seed_response.add_argument("--stream-port", default="")
    seed_response.set_defaults(func=command_seed_response)

    is_configured = subparsers.add_parser("is-configured")
    is_configured.add_argument("--config", required=True)
    is_configured.add_argument("--host", default="")
    is_configured.add_argument("--connect-host", default="")
    is_configured.add_argument("--port", default="")
    is_configured.set_defaults(func=command_is_configured)

    sync_config = subparsers.add_parser("sync-config")
    sync_config.add_argument("--config", required=True)
    sync_config.add_argument("--response", required=True)
    sync_config.add_argument("--host", default="")
    sync_config.add_argument("--connect-host", default="")
    sync_config.add_argument("--port", default="")
    sync_config.set_defaults(func=command_sync_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
