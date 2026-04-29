"""GPU Inventory Service + GPU Metrics Service.

GoEnterprise Plan 10, Schritte 1 + 3 + 4
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from core.persistence.json_state_store import JsonStateStore
from core.repository.gpu_repository import GpuRepository

GpuClass = Literal["gaming", "workstation", "compute", "unknown"]
GpuMode = Literal["passthrough", "timeslice", "vgpu", "unassigned"]


@dataclass
class GpuDevice:
    gpu_id: str             # "node_id:pci_addr"
    node_id: str
    pci_addr: str
    model: str
    vram_gb: float
    gpu_class: GpuClass = "unknown"
    supports_vgpu: bool = False
    supports_timeslice: bool = True
    current_mode: GpuMode = "unassigned"
    current_assignment: str = ""    # vmid or "" if free
    driver_version: str = ""


def gpu_device_from_dict(d: dict[str, Any]) -> GpuDevice:
    return GpuDevice(**{k: v for k, v in d.items() if k in GpuDevice.__dataclass_fields__})


def _classify_gpu(model: str) -> GpuClass:
    m = model.lower()
    if any(x in m for x in ("a100", "h100", "h200", "a30 ", " a30,", "a40 ", " a40,", "v100", "t4 ", " t4,")):
        return "compute"
    if any(x in m for x in ("quadro", "rtx pro", "rtx a", "a2000", "a4000", "a5000", "a6000")):
        return "workstation"
    if any(x in m for x in ("rtx", "gtx", "rx ", "radeon", "arc")):
        return "gaming"
    return "unknown"


class GpuInventoryService:
    """
    Tracks GPU hardware across all cluster nodes.

    Scans via nvidia-smi (NVIDIA) and lspci (others).
    State is persisted for offline queries.

    GoEnterprise Plan 10, Schritt 1
    """

    STATE_FILE = Path("/var/lib/beagle/beagle-manager/gpu-inventory.json")

    def __init__(
        self,
        state_file: Path | None = None,
        run_cmd: Callable[[list[str]], str] | None = None,
        gpu_repository: GpuRepository | None = None,
    ) -> None:
        self._state_file = state_file or self.STATE_FILE
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._run_cmd = run_cmd or self._default_run
        self._gpu_repo: GpuRepository | None = gpu_repository
        self._state = self._load()

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def scan_node(self, node_id: str) -> list[GpuDevice]:
        """Scan a node for GPUs using nvidia-smi."""
        raw = self._run_nvidia_smi()
        devices = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("name"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                continue
            model, vram_str, driver, pci = parts[0], parts[1], parts[2], parts[3]
            try:
                vram_gb = float(vram_str.replace("MiB", "").strip()) / 1024.0
            except ValueError:
                vram_gb = 0.0
            gpu_id = f"{node_id}:{pci}"
            dev = GpuDevice(
                gpu_id=gpu_id,
                node_id=node_id,
                pci_addr=pci,
                model=model,
                vram_gb=round(vram_gb, 1),
                gpu_class=_classify_gpu(model),
                driver_version=driver,
                supports_vgpu="A" in model or "vGPU" in model,
            )
            devices.append(dev)
            self._state[gpu_id] = asdict(dev)

        self._save()
        return devices

    def register_gpu(self, device: GpuDevice) -> GpuDevice:
        """Manually register a GPU (for testing or non-NVIDIA cards)."""
        if device.gpu_class == "unknown":
            from dataclasses import replace
            device = replace(device, gpu_class=_classify_gpu(device.model))
        self._state[device.gpu_id] = asdict(device)
        self._save()
        return device

    def get_gpu(self, gpu_id: str) -> GpuDevice | None:
        d = self._state.get(gpu_id)
        return gpu_device_from_dict(d) if d else None

    def list_gpus(
        self,
        *,
        node_id: str | None = None,
        gpu_class: GpuClass | None = None,
        free_only: bool = False,
    ) -> list[GpuDevice]:
        devices = [gpu_device_from_dict(d) for d in self._state.values()]
        if node_id:
            devices = [d for d in devices if d.node_id == node_id]
        if gpu_class:
            devices = [d for d in devices if d.gpu_class == gpu_class]
        if free_only:
            devices = [d for d in devices if not d.current_assignment]
        return devices

    def assign_gpu(self, gpu_id: str, vm_id: str, mode: GpuMode) -> GpuDevice:
        if gpu_id not in self._state:
            raise KeyError(f"GPU {gpu_id!r} not found")
        self._state[gpu_id]["current_assignment"] = vm_id
        self._state[gpu_id]["current_mode"] = mode
        self._save()
        return gpu_device_from_dict(self._state[gpu_id])

    def release_gpu(self, gpu_id: str) -> GpuDevice:
        if gpu_id not in self._state:
            raise KeyError(f"GPU {gpu_id!r} not found")
        self._state[gpu_id]["current_assignment"] = ""
        self._state[gpu_id]["current_mode"] = "unassigned"
        self._save()
        return gpu_device_from_dict(self._state[gpu_id])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_nvidia_smi(self) -> str:
        try:
            return self._run_cmd([
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version,pci.bus_id",
                "--format=csv,noheader",
            ])
        except Exception:
            return ""

    def _load(self) -> dict[str, Any]:
        data = JsonStateStore(self._state_file, default_factory=dict).load()
        if self._gpu_repo is not None:
            # Overlay from repository (authoritative when repo is set)
            for g in self._gpu_repo.list():
                gid = g.get("gpu_id")
                if gid:
                    data.setdefault(gid, g)
        return data

    def _save(self) -> None:
        if self._gpu_repo is not None:
            for gpu_dict in self._state.values():
                if isinstance(gpu_dict, dict) and gpu_dict.get("gpu_id"):
                    try:
                        self._gpu_repo.save(gpu_dict)
                    except Exception:  # pragma: no cover
                        pass
        JsonStateStore(self._state_file, default_factory=dict).save(self._state)

    @staticmethod
    def _default_run(cmd: list[str]) -> str:
        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout


# ===========================================================================
# GPU Metrics Service (Plan 10, Schritt 3)
# ===========================================================================

@dataclass
class GpuMetricSample:
    timestamp: str
    gpu_id: str
    vm_id: str
    util_pct: float         # GPU core utilization
    vram_used_mb: float
    temp_c: float
    encoder_util_pct: float  # NVENC utilization
    power_w: float


class GpuMetricsService:
    """Tracks per-VM GPU utilization for stream routing decisions."""

    STATE_DIR = Path("/var/lib/beagle/gpu-metrics")
    ENCODER_OVERLOAD_THRESHOLD = 90.0

    def __init__(
        self,
        state_dir: Path | None = None,
        utcnow: Callable[[], str] | None = None,
    ) -> None:
        self._dir = state_dir or self.STATE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._utcnow = utcnow or self._default_utcnow

    def record(self, sample: GpuMetricSample) -> None:
        day = sample.timestamp[:10]
        shard = self._dir / f"{sample.gpu_id}_{day}.jsonl"
        with shard.open("a") as f:
            f.write(json.dumps(asdict(sample)) + "\n")

    def get_recent(self, gpu_id: str, *, minutes: int = 10) -> list[GpuMetricSample]:
        import datetime
        now = self._current_datetime()
        cutoff = (now - datetime.timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S")
        today = now.strftime("%Y-%m-%d")
        shard = self._dir / f"{gpu_id}_{today}.jsonl"
        if not shard.exists():
            return []
        samples = []
        for line in shard.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                if d.get("timestamp", "") >= cutoff:
                    samples.append(GpuMetricSample(**d))
        return samples

    def check_encoder_overload(self, gpu_id: str) -> bool:
        """Return True if NVENC is overloaded (avg >90% in last 10 min)."""
        samples = self.get_recent(gpu_id)
        if not samples:
            return False
        avg = sum(s.encoder_util_pct for s in samples) / len(samples)
        return avg > self.ENCODER_OVERLOAD_THRESHOLD

    def avg_utilization(self, gpu_id: str, *, minutes: int = 10) -> float:
        samples = self.get_recent(gpu_id, minutes=minutes)
        if not samples:
            return 0.0
        return sum(s.util_pct for s in samples) / len(samples)

    @staticmethod
    def _default_utcnow() -> str:
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _current_datetime(self):
        import datetime
        raw = str(self._utcnow() or "").strip()
        if raw:
            try:
                parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=datetime.timezone.utc)
                return parsed.astimezone(datetime.timezone.utc)
            except ValueError:
                pass
        return datetime.datetime.now(datetime.timezone.utc)


# ===========================================================================
# GPU Pool Rebalancer (Plan 10, Schritt 4)
# ===========================================================================

@dataclass
class GpuRebalanceRecommendation:
    vm_id: str
    from_gpu_id: str
    to_gpu_id: str
    reason: str


class GpuPoolRebalancer:
    """Identifies GPU hotspots and recommends VM migrations."""

    OVERLOAD_THRESHOLD = 90.0
    UNDERLOAD_THRESHOLD = 20.0

    def __init__(
        self,
        inventory: GpuInventoryService,
        metrics: GpuMetricsService,
        migrate_vm: Callable[[str, str], None] | None = None,
    ) -> None:
        self._inv = inventory
        self._metrics = metrics
        self._migrate_vm = migrate_vm

    def rebalance(
        self,
        node_id: str | None = None,
        auto_execute: bool = False,
    ) -> list[GpuRebalanceRecommendation]:
        gpus = self._inv.list_gpus(node_id=node_id) if node_id else self._inv.list_gpus()
        overloaded = [g for g in gpus if self._metrics.avg_utilization(g.gpu_id) > self.OVERLOAD_THRESHOLD and g.current_assignment]
        underloaded = [g for g in gpus if self._metrics.avg_utilization(g.gpu_id) < self.UNDERLOAD_THRESHOLD and not g.current_assignment]

        recs = []
        for src in overloaded:
            for dst in underloaded:
                if src.gpu_class == dst.gpu_class:
                    rec = GpuRebalanceRecommendation(
                        vm_id=src.current_assignment,
                        from_gpu_id=src.gpu_id,
                        to_gpu_id=dst.gpu_id,
                        reason=f"source={self._metrics.avg_utilization(src.gpu_id):.0f}% > {self.OVERLOAD_THRESHOLD}%",
                    )
                    recs.append(rec)
                    if auto_execute and self._migrate_vm:
                        self._migrate_vm(src.current_assignment, dst.gpu_id)
                    break
        return recs
