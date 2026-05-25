from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL_HTML = ROOT / "tools" / "audio-mic-test.html"
TOOL_SERVER = ROOT / "tools" / "audio-mic-test-server.py"


def test_audio_mic_test_tool_logs_recording_and_playback_events() -> None:
    html = TOOL_HTML.read_text(encoding="utf-8")

    assert "fetch('/log'" in html
    assert "type: 'page-loaded'" in html
    assert "type: 'stream-opened'" in html
    assert "type: 'dataavailable'" in html
    assert "type: 'recording-finalized'" in html
    assert "type: 'play-click'" in html
    assert "type: 'playback-error'" in html
    assert "audio-element-event" in html
    assert "rms" in html
    assert "peak" in html


def test_audio_mic_test_tool_prefers_usb_microphones() -> None:
    html = TOOL_HTML.read_text(encoding="utf-8")

    assert "sc420|usb microphone|usb" in html
    assert "selectedLabel" in html
    assert "deviceSelect.value = preferred.value" in html


def test_audio_mic_test_server_writes_jsonl_log() -> None:
    server = TOOL_SERVER.read_text(encoding="utf-8")

    assert "class AudioMicTestHandler" in server
    assert 'if self.path != "/log"' in server
    assert "MAX_LOG_BODY_BYTES" in server
    assert "sanitize_payload" in server
    assert "log_file.open(\"a\", encoding=\"utf-8\")" in server
    assert "json.dumps(entry" in server