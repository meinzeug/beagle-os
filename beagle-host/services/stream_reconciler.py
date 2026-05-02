"""Stream Reconciler Service.

Translates the logic of scripts/reconcile-public-streams.sh into a Python
service that can be invoked from the control plane or run as a standalone
systemd service (beagle-stream-reconciler.service).

Responsibilities:
  - Read active VMs and their stream metadata from the control plane
  - Maintain the public-stream port mapping (public-streams.json)
  - Generate and apply nftables DNAT rules for external Beagle Stream Client access
  - Emit an audit event after each reconcile cycle
"""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_STREAMS_FILE = Path("/var/lib/beagle/beagle-manager/public-streams.json")
_DEFAULT_NFT_STATE_FILE = Path("/etc/beagle/beagle-streams.nft")
_DEFAULT_NFT_TABLE = "beagle_stream"
_DEFAULT_BASE_PORT = 50000
_DEFAULT_PORT_STEP = 32
_DEFAULT_PORT_COUNT = 256


class StreamReconcilerService:
    """Reconcile public Beagle Stream Client stream NAT rules for active VMs."""

    def __init__(
        self,
        *,
        list_vms_fn: Any,
        get_vm_config_fn: Any,
        first_guest_ipv4_fn: Any,
        parse_description_meta_fn: Any,
        public_host: str = "",
        lan_iface: str = "virbr10",
        base_port: int = _DEFAULT_BASE_PORT,
        port_step: int = _DEFAULT_PORT_STEP,
        port_count: int = _DEFAULT_PORT_COUNT,
        streams_file: Path = _DEFAULT_STREAMS_FILE,
        nft_state_file: Path = _DEFAULT_NFT_STATE_FILE,
        nft_table: str = _DEFAULT_NFT_TABLE,
        dry_run: bool = False,
    ) -> None:
        self._list_vms = list_vms_fn
        self._get_vm_config = get_vm_config_fn
        self._first_guest_ipv4 = first_guest_ipv4_fn
        self._parse_meta = parse_description_meta_fn
        self._public_host = public_host or self._resolve_hostname()
        self._lan_iface = lan_iface
        self._base_port = base_port
        self._port_step = port_step
        self._port_count = port_count
        self._streams_file = streams_file
        self._nft_state_file = nft_state_file
        self._nft_table = nft_table
        self._dry_run = dry_run

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reconcile(self) -> list[dict[str, Any]]:
        """Run one reconcile cycle. Returns list of active stream items."""
        streams = self._load_streams()
        used: set[int] = {int(v) for v in streams.values()}
        upper_bound = self._base_port + (self._port_step * self._port_count)

        try:
            vms = self._list_vms() or []
        except Exception as exc:
            logger.warning("StreamReconciler: list_vms failed: %s", exc)
            return []

        items: list[dict[str, Any]] = []
        active_keys: set[str] = set()

        for vm in sorted(vms, key=lambda v: int(v.get("vmid", 0))):
            if vm.get("type") != "qemu" or vm.get("vmid") is None or not vm.get("node"):
                continue
            vmid = int(vm["vmid"])
            node = str(vm["node"])
            try:
                config = self._get_vm_config(node, vmid) or {}
            except Exception:
                config = {}
            meta = self._parse_meta(config.get("description", ""))
            try:
                guest_ip = self._first_guest_ipv4(vmid)
            except Exception:
                guest_ip = None

            if not self._should_publish(meta, guest_ip):
                continue
            if not guest_ip:
                continue

            key = f"{node}:{vmid}"
            active_keys.add(key)

            explicit_port_raw = str(meta.get("beagle-public-beagle-stream-client-port", "")).strip()
            if explicit_port_raw.isdigit():
                mapped_base: int | None = int(explicit_port_raw)
                streams[key] = mapped_base
                used.add(mapped_base)
            else:
                mapped_base = streams.get(key)  # type: ignore[assignment]
                if mapped_base is None:
                    for candidate in range(self._base_port, upper_bound, self._port_step):
                        if candidate not in used:
                            mapped_base = candidate
                            streams[key] = candidate
                            used.add(candidate)
                            break

            if mapped_base is None:
                continue

            items.append(
                {
                    "vmid": vmid,
                    "node": node,
                    "name": str(config.get("name") or vm.get("name") or f"vm-{vmid}"),
                    "guest_ip": guest_ip,
                    "public_host": str(meta.get("beagle-public-stream-host", "")).strip()
                    or self._public_host,
                    "base_port": int(mapped_base),
                    "beagle_stream_server_api_url": str(
                        meta.get("beagle-public-beagle-stream-server-api-url", "")
                    ).strip()
                    or f"https://{self._public_host}:{int(mapped_base) + 1}",
                }
            )

        # Prune stale keys
        for stale in [k for k in streams if k not in active_keys]:
            streams.pop(stale, None)

        self._save_streams(streams)

        if not self._dry_run:
            try:
                self._apply_nft_rules(items)
            except Exception as exc:
                logger.error("StreamReconciler: nft apply failed: %s", exc)

        logger.info("StreamReconciler: reconciled %d stream(s)", len(items))
        return items

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _should_publish(meta: dict[str, str], guest_ip: str | None) -> bool:
        if str(meta.get("beagle-public-stream", "1")).strip().lower() in {"0", "false", "no", "off"}:
            return False
        if meta.get("beagle-public-beagle-stream-client-port"):
            return True
        if meta.get("beagle-stream-server-user") or meta.get("beagle-stream-server-password") or meta.get("beagle-stream-server-api-url"):
            return True
        if meta.get("beagle-stream-client-host") or meta.get("beagle-stream-server-host") or meta.get("beagle-stream-server-ip"):
            return True
        if guest_ip and str(meta.get("beagle-role", "")).strip().lower() == "desktop":
            return True
        return False

    def _load_streams(self) -> dict[str, int]:
        try:
            payload = json.loads(self._streams_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        result: dict[str, int] = {}
        for k, v in payload.items():
            try:
                result[str(k)] = int(v)
            except (TypeError, ValueError):
                pass
        return result

    def _save_streams(self, streams: dict[str, int]) -> None:
        self._streams_file.parent.mkdir(parents=True, exist_ok=True)
        self._streams_file.write_text(
            json.dumps(streams, indent=2) + "\n", encoding="utf-8"
        )

    def _apply_nft_rules(self, items: list[dict[str, Any]]) -> None:
        public_ips = self._resolve_public_ips(self._public_host)
        nft_text = self._build_nft_rules(items, public_ips)

        self._nft_state_file.parent.mkdir(parents=True, exist_ok=True)
        self._nft_state_file.write_text(nft_text, encoding="utf-8")

        subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], capture_output=True)
        subprocess.run(
            ["nft", "delete", "table", "inet", self._nft_table],
            capture_output=True,
        )
        result = subprocess.run(
            ["nft", "-f", str(self._nft_state_file)], capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"nft -f failed: {result.stderr.strip()}")

    def _build_nft_rules(
        self, items: list[dict[str, Any]], public_ips: list[str]
    ) -> str:
        lines: list[str] = [
            f"table inet {self._nft_table} {{",
            "  chain prerouting {",
            "    type nat hook prerouting priority dstnat; policy accept;",
        ]
        if public_ips and items:
            daddr = (
                "{ " + ", ".join(public_ips) + " }"
                if len(public_ips) > 1
                else public_ips[0]
            )
            for item in items:
                guest_ip = item["guest_ip"]
                base = int(item["base_port"])
                tcp_ports = {base - 5, base, base + 1, base + 21}
                udp_ports = {base + p for p in range(9, 16)}
                for port in sorted(tcp_ports):
                    lines.append(
                        f"    ip daddr {daddr} tcp dport {port} dnat to {guest_ip}:{port}"
                    )
                for port in sorted(udp_ports):
                    lines.append(
                        f"    ip daddr {daddr} udp dport {port} dnat to {guest_ip}:{port}"
                    )
        lines.append("  }")
        lines.append("  chain forward {")
        lines.append("    type filter hook forward priority filter; policy accept;")
        for item in items:
            guest_ip = item["guest_ip"]
            base = int(item["base_port"])
            tcp_set = f"{{ {base - 5}, {base}, {base + 1}, {base + 21} }}"
            udp_set = ", ".join(str(base + p) for p in range(9, 16))
            udp_set = f"{{ {udp_set} }}"
            lines.append(
                f'    oifname "{self._lan_iface}" ip daddr {guest_ip} tcp dport {tcp_set} accept'
            )
            lines.append(
                f'    oifname "{self._lan_iface}" ip daddr {guest_ip} udp dport {udp_set} accept'
            )
        lines.append("  }")
        lines.append("}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _resolve_public_ips(host: str) -> list[str]:
        if not host:
            return []
        try:
            seen: set[str] = set()
            ips: list[str] = []
            for item in socket.getaddrinfo(
                host, None, family=socket.AF_INET, type=socket.SOCK_STREAM
            ):
                ip = item[4][0]
                if ip not in seen:
                    seen.add(ip)
                    ips.append(ip)
            return ips
        except socket.gaierror:
            return [host]

    @staticmethod
    def _resolve_hostname() -> str:
        try:
            return socket.getfqdn()
        except Exception:
            return socket.gethostname()


# ------------------------------------------------------------------
# Standalone daemon entry-point (used by systemd unit)
# ------------------------------------------------------------------

def _run_daemon(interval: int = 60) -> None:
    """Run reconcile in a loop. Imports provider helpers directly."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s stream-reconciler %(message)s",
    )
    env_file = Path(os.environ.get("BEAGLE_MANAGER_ENV_FILE", "/etc/beagle/beagle-manager.env"))
    env: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")

    # Resolve provider module path
    import sys

    provider_lib = Path(
        env.get(
            "BEAGLE_PROVIDER_MODULE_PATH",
            str(Path(__file__).parent.parent.parent / "scripts" / "lib" / "beagle_provider.py"),
        )
    ).resolve()
    sys.path.insert(0, str(provider_lib.parent))
    from beagle_provider import (  # type: ignore[import]
        first_guest_ipv4,
        list_vms,
        parse_description_meta,
        vm_config,
    )

    svc = StreamReconcilerService(
        list_vms_fn=list_vms,
        get_vm_config_fn=vm_config,
        first_guest_ipv4_fn=first_guest_ipv4,
        parse_description_meta_fn=parse_description_meta,
        public_host=env.get("BEAGLE_PUBLIC_STREAM_HOST", ""),
        lan_iface=env.get("BEAGLE_PUBLIC_STREAM_LAN_IF", "virbr10"),
        base_port=int(env.get("BEAGLE_PUBLIC_STREAM_BASE_PORT", str(_DEFAULT_BASE_PORT))),
        port_step=int(env.get("BEAGLE_PUBLIC_STREAM_PORT_STEP", str(_DEFAULT_PORT_STEP))),
        port_count=int(env.get("BEAGLE_PUBLIC_STREAM_PORT_COUNT", str(_DEFAULT_PORT_COUNT))),
        streams_file=Path(
            env.get("BEAGLE_PUBLIC_STREAMS_FILE", str(_DEFAULT_STREAMS_FILE))
        ),
        nft_state_file=Path(
            env.get("BEAGLE_PUBLIC_STREAM_NFT_STATE_FILE", str(_DEFAULT_NFT_STATE_FILE))
        ),
        nft_table=env.get("BEAGLE_PUBLIC_STREAM_NFT_TABLE", _DEFAULT_NFT_TABLE),
    )

    logger.info("StreamReconciler daemon started, interval=%ds", interval)
    while True:
        try:
            items = svc.reconcile()
            for item in items:
                logger.info(
                    "  VM %s -> %s:%s (%s)",
                    item["vmid"],
                    item["public_host"],
                    item["base_port"],
                    item["guest_ip"],
                )
        except Exception as exc:
            logger.error("Reconcile cycle error: %s", exc)
        time.sleep(interval)


if __name__ == "__main__":
    _run_daemon()
