from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
PAIRING_SH = ROOT_DIR / "thin-client-assistant" / "runtime" / "beagle_stream_client_pairing.sh"


def _run_pairing_ready_script(script_body: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["TMP_LIST_LOG"] = str(tmp_path / "list.log")
    return subprocess.run(
        ["bash", "-lc", script_body],
        cwd=str(ROOT_DIR),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_stream_ready_rejects_certificate_mismatch_from_list_log(tmp_path: Path) -> None:
    script = f'''
source "{PAIRING_SH}"
beagle_stream_client_pair_status_ready() {{ return 1; }}
beagle_stream_client_list() {{
  echo "Server certificate mismatch" >"$TMP_LIST_LOG"
  return 0
}}
export BEAGLE_STREAM_CLIENT_LIST_LOG="$TMP_LIST_LOG"
if beagle_stream_client_stream_ready; then
  echo "ready"
  exit 1
fi
exit 0
'''
    result = _run_pairing_ready_script(script, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_stream_ready_accepts_valid_pair_status_without_list_call(tmp_path: Path) -> None:
    script = f'''
source "{PAIRING_SH}"
beagle_stream_client_pair_status() {{ printf '1\\n'; return 0; }}
beagle_stream_client_list() {{
  echo "list should not be called" >&2
  return 99
}}
export BEAGLE_STREAM_CLIENT_LIST_LOG="$TMP_LIST_LOG"
beagle_stream_client_stream_ready
'''
    result = _run_pairing_ready_script(script, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_stream_ready_rejects_explicit_unpaired_status_without_list_fallback(tmp_path: Path) -> None:
    script = f'''
source "{PAIRING_SH}"
beagle_stream_client_pair_status() {{ printf '0\\n'; return 0; }}
beagle_stream_client_list() {{
  echo "list fallback must not run" >&2
  return 0
}}
export BEAGLE_STREAM_CLIENT_LIST_LOG="$TMP_LIST_LOG"
if beagle_stream_client_stream_ready; then
  echo "ready"
  exit 1
fi
exit 0
'''
    result = _run_pairing_ready_script(script, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
