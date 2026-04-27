from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "server-installer" / "post-install-check.sh"


def _write_stub(path: Path, name: str, body: str) -> None:
    target = path / name
    target.write_text(body, encoding="utf-8")
    target.chmod(0o755)


def _stub_env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    kvm_device = tmp_path / "kvm"
    kvm_device.write_text("", encoding="utf-8")
    _write_stub(
        bin_dir,
        "systemctl",
        "#!/usr/bin/env bash\nif [[ \"$1\" == \"is-active\" ]]; then exit 0; fi\nexit 0\n",
    )
    _write_stub(
        bin_dir,
        "virsh",
        "#!/usr/bin/env bash\nexit 0\n",
    )
    _write_stub(
        bin_dir,
        "ping",
        "#!/usr/bin/env bash\nexit 0\n",
    )
    _write_stub(
        bin_dir,
        "hostname",
        "#!/usr/bin/env bash\necho test-node.beagle-os.local\n",
    )
    _write_stub(
        bin_dir,
        "curl",
        "#!/usr/bin/env bash\nif [[ \"$*\" == *\"--write-out\"* ]]; then printf '200'; fi\nexit 0\n",
    )
    _write_stub(
        bin_dir,
        "timeout",
        "#!/usr/bin/env bash\nshift\nexec \"$@\"\n",
    )
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["BEAGLE_API_URL"] = "http://127.0.0.1:9088/healthz"
    env["BEAGLE_KVM_DEVICE"] = str(kvm_device)
    return env


def test_post_install_check_passes_syntax_check():
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_post_install_check_happy_path(tmp_path: Path):
    env = _stub_env(tmp_path)
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env, check=False)
    assert result.returncode == 0, result.stderr
    assert "Results:" in result.stdout
