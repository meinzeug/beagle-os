from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
for _path in (str(ROOT_DIR), str(ROOT_DIR / "beagle-host" / "services")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from vm_metrics_sse import VmMetricsSseService


class _FakeVmMetricsSseService(VmMetricsSseService):
    def __init__(self, responses, *, monotonic_values=None):
        self._responses = list(responses)
        self._guest_df_values = [(8 * 1024, 16 * 1024), (8 * 1024, 16 * 1024)]
        monotonic_iter = iter(monotonic_values or [1_000_000_000, 4_000_000_000])
        super().__init__(
            virsh_bin="/usr/bin/virsh",
            sleep_fn=lambda _seconds: None,
            monotonic_ns_fn=lambda: next(monotonic_iter),
        )

    def _run_virsh(self, *args: str) -> str:
        return self._responses.pop(0)

    def _guest_df(self, domain: str) -> tuple[int, int]:
        return self._guest_df_values.pop(0)


def test_resolve_virsh_bin_prefers_known_absolute_path() -> None:
    resolved = VmMetricsSseService._resolve_virsh_bin("/usr/bin/virsh")
    assert resolved == "/usr/bin/virsh"


def test_stream_emits_hello_and_metrics_payload() -> None:
    raw_a = "\n".join([
        "Domain: 'beagle-100'",
        "state.state=1",
        "cpu.time=1000000000",
        "vcpu.current=4",
        "vcpu.maximum=8",
        "balloon.current=1048576",
        "balloon.maximum=2097152",
        "block.count=1",
        "block.0.rd.bytes=1000",
        "block.0.wr.bytes=2000",
        "net.count=1",
        "net.0.rx.bytes=3000",
        "net.0.tx.bytes=4000",
    ])
    raw_b = "\n".join([
        "Domain: 'beagle-100'",
        "state.state=1",
        "cpu.time=2500000000",
        "vcpu.current=4",
        "vcpu.maximum=8",
        "balloon.current=1048576",
        "balloon.maximum=2097152",
        "block.count=1",
        "block.0.rd.bytes=4000",
        "block.0.wr.bytes=8000",
        "net.count=1",
        "net.0.rx.bytes=9000",
        "net.0.tx.bytes=15000",
    ])
    service = _FakeVmMetricsSseService([raw_a, raw_b])
    stream = service.stream(100)

    hello = next(stream).decode("utf-8")
    first_metrics = next(stream).decode("utf-8")
    second_metrics = next(stream).decode("utf-8")

    assert "event: hello" in hello
    assert '"vmid":100' in hello
    assert "event: metrics" in first_metrics
    assert '"status":"running"' in first_metrics
    assert '"guest_agent_available":true' in first_metrics
    assert '"vcpu_current":4' in first_metrics
    assert '"disk_read_bps":0' in first_metrics
    assert "event: metrics" in second_metrics
    assert '"disk_read_bps":1000' in second_metrics
    assert '"disk_write_bps":2000' in second_metrics
    assert '"net_rx_bps":2000' in second_metrics
    assert '"net_tx_bps":3666' in second_metrics


def test_stream_emits_structured_error_when_virsh_fails() -> None:
    class _Broken(VmMetricsSseService):
        def __init__(self):
            super().__init__(virsh_bin="/usr/bin/virsh", sleep_fn=lambda _seconds: None, monotonic_ns_fn=lambda: 1)

        def _run_virsh(self, *args: str) -> str:
            raise RuntimeError("virsh domstats failed: permission denied")

    stream = _Broken().stream(100)
    _hello = next(stream)
    error = next(stream).decode("utf-8")
    assert "event: error" in error
    assert '"code":"metrics_unavailable"' in error
    assert "permission denied" in error
