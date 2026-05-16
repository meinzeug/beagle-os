from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
AUDIO_INIT = (
    ROOT_DIR
    / "thin-client-assistant"
    / "live-build"
    / "config"
    / "includes.chroot"
    / "usr"
    / "local"
    / "bin"
    / "pve-thin-client-audio-init"
)


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _run_select_sink(tmp_path: Path, mock_sinks: str) -> str:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        bindir / "pactl",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"list\" && \"${2:-}\" == \"short\" && \"${3:-}\" == \"sinks\" ]]; then\n"
        "  printf '%b' \"${MOCK_SINKS:-}\"\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"${1:-}\" == \"info\" ]]; then\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
    )

    script_copy = tmp_path / "audio-init-no-main.sh"
    content = AUDIO_INIT.read_text(encoding="utf-8")
    script_copy.write_text(content.replace('\nmain "$@"\n', "\n"), encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["MOCK_SINKS"] = mock_sinks

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{script_copy}"; select_sink',
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stdout.strip()


def test_select_sink_prefers_pci_over_usb_when_both_exist(tmp_path: Path) -> None:
    selected = _run_select_sink(
        tmp_path,
        "\n".join(
            [
                "56 alsa_output.usb-SC420_USB_Microphone_SC420_USB_Microphone_20220325-00.analog-stereo PipeWire s16le 2ch 48000Hz SUSPENDED",
                "59 alsa_output.pci-0000_03_00.6.analog-stereo PipeWire s32le 2ch 48000Hz SUSPENDED",
            ]
        )
        + "\n",
    )
    assert selected == "alsa_output.pci-0000_03_00.6.analog-stereo"


def test_select_sink_falls_back_to_usb_when_only_usb_exists(tmp_path: Path) -> None:
    selected = _run_select_sink(
        tmp_path,
        "56 alsa_output.usb-SC420_USB_Microphone_SC420_USB_Microphone_20220325-00.analog-stereo PipeWire s16le 2ch 48000Hz SUSPENDED\n",
    )
    assert selected == "alsa_output.usb-SC420_USB_Microphone_SC420_USB_Microphone_20220325-00.analog-stereo"
