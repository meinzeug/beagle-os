from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
PAIRING_SH = ROOT_DIR / "thin-client-assistant" / "runtime" / "beagle_stream_client_pairing.sh"
MANAGER_REGISTRATION_SH = ROOT_DIR / "thin-client-assistant" / "runtime" / "beagle_stream_client_manager_registration.sh"


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


def test_ensure_paired_retries_until_manager_token_available(tmp_path: Path) -> None:
    script = f'''
source "{PAIRING_SH}"
beagle_stream_client_bin() {{ printf '/usr/bin/false\n'; }}
beagle_stream_client_connect_host() {{ printf '127.0.0.1\n'; }}
beagle_stream_client_port() {{ printf '47984\n'; }}
beagle_stream_client_target() {{ printf '127.0.0.1:47984\n'; }}
beagle_stream_client_stream_ready() {{ return 1; }}
register_beagle_stream_client_via_manager() {{ return 0; }}
submit_beagle_stream_server_pairing_token() {{ return 1; }}
complete_beagle_stream_client_pairing_handshake() {{ return 0; }}
beagle_stream_client_pair_status_ready() {{ return 0; }}
beagle_stream_client_pairing_timeout() {{ printf '3\n'; }}
beagle_stream_client_pairing_retry_sleep() {{ printf '0\n'; }}
beagle_log_event() {{ return 0; }}
request_calls=0
request_beagle_stream_client_pairing_token_via_manager() {{
  request_calls=$((request_calls + 1))
  if [[ "$request_calls" -lt 2 ]]; then
    return 1
  fi
  export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TOKEN='TOKEN_OK'
  return 0
}}
exchange_beagle_stream_client_pairing_token_via_manager() {{
  [[ "${{1:-}}" == 'TOKEN_OK' ]]
}}
ensure_paired
'''
    result = _run_pairing_ready_script(script, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_manager_registration_keeps_bearer_token_out_of_curl_argv() -> None:
    script = MANAGER_REGISTRATION_SH.read_text(encoding="utf-8")

    assert 'Authorization: Bearer ${manager_token}' not in script
    assert "beagle_stream_client_manager_auth_header_file" in script
    assert '--header "@${auth_header_file}"' in script


def test_ensure_paired_uses_preseeded_token_when_manager_request_fails(tmp_path: Path) -> None:
    script = f'''
source "{PAIRING_SH}"
beagle_stream_client_bin() {{ printf '/usr/bin/false\n'; }}
beagle_stream_client_connect_host() {{ printf '127.0.0.1\n'; }}
beagle_stream_client_port() {{ printf '47984\n'; }}
beagle_stream_client_target() {{ printf '127.0.0.1:47984\n'; }}
beagle_stream_client_stream_ready() {{ return 1; }}
register_beagle_stream_client_via_manager() {{ return 1; }}
request_beagle_stream_client_pairing_token_via_manager() {{ return 1; }}
submit_beagle_stream_server_pairing_token() {{ return 1; }}
complete_beagle_stream_client_pairing_handshake() {{ return 0; }}
beagle_stream_client_pair_status_ready() {{ return 0; }}
beagle_stream_client_pairing_timeout() {{ printf '1\n'; }}
beagle_stream_client_pairing_retry_sleep() {{ printf '0\n'; }}
beagle_log_event() {{ return 0; }}
exchange_beagle_stream_client_pairing_token_via_manager() {{
  [[ "${{1:-}}" == 'PRESET_TOKEN' ]]
}}
export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TOKEN='PRESET_TOKEN'
ensure_paired
'''
    result = _run_pairing_ready_script(script, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_pair_status_ignores_authenticated_apps_helper(tmp_path: Path) -> None:
    script = f'''
source "{PAIRING_SH}"
beagle_stream_client_connect_host() {{ printf '192.168.123.114\n'; }}
beagle_stream_client_port() {{ printf '50000\n'; }}
beagle_stream_server_apps_json() {{
  printf '{{"apps":[{{"name":"Desktop"}}]}}\n'
}}
selected_beagle_stream_server_api_url() {{
  printf 'https://192.168.123.114:50001\n'
}}
curl() {{
  printf '<root><PairStatus>0</PairStatus></root>\n'
  return 0
}}
if [[ "$(beagle_stream_client_pair_status)" != "0" ]]; then
  echo "expected unpaired"
  exit 1
fi
'''
    result = _run_pairing_ready_script(script, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_pairing_handshake_runs_client_cli_with_x11_environment(tmp_path: Path) -> None:
    fake_bin = tmp_path / "beagle-stream"
    capture_file = tmp_path / "pair-env.txt"
    fake_bin.write_text(
        f'''#!/usr/bin/env bash
printf '%s\n' "$DISPLAY|$XAUTHORITY|$QT_QPA_PLATFORM|$XDG_SESSION_TYPE|$*" >"{capture_file}"
exit 0
''',
        encoding="utf-8",
    )
    fake_bin.chmod(0o755)

    script = f'''
source "{PAIRING_SH}"
beagle_stream_client_bin() {{ printf '%s\n' "{fake_bin}"; }}
beagle_stream_client_connect_host() {{ printf '192.168.123.114\n'; }}
beagle_stream_client_port() {{ printf '50000\n'; }}
beagle_stream_client_target() {{ printf '%s:%s\n' "${{1:-}}" "${{2:-}}"; }}
beagle_stream_client_prepare_cli_environment() {{
  export DISPLAY=':0'
  export XAUTHORITY='/home/thinclient/.Xauthority'
  export QT_QPA_PLATFORM='xcb'
  export XDG_SESSION_TYPE='x11'
}}
export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_COMPAT_PIN='SECRET_COMPAT_PIN'
export BEAGLE_STREAM_CLIENT_PAIR_LOG='{tmp_path / "pair.log"}'
complete_beagle_stream_client_pairing_handshake
'''
    result = _run_pairing_ready_script(script, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert capture_file.read_text(encoding="utf-8").strip() == (
        ":0|/home/thinclient/.Xauthority|xcb|x11|pair 192.168.123.114:50000 --pin SECRET_COMPAT_PIN"
    )


def test_pairing_handshake_accepts_pair_status_after_cli_timeout(tmp_path: Path) -> None:
    fake_bin = tmp_path / "beagle-stream"
    fake_bin.write_text(
        '''#!/usr/bin/env bash
exit 124
''',
        encoding="utf-8",
    )
    fake_bin.chmod(0o755)

    script = f'''
source "{PAIRING_SH}"
beagle_stream_client_bin() {{ printf '%s\n' "{fake_bin}"; }}
beagle_stream_client_connect_host() {{ printf '192.168.123.114\n'; }}
beagle_stream_client_port() {{ printf '50000\n'; }}
beagle_stream_client_target() {{ printf '%s:%s\n' "${{1:-}}" "${{2:-}}"; }}
beagle_stream_client_pair_status() {{ printf '1\n'; }}
export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_COMPAT_PIN='SECRET_COMPAT_PIN'
export BEAGLE_STREAM_CLIENT_PAIR_LOG='{tmp_path / "pair.log"}'
complete_beagle_stream_client_pairing_handshake
'''
    result = _run_pairing_ready_script(script, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PairStatus=1" in (tmp_path / "pair.log").read_text(encoding="utf-8")


def test_pair_exchange_exports_internal_compat_secret(tmp_path: Path) -> None:
    response_file = tmp_path / "pair-exchange.json"
    response_file.write_text(
        '{"ok":true,"pairing":{"mode":"pin-compat","pin":"SECRET_COMPAT_PIN"}}',
        encoding="utf-8",
    )

    script = f'''
export BEAGLE_STREAM_CLIENT_CONFIG_STATE_SH=/dev/null
source "{MANAGER_REGISTRATION_SH}"
mapfile -t parsed < <(parse_beagle_stream_client_pair_exchange_response "{response_file}")
if [[ "${{parsed[0]:-}}" != "pin-compat" || "${{parsed[1]:-}}" != "SECRET_COMPAT_PIN" ]]; then
  printf 'bad parse: %s/%s\n' "${{parsed[0]:-}}" "${{parsed[1]:-}}"
  exit 1
fi
export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_COMPAT_PIN="${{parsed[1]}}"
[[ "$PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_COMPAT_PIN" == "SECRET_COMPAT_PIN" ]]
'''
    result = _run_pairing_ready_script(script, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
