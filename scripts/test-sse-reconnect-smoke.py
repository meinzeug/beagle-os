#!/usr/bin/env python3
"""Smoke: SSE /events/stream endpoint is reachable and delivers events.

Validates that after host/VM reboot, the WebUI can reconnect to the
live SSE stream. This smoke:
1. Opens an SSE connection to /events/stream
2. Reads until a 'hello' or 'tick' event arrives (or timeout)
3. Confirms the stream is properly formatted SSE

Run on srv1:
    source /etc/beagle/beagle-manager.env
    python3 /opt/beagle/scripts/test-sse-reconnect-smoke.py \
        --base http://127.0.0.1:9088 --token "$BEAGLE_MANAGER_API_TOKEN"

Expected output: SSE_RECONNECT_SMOKE=PASS
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SSE /events/stream endpoint")
    parser.add_argument("--base", default=os.environ.get("BEAGLE_API_BASE", "http://127.0.0.1:9088"))
    parser.add_argument("--token", default=os.environ.get("BEAGLE_MANAGER_API_TOKEN", ""))
    parser.add_argument("--timeout", type=float, default=30.0, help="Seconds to wait for SSE event")
    args = parser.parse_args()

    token = str(args.token or "").strip()
    if not token:
        print("SSE_RECONNECT_SMOKE=FAIL")
        print("error=missing token")
        return 2

    base = str(args.base).rstrip("/")
    url = f"{base}/api/v1/events/stream?access_token={token}"

    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "text/event-stream" not in ct:
                print("SSE_RECONNECT_SMOKE=FAIL")
                print(f"error=wrong Content-Type: {ct!r} (expected text/event-stream)")
                return 1

            deadline = time.monotonic() + args.timeout
            received_events: list[str] = []
            buf = b""

            while time.monotonic() < deadline:
                chunk = resp.read(512)
                if not chunk:
                    break
                buf += chunk

                lines = buf.split(b"\n")
                buf = lines[-1]  # incomplete last line stays in buffer

                for line in lines[:-1]:
                    text = line.decode("utf-8", errors="replace").strip()
                    if text.startswith("event:"):
                        event_name = text[len("event:"):].strip()
                        received_events.append(event_name)

                if any(e in ("hello", "tick") for e in received_events):
                    break

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print("SSE_RECONNECT_SMOKE=FAIL")
        print(f"error=HTTP {exc.code}: {raw[:200]}")
        return 1
    except TimeoutError:
        print("SSE_RECONNECT_SMOKE=FAIL")
        print(f"error=timeout after {args.timeout}s waiting for SSE event")
        return 1
    except Exception as exc:
        print("SSE_RECONNECT_SMOKE=FAIL")
        print(f"error={exc}")
        return 1

    if not any(e in ("hello", "tick") for e in received_events):
        print("SSE_RECONNECT_SMOKE=FAIL")
        print(f"error=no 'hello' or 'tick' event received (got: {received_events})")
        return 1

    print("SSE_RECONNECT_SMOKE=PASS")
    events_str = ", ".join(received_events[:5])
    print(f"events_received=[{events_str}] stream_visible=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
