from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable


def _unlink_if_present(path: Path, removed: list[str]) -> None:
    candidate = Path(path)
    if not candidate.exists():
        return
    candidate.unlink(missing_ok=True)
    removed.append(str(candidate))


def _rmtree_if_present(path: Path, removed: list[str]) -> None:
    candidate = Path(path)
    if not candidate.exists():
        return
    shutil.rmtree(candidate, ignore_errors=True)
    if not candidate.exists():
        removed.append(str(candidate))


def cleanup_vm_runtime_artifacts(
    *,
    vmid: int,
    actions_dir: Path,
    endpoints_dir: Path,
    installer_prep_dir: Path,
    load_json_file: Callable[[Path, Any], Any],
    ubuntu_beagle_tokens_dir: Path,
    usb_tunnel_auth_dir: Path,
    vm_secrets_dir: Path,
) -> list[str]:
    target_vmid = int(vmid)
    removed: list[str] = []

    pattern_groups = (
        (Path(endpoints_dir), (f"*-{target_vmid}.json",)),
        (Path(installer_prep_dir), (f"*-{target_vmid}.json", f"*-{target_vmid}.log")),
        (Path(actions_dir), (f"*-{target_vmid}-queue.json", f"*-{target_vmid}-last-result.json")),
        (Path(vm_secrets_dir), (f"*-{target_vmid}.json", f"*-{target_vmid}.json.lock")),
        (Path(usb_tunnel_auth_dir), (f"*-{target_vmid}.pub",)),
    )
    for base_dir, patterns in pattern_groups:
        if not base_dir.exists():
            continue
        for pattern in patterns:
            for path in sorted(base_dir.glob(pattern)):
                _unlink_if_present(path, removed)

    tokens_dir = Path(ubuntu_beagle_tokens_dir)
    if tokens_dir.exists():
        for path in sorted(tokens_dir.glob("*.json")):
            payload = load_json_file(path, None)
            if isinstance(payload, dict) and int(payload.get("vmid", 0) or 0) == target_vmid:
                expected_seed_iso = f"beagle-ubuntu-autoinstall-vm{target_vmid}.iso"
                seed_iso = Path(str(payload.get("seed_iso") or ""))
                if seed_iso.name == expected_seed_iso:
                    _unlink_if_present(seed_iso, removed)
                _unlink_if_present(path, removed)
                # also remove the companion lock file if it exists
                _unlink_if_present(Path(str(path) + ".lock"), removed)
        _rmtree_if_present(tokens_dir / "seed" / str(target_vmid), removed)

    return removed
