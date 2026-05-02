from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "ensure-vm-stream-ready.sh"


def test_ensure_vm_stream_ready_validates_desktop_streaming_guards() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert "beagle_stream_server_guest_desktop_smoke_json" in content
    assert "DISPLAY=:0 XAUTHORITY=\"$xauth\" xset q" in content
    assert "pgrep -x light-locker" in content
    assert "pgrep -x xfce4-power-manager" in content
    assert '"desktop_smoke"' in content
    assert "Desktop-Streaming-Guards melden Warnungen" in content
    assert '"desktop_smoke_ok"' in content
