#!/usr/bin/env python3
"""Expose the local thin-client microphone as a low-latency PCM TCP stream."""

from __future__ import annotations

import argparse
import os
import pwd
import socket
import subprocess
import sys
import time
from pathlib import Path


SAMPLE_WIDTH_BYTES = 2


def log(message: str) -> None:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"{stamp} beagle-audio-input-bridge: {message}", file=sys.stderr, flush=True)


def runtime_env(user: str) -> dict[str, str]:
    env = os.environ.copy()
    try:
        info = pwd.getpwnam(user)
        uid = info.pw_uid
        home = info.pw_dir
    except KeyError:
        uid = int(env.get("PVE_THIN_CLIENT_AUDIO_USER_UID", "1000"))
        home = env.get("HOME", "/home/thinclient")
    runtime_dir = env.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}"
    env.update(
        {
            "HOME": home,
            "XDG_RUNTIME_DIR": runtime_dir,
            "PULSE_SERVER": env.get("PULSE_SERVER", f"unix:{runtime_dir}/pulse/native"),
        }
    )
    return env


def run_as_user_prefix(user: str) -> list[str]:
    if os.geteuid() == 0:
        return ["runuser", "-u", user, "--"]
    return []


def pactl_lines(user: str, *args: str) -> list[str]:
    cmd = [*run_as_user_prefix(user), "env", *[f"{key}={value}" for key, value in runtime_env(user).items() if key in {"HOME", "XDG_RUNTIME_DIR", "PULSE_SERVER"}], "pactl", *args]
    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=5)
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
    return output.splitlines()


def select_source(user: str, configured: str) -> str:
    if configured:
        return configured
    candidates: list[str] = []
    for line in pactl_lines(user, "list", "short", "sources"):
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[1]
        lower = name.lower()
        if lower.endswith(".monitor"):
            continue
        candidates.append(name)
    for name in candidates:
        lower = name.lower()
        if "usb" in lower or "sc420" in lower:
            return name
    for name in candidates:
        if "input" in name.lower():
            return name
    return candidates[0] if candidates else "@DEFAULT_SOURCE@"


def start_parec(user: str, source: str, rate: int, channels: int, latency_msec: int) -> subprocess.Popen[bytes]:
    env = runtime_env(user)
    cmd = [
        *run_as_user_prefix(user),
        "env",
        f"HOME={env['HOME']}",
        f"XDG_RUNTIME_DIR={env['XDG_RUNTIME_DIR']}",
        f"PULSE_SERVER={env['PULSE_SERVER']}",
        "parec",
        f"--device={source}",
        "--format=s16le",
        f"--rate={rate}",
        f"--channels={channels}",
        f"--latency-msec={latency_msec}",
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def frame_bytes(rate: int, channels: int, frame_msec: int, configured_chunk_bytes: int) -> int:
    if configured_chunk_bytes > 0:
        return configured_chunk_bytes
    bytes_per_sec = rate * channels * SAMPLE_WIDTH_BYTES
    return max(2, (bytes_per_sec * frame_msec) // 1000)


def read_exact(stream: object, size: int) -> bytes:
    if size <= 0:
        return b""
    out = bytearray()
    while len(out) < size:
        chunk = stream.read(size - len(out))
        if not chunk:
            break
        out.extend(chunk)
    return bytes(out)


def serve_client(conn: socket.socket, args: argparse.Namespace) -> None:
    source = select_source(args.user, args.source)
    chunk_bytes = frame_bytes(args.rate, args.channels, args.frame_msec, args.chunk_bytes)
    log(
        f"client connected source={source} rate={args.rate} channels={args.channels} "
        f"frame_msec={args.frame_msec} chunk_bytes={chunk_bytes}"
    )
    process = start_parec(args.user, source, args.rate, args.channels, args.latency_msec)
    assert process.stdout is not None
    try:
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    try:
        while True:
            chunk = read_exact(process.stdout, chunk_bytes)
            if not chunk:
                break
            if len(chunk) != chunk_bytes:
                log(f"short frame from parec: expected={chunk_bytes} got={len(chunk)}")
                break
            conn.sendall(chunk)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        err = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        if err.strip():
            log("parec stderr=" + err.strip().replace("\n", " | ")[:800])
        log("client disconnected")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Beagle thin-client audio input bridge")
    parser.add_argument("--host", default=os.environ.get("PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_LISTEN", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_LOCAL_PORT", "43200")))
    parser.add_argument("--user", default=os.environ.get("PVE_THIN_CLIENT_AUDIO_USER", "thinclient"))
    parser.add_argument("--source", default=os.environ.get("PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_SOURCE", ""))
    parser.add_argument("--rate", type=int, default=int(os.environ.get("PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_RATE", "48000")))
    parser.add_argument("--channels", type=int, default=int(os.environ.get("PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_CHANNELS", "1")))
    parser.add_argument("--frame-msec", type=int, default=int(os.environ.get("PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_FRAME_MSEC", "20")))
    parser.add_argument("--latency-msec", type=int, default=int(os.environ.get("PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_LATENCY_MSEC", "20")))
    parser.add_argument("--chunk-bytes", type=int, default=int(os.environ.get("PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_CHUNK_BYTES", "0")))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    Path("/var/log/beagle").mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        server.listen(1)
        log(f"listening on {args.host}:{args.port}")
        while True:
            conn, addr = server.accept()
            with conn:
                log(f"accepted {addr[0]}:{addr[1]}")
                serve_client(conn, args)


if __name__ == "__main__":
    raise SystemExit(main())