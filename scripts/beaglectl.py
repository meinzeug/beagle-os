#!/usr/bin/env python3
"""beaglectl: lightweight Beagle API CLI.

This is a dependency-free CLI built on argparse + urllib to keep
runtime requirements minimal on hosts and recovery systems.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "beaglectl" / "config.json"


def read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_config(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_setting(args: argparse.Namespace, cfg: dict[str, Any], key: str, env_name: str = "") -> str:
    cli_value = getattr(args, key, "")
    if cli_value:
        return str(cli_value)
    if env_name:
        env_value = os.environ.get(env_name, "").strip()
        if env_value:
            return env_value
    return str(cfg.get(key, "")).strip()


def api_request(server: str, method: str, path: str, token: str = "", body: dict[str, Any] | None = None) -> Any:
    base = server.rstrip("/")
    target = f"{base}{path if path.startswith('/') else '/' + path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(target, data=data, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if not raw:
                return {"ok": True, "status": response.status}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"ok": True, "status": response.status, "raw": raw}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        detail: dict[str, Any] = {"ok": False, "status": exc.code, "error": exc.reason}
        if raw:
            try:
                detail["body"] = json.loads(raw)
            except json.JSONDecodeError:
                detail["body"] = raw
        return detail
    except urllib.error.URLError as exc:
        return {"ok": False, "status": 0, "error": str(exc)}


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=True))


def print_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        print("(no entries)")
        return
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            widths[col] = max(widths[col], len(str(row.get(col, ""))))
    header = "  ".join(col.ljust(widths[col]) for col in columns)
    sep = "  ".join("-" * widths[col] for col in columns)
    print(header)
    print(sep)
    for row in rows:
        print("  ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns))


def handle_config(args: argparse.Namespace, cfg_path: Path, cfg: dict[str, Any]) -> int:
    if args.config_action == "init":
        merged = {
            "server": args.server or cfg.get("server", "http://127.0.0.1:9088"),
            "token": args.token or cfg.get("token", ""),
            "tenant": cfg.get("tenant", "default"),
        }
        write_config(cfg_path, merged)
        print(f"Initialized config at {cfg_path}")
        return 0
    if args.config_action == "set":
        cfg[args.key] = args.value
        write_config(cfg_path, cfg)
        print(f"Updated {args.key} in {cfg_path}")
        return 0
    if args.config_action == "show":
        print_json(cfg)
        return 0
    print("Unknown config action", file=sys.stderr)
    return 2


def normalize_vm_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("inventory"), list):
        rows: list[dict[str, Any]] = []
        for item in payload["inventory"]:
            if str(item.get("type", "")).lower() != "vm":
                continue
            rows.append(
                {
                    "vmid": item.get("vmid", ""),
                    "name": item.get("name", ""),
                    "state": item.get("state", ""),
                    "node": item.get("node", ""),
                }
            )
        return rows
    return []


def handle_vm(args: argparse.Namespace, server: str, token: str) -> int:
    if args.vm_action == "list":
        payload = api_request(server, "GET", "/api/v1/vms", token=token)
        if args.json:
            print_json(payload)
            return 0
        rows = normalize_vm_rows(payload)
        if rows:
            print_table(rows, ["vmid", "name", "state", "node"])
            return 0
        print_json(payload)
        return 0

    if args.vm_action in {"start", "stop", "reboot"}:
        vmid = int(args.vmid)
        payload = api_request(
            server,
            "POST",
            f"/api/v1/virtualization/vms/{vmid}/power",
            token=token,
            body={"action": args.vm_action},
        )
        print_json(payload)
        return 0 if payload.get("ok", True) else 1
    return 2


def handle_simple_list(args: argparse.Namespace, server: str, token: str) -> int:
    mapping = {
        "pool": "/api/v1/provisioning/catalog",
        "user": "/api/v1/auth/users",
        "node": "/api/v1/status",
        "backup": "/api/v1/backups",
        "session": "/api/v1/sessions",
    }
    endpoint = mapping.get(args.command, "")
    payload = api_request(server, "GET", endpoint, token=token)
    print_json(payload)
    return 0 if payload.get("ok", True) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Beagle control-plane CLI")
    parser.add_argument("--config-path", default=str(DEFAULT_CONFIG_PATH), help="Path to config JSON")
    parser.add_argument("--server", default="", help="Control-plane base URL")
    parser.add_argument("--token", default="", help="Bearer token")
    parser.add_argument("--json", action="store_true", help="JSON output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    vm = subparsers.add_parser("vm", help="VM actions")
    vm_sub = vm.add_subparsers(dest="vm_action", required=True)
    vm_sub.add_parser("list", help="List VMs")
    for action in ("start", "stop", "reboot"):
        vm_action = vm_sub.add_parser(action, help=f"{action.capitalize()} VM")
        vm_action.add_argument("vmid", type=int)

    for name in ("pool", "user", "node", "backup", "session"):
        cmd = subparsers.add_parser(name, help=f"{name.capitalize()} operations")
        cmd_sub = cmd.add_subparsers(dest=f"{name}_action", required=True)
        cmd_sub.add_parser("list", help=f"List {name}s")

    config = subparsers.add_parser("config", help="Manage beaglectl config")
    config_sub = config.add_subparsers(dest="config_action", required=True)
    config_sub.add_parser("init", help="Initialize config")
    set_cmd = config_sub.add_parser("set", help="Set config key")
    set_cmd.add_argument("key")
    set_cmd.add_argument("value")
    config_sub.add_parser("show", help="Show config")

    return parser


def normalize_global_args(argv: list[str]) -> list[str]:
    """Allow global args both before and after subcommands.

    argparse natively expects global args before the subcommand. This helper
    extracts known global args from any position and places them first.
    """

    global_flags = {"--json"}
    global_key_values = {"--config-path", "--server", "--token"}
    front: list[str] = []
    rest: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in global_flags:
            front.append(token)
            index += 1
            continue
        if token in global_key_values:
            front.append(token)
            if index + 1 < len(argv):
                front.append(argv[index + 1])
                index += 2
            else:
                index += 1
            continue
        rest.append(token)
        index += 1
    return front + rest


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(normalize_global_args(raw_argv))
    cfg_path = Path(args.config_path).expanduser()
    cfg = read_config(cfg_path)

    if args.command == "config":
        return handle_config(args, cfg_path, cfg)

    server = resolve_setting(args, cfg, "server", env_name="BEAGLE_SERVER")
    token = resolve_setting(args, cfg, "token", env_name="BEAGLE_TOKEN")
    if not server:
        print("Missing server URL. Use --server or config init/set.", file=sys.stderr)
        return 2

    if args.command == "vm":
        return handle_vm(args, server, token)

    return handle_simple_list(args, server, token)


if __name__ == "__main__":
    raise SystemExit(main())
