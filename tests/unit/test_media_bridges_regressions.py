"""Checks for the independent thin-client audio and camera bridges."""
from pathlib import Path
import os
import select
import shutil
import socket
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_audio_bridge_starts_as_unprivileged_user_without_log_directory():
    bridge = ROOT / 'thin-client-assistant/runtime/beagle_audio_input_bridge.py'
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen(
        ['python3', str(bridge), '--host', '127.0.0.1', '--port', str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    try:
        assert process.stderr is not None
        ready, _, _ = select.select([process.stderr], [], [], 5)
        assert ready, 'audio bridge did not start'
        assert 'listening on 127.0.0.1' in process.stderr.readline()
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_camera_mjpeg_stream_can_be_decoded_without_saving_images():
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('ffmpeg not installed')
    source = subprocess.run(
        [ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
         '-i', 'testsrc=size=160x120:rate=5', '-frames:v', '3',
         '-threads', '1', '-c:v', 'mjpeg', '-f', 'mjpeg', 'pipe:1'],
        capture_output=True, timeout=15, check=True,
    )
    assert source.stdout
    decoded = subprocess.run(
        [ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'mjpeg',
         '-i', 'pipe:0', '-frames:v', '3', '-f', 'null', '-'],
        input=source.stdout, capture_output=True, timeout=15,
    )
    assert decoded.returncode == 0, decoded.stderr.decode(errors='replace')


def test_camera_sender_and_guest_receivers_agree_on_wire_format():
    sender = (ROOT / 'thin-client-assistant/runtime/beagle-camera-stream').read_text()
    receiver = (ROOT / 'scripts/lib/beagle-camera-receive').read_text()
    provisioner = (ROOT / 'scripts/configure-beagle-stream-server-guest.sh').read_text()
    assert '-f mjpeg' in sender and 'tcp://127.0.0.1:${STREAM_PORT}' in sender
    assert '-f mjpeg' in receiver and 'v4l2loopback-ctl add' in receiver
    assert '-f mjpeg' in provisioner and 'v4l2loopback-ctl add' in provisioner


def test_extender_builder_rejects_unverified_source(tmp_path):
    archive = tmp_path / 'wrong.tar.gz'
    archive.write_bytes(b'untrusted content')
    result = subprocess.run(
        ['bash', str(ROOT / 'scripts/build-beagle-usbip-extender.sh'), str(tmp_path / 'extender')],
        env={**os.environ, 'BEAGLE_EXTENDER_ARCHIVE': str(archive)},
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0
    assert 'checksum' in result.stderr
    assert not (tmp_path / 'extender').exists()
