"""VM Live Metrics SSE service.

Streams real-time CPU, RAM, disk usage and network I/O for a single VM
as Server-Sent Events using virsh domstats and the QEMU guest agent.

Events emitted every ~3 s while the connection is open:
  event: metrics
  data: {"ts": "...", "cpu_pct": 12.4, "ram_used": ..., "ram_total": ...,
         "disk_read_bps": ..., "disk_write_bps": ...,
         "net_rx_bps": ..., "net_tx_bps": ...,
         "disk_used_bytes": ..., "disk_total_bytes": ...,
         "disk_used_pct": 38.2}
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from typing import Any


_POLL_INTERVAL = 3.0   # seconds between samples
_MAX_EVENTS   = 600    # hard cap: ~30 min per connection


class VmMetricsSseService:
    """Collect and yield SSE-formatted metric events for a single VM."""

    def __init__(self, *, virsh_connect: str = "qemu:///system") -> None:
        self._connect = virsh_connect

    # ------------------------------------------------------------------
    # Public generator
    # ------------------------------------------------------------------

    def stream(self, vmid: int) -> Any:
        """Yield raw ``bytes`` chunks suitable for writing directly to the socket.

        Yields a ``hello`` event first, then ``metrics`` events on every poll.
        Raises ``StopIteration`` after MAX_EVENTS or on virsh failures.
        """
        domain = f"beagle-{int(vmid)}"
        yield self._encode("hello", {"ok": True, "vmid": int(vmid), "ts": _ts()})

        prev_cpu_ns: int | None = None
        prev_time_ns: int | None = None
        prev_disk: dict[str, int] = {}
        prev_net: dict[str, int] = {}
        prev_ts_ns: int = 0

        for _ in range(_MAX_EVENTS):
            time.sleep(_POLL_INTERVAL)
            now_ns = time.monotonic_ns()

            try:
                raw = self._run_virsh("domstats", "--raw",
                                      "--cpu-total", "--balloon",
                                      "--block", "--interface",
                                      domain)
            except RuntimeError as exc:
                yield self._encode("error", {"ok": False, "error": str(exc)})
                return

            stats = _parse_domstats(raw)

            # ---- CPU % ----
            cpu_pct = 0.0
            cpu_ns = stats.get("cpu.time")
            if cpu_ns is not None and prev_cpu_ns is not None and prev_ts_ns > 0:
                delta_cpu = max(0, int(cpu_ns) - prev_cpu_ns)
                delta_wall = max(1, now_ns - prev_ts_ns)
                # cpu.time is nanoseconds of CPU consumed across all vCPUs
                vcpus = max(1, int(stats.get("vcpu.maximum", stats.get("vcpu.current", 1)) or 1))
                cpu_pct = round(min(100.0, (delta_cpu / (delta_wall * vcpus)) * 100.0), 1)
            prev_cpu_ns = int(cpu_ns) if cpu_ns is not None else prev_cpu_ns
            prev_ts_ns = now_ns

            # ---- RAM ----
            ram_used: int = 0
            ram_total: int = 0
            # balloon.current is the active allocation in KiB
            balloon_cur = stats.get("balloon.current")
            balloon_max = stats.get("balloon.maximum")
            if balloon_max:
                ram_total = int(balloon_max) * 1024
            if balloon_cur:
                ram_used = int(balloon_cur) * 1024

            # ---- Block I/O ----
            block_count = int(stats.get("block.count", 0) or 0)
            disk_rd_bytes = sum(
                int(stats.get(f"block.{i}.rd.bytes", 0) or 0)
                for i in range(block_count)
            )
            disk_wr_bytes = sum(
                int(stats.get(f"block.{i}.wr.bytes", 0) or 0)
                for i in range(block_count)
            )
            disk_rd_bps = 0
            disk_wr_bps = 0
            if prev_disk and prev_ts_ns > 0:
                delta_s = max(0.001, (now_ns - prev_ts_ns) / 1e9)
                disk_rd_bps = int(max(0, disk_rd_bytes - prev_disk.get("rd", 0)) / delta_s)
                disk_wr_bps = int(max(0, disk_wr_bytes - prev_disk.get("wr", 0)) / delta_s)
            prev_disk = {"rd": disk_rd_bytes, "wr": disk_wr_bytes}

            # ---- Network I/O ----
            net_count = int(stats.get("net.count", 0) or 0)
            net_rx_bytes = sum(
                int(stats.get(f"net.{i}.rx.bytes", 0) or 0)
                for i in range(net_count)
            )
            net_tx_bytes = sum(
                int(stats.get(f"net.{i}.tx.bytes", 0) or 0)
                for i in range(net_count)
            )
            net_rx_bps = 0
            net_tx_bps = 0
            if prev_net and prev_ts_ns > 0:
                delta_s = max(0.001, (now_ns - prev_ts_ns) / 1e9)
                net_rx_bps = int(max(0, net_rx_bytes - prev_net.get("rx", 0)) / delta_s)
                net_tx_bps = int(max(0, net_tx_bytes - prev_net.get("tx", 0)) / delta_s)
            prev_net = {"rx": net_rx_bytes, "tx": net_tx_bytes}

            # ---- Disk usage from guest agent ----
            disk_used_bytes, disk_total_bytes = self._guest_df(domain)
            disk_used_pct = (
                round(disk_used_bytes / disk_total_bytes * 100, 1)
                if disk_total_bytes > 0
                else 0.0
            )

            payload = {
                "ts": _ts(),
                "cpu_pct": cpu_pct,
                "ram_used": ram_used,
                "ram_total": ram_total,
                "ram_pct": round(ram_used / ram_total * 100, 1) if ram_total > 0 else 0.0,
                "disk_read_bps": disk_rd_bps,
                "disk_write_bps": disk_wr_bps,
                "net_rx_bps": net_rx_bps,
                "net_tx_bps": net_tx_bps,
                "disk_used_bytes": disk_used_bytes,
                "disk_total_bytes": disk_total_bytes,
                "disk_used_pct": disk_used_pct,
            }
            yield self._encode("metrics", payload)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_virsh(self, *args: str) -> str:
        cmd = ["virsh", "--connect", self._connect] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(
                f"virsh {' '.join(args[:2])} failed: {result.stderr.strip()}"
            )
        return result.stdout

    def _guest_df(self, domain: str) -> tuple[int, int]:
        """Return (used_bytes, total_bytes) of the root filesystem via QEMU guest agent.

        Returns (0, 0) when the agent is unavailable or the VM is not running.
        """
        try:
            ga_cmd = json.dumps({
                "execute": "guest-exec",
                "arguments": {
                    "path": "/bin/df",
                    "arg": ["-B1", "--output=size,used", "/"],
                    "capture-output": True,
                },
            })
            out = self._run_virsh("qemu-agent-command", "--timeout", "5", domain, ga_cmd)
            pid_data = json.loads(out)
            pid = pid_data["return"]["pid"]

            # Poll for completion (max 3 attempts × 0.5 s)
            result_data: dict[str, Any] = {}
            for _ in range(6):
                time.sleep(0.5)
                status_cmd = json.dumps({
                    "execute": "guest-exec-status",
                    "arguments": {"pid": pid},
                })
                status_raw = self._run_virsh("qemu-agent-command", domain, status_cmd)
                result_data = json.loads(status_raw).get("return", {})
                if result_data.get("exited"):
                    break

            import base64
            out_data = result_data.get("out-data", "")
            if not out_data:
                return (0, 0)
            text = base64.b64decode(out_data).decode("utf-8", errors="replace")
            lines = [l for l in text.splitlines() if l.strip() and not l.strip().lower().startswith("size")]
            if not lines:
                return (0, 0)
            parts = lines[0].split()
            if len(parts) >= 2:
                total = int(parts[0])
                used = int(parts[1])
                return (used, total)
        except Exception:
            pass
        return (0, 0)

    @staticmethod
    def _encode(event_name: str, payload: dict[str, Any]) -> bytes:
        return (
            f"event: {event_name}\n"
            f"data: {json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}\n\n"
        ).encode("utf-8")


# ------------------------------------------------------------------
# Module helpers
# ------------------------------------------------------------------

def _ts() -> str:
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_domstats(raw: str) -> dict[str, Any]:
    """Parse ``virsh domstats --raw`` output into a flat dict."""
    result: dict[str, Any] = {}
    for line in raw.splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Try numeric conversion
        try:
            result[key] = int(value)
            continue
        except ValueError:
            pass
        try:
            result[key] = float(value)
            continue
        except ValueError:
            pass
        result[key] = value
    return result
