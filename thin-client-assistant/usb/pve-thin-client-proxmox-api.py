#!/usr/bin/env python3
import argparse
import json
import ssl
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPSHandler

from proxmox_preset import Endpoint, build_preset, normalize_endpoint, shell_line


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class ProxmoxApi:
    def __init__(self, endpoint: Endpoint, username: str, password: str, verify_tls: bool):
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.ticket = ""

        context = ssl.create_default_context()
        if not verify_tls:
            context = ssl._create_unverified_context()  # noqa: SLF001
        self.opener = build_opener(HTTPSHandler(context=context))

    def url(self, path: str, query: dict[str, Any] | None = None) -> str:
        base = f"{self.endpoint.scheme}://{self.endpoint.host}:{self.endpoint.port}/api2/json{path}"
        if query:
            return f"{base}?{urlencode(query)}"
        return base

    def request(self, path: str, *, query: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> Any:
        payload = None
        headers = {"Accept": "application/json"}
        if data is not None:
            payload = urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if self.ticket:
            headers["Cookie"] = f"PVEAuthCookie={self.ticket}"
        request = Request(self.url(path, query=query), data=payload, headers=headers)
        try:
            with self.opener.open(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise SystemExit(f"Proxmox API request failed: {exc.code} {exc.reason}: {detail}") from exc
        except URLError as exc:
            raise SystemExit(f"Unable to reach Proxmox API: {exc.reason}") from exc

        try:
            payload_json = json.loads(body)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON response from Proxmox API: {exc}") from exc

        if "data" not in payload_json:
            raise SystemExit("Unexpected Proxmox API response: missing data field")
        return payload_json["data"]

    def login(self) -> None:
        data = self.request(
            "/access/ticket",
            data={"username": self.username, "password": self.password},
        )
        ticket = data.get("ticket", "")
        if not ticket:
            raise SystemExit("Proxmox login succeeded but no ticket was returned")
        self.ticket = ticket

    def list_nodes(self) -> list[str]:
        data = self.request("/nodes")
        nodes: list[str] = []
        for item in data:
            node = str(item.get("node", "")).strip()
            if node and node not in nodes:
                nodes.append(node)
        return nodes

    def list_vms_on_node(self, node: str) -> list[dict[str, Any]]:
        data = self.request(f"/nodes/{node}/qemu")
        vms = []
        for item in data:
            if item.get("vmid") is None:
                continue
            vms.append(
                {
                    "vmid": int(item["vmid"]),
                    "node": node,
                    "name": item.get("name") or f"vm-{item['vmid']}",
                    "status": item.get("status", "unknown"),
                    "tags": item.get("tags", ""),
                    "template": bool(item.get("template")),
                }
            )
        return vms

    def list_vms(self) -> list[dict[str, Any]]:
        data = self.request("/cluster/resources", query={"type": "vm"})
        vms = []
        for item in data:
            if item.get("type") != "qemu":
                continue
            if item.get("vmid") is None or not item.get("node"):
                continue
            vms.append(
                {
                    "vmid": int(item["vmid"]),
                    "node": item["node"],
                    "name": item.get("name") or f"vm-{item['vmid']}",
                    "status": item.get("status", "unknown"),
                    "tags": item.get("tags", ""),
                    "template": bool(item.get("template")),
                }
            )
        if not vms:
            seen: set[tuple[str, int]] = set()
            for node in self.list_nodes():
                for vm in self.list_vms_on_node(node):
                    key = (vm["node"], vm["vmid"])
                    if key in seen:
                        continue
                    seen.add(key)
                    vms.append(vm)
        vms.sort(key=lambda entry: (entry["name"].lower(), entry["vmid"]))
        return vms

    def resolve_vm(self, vmid: int, node: str | None = None) -> dict[str, Any]:
        for vm in self.list_vms():
            if vm["vmid"] == vmid and (not node or vm["node"] == node):
                return vm
        raise SystemExit(f"VM {vmid} is not visible for the supplied user")

    def fetch_vm_config(self, node: str, vmid: int) -> dict[str, Any]:
        return self.request(f"/nodes/{node}/qemu/{vmid}/config")


def command_list_vms(args: argparse.Namespace) -> int:
    endpoint = normalize_endpoint(args.host, args.scheme, args.port)
    api = ProxmoxApi(endpoint, args.username, args.password, parse_bool(args.verify_tls))
    api.login()
    payload = {
        "endpoint": {"scheme": endpoint.scheme, "host": endpoint.host, "port": endpoint.port},
        "username": args.username,
        "vms": api.list_vms(),
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def command_build_preset_env(args: argparse.Namespace) -> int:
    endpoint = normalize_endpoint(args.host, args.scheme, args.port)
    verify_tls = parse_bool(args.verify_tls)
    api = ProxmoxApi(endpoint, args.username, args.password, verify_tls)
    api.login()
    vm = api.resolve_vm(args.vmid, args.node)
    config = api.fetch_vm_config(vm["node"], vm["vmid"])
    preset, _ = build_preset(vm, config, endpoint, args.username, verify_tls)
    sys.stdout.write("".join(shell_line(key, value) for key, value in preset.items()))
    return 0


def command_build_preset_json(args: argparse.Namespace) -> int:
    endpoint = normalize_endpoint(args.host, args.scheme, args.port)
    verify_tls = parse_bool(args.verify_tls)
    api = ProxmoxApi(endpoint, args.username, args.password, verify_tls)
    api.login()
    vm = api.resolve_vm(args.vmid, args.node)
    config = api.fetch_vm_config(vm["node"], vm["vmid"])
    preset, available_modes = build_preset(vm, config, endpoint, args.username, verify_tls)
    payload = {"vm": vm, "preset": preset, "available_modes": available_modes}
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Proxmox API helper for the thin-client installer")
    parser.add_argument("--host", required=True)
    parser.add_argument("--scheme", default="https")
    parser.add_argument("--port", type=int, default=8006)
    parser.add_argument("--verify-tls", default="1")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-vms-json")

    preset_env = subparsers.add_parser("build-preset-env")
    preset_env.add_argument("--vmid", type=int, required=True)
    preset_env.add_argument("--node")

    preset_json = subparsers.add_parser("build-preset-json")
    preset_json.add_argument("--vmid", type=int, required=True)
    preset_json.add_argument("--node")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list-vms-json":
        return command_list_vms(args)
    if args.command == "build-preset-env":
        return command_build_preset_env(args)
    if args.command == "build-preset-json":
        return command_build_preset_json(args)
    parser.error(f"unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
