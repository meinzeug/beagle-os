from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_tc_mic_bridge_has_jitter_buffer_controls() -> None:
    script = (ROOT / "scripts" / "lib" / "beagle-tc-mic-bridge").read_text(encoding="utf-8")

    assert 'BEAGLE_TC_MIC_FRAME_MSEC:-20' in script
    assert 'BEAGLE_TC_MIC_PREBUFFER_MSEC:-60' in script
    assert 'BEAGLE_TC_MIC_MAX_BUFFER_MSEC:-200' in script
    assert 'BEAGLE_TC_MIC_STATS_INTERVAL_SEC:-5' in script
    assert 'frame_buffer: deque[bytes] = deque()' in script
    assert 'if len(frame_buffer) >= max_buffer_frames:' in script
    assert 'stats["frames_dropped"] += 1' in script
    assert 'stats["underruns"] += 1' in script
    assert 'stats["silence_inserted"] += 1' in script
    assert 'emit_stats("stats", len(frame_buffer))' in script


def test_tc_mic_bridge_writes_silence_on_underrun() -> None:
    script = (ROOT / "scripts" / "lib" / "beagle-tc-mic-bridge").read_text(encoding="utf-8")

    assert 'silence = b"\\0" * frame_bytes' in script
    assert 'if started and frame_buffer:' in script
    assert 'frame = silence' in script
    assert 'time.sleep(0.002)' in script


def test_tc_mic_bridge_reloads_pipe_source_module() -> None:
    script = (ROOT / "scripts" / "lib" / "beagle-tc-mic-bridge").read_text(encoding="utf-8")

    assert 'unload_pipe_source()' in script
    assert 'pactl list short modules' in script
    assert 'pactl unload-module "$module_id"' in script
    assert 'unload_pipe_source' in script


def test_tc_mic_bridge_service_has_cpu_safety_limit() -> None:
    service = (ROOT / "scripts" / "lib" / "beagle-tc-mic-bridge.service").read_text(encoding="utf-8")

    assert "Nice=5" in service
    assert "CPUQuota=25%" in service
