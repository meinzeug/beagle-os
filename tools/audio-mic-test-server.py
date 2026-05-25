#!/usr/bin/env python3
"""Serve the Beagle microphone test page and persist browser-side diagnostics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


MAX_LOG_BODY_BYTES = 64 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sanitize_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
      return {"message": str(payload)[:2000]}

    safe: dict[str, Any] = {}
    for key, value in payload.items():
        key_text = str(key)[:80]
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key_text] = value if not isinstance(value, str) else value[:4000]
        elif isinstance(value, list):
            safe[key_text] = value[:40]
        elif isinstance(value, dict):
            safe[key_text] = {str(k)[:80]: str(v)[:800] for k, v in list(value.items())[:40]}
        else:
            safe[key_text] = str(value)[:1000]
    return safe


class AudioMicTestHandler(SimpleHTTPRequestHandler):
    server_version = "BeagleAudioMicTest/1.0"

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path != "/log":
            self.send_error(HTTPStatus.NOT_FOUND, "not found")
            return

        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length > MAX_LOG_BODY_BYTES:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "log payload too large")
            return

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8", errors="replace") or "{}")
        except json.JSONDecodeError as exc:
            payload = {"message": "invalid-json", "error": str(exc), "raw": raw_body[:1000].decode("utf-8", errors="replace")}

        entry = {
            "time": utc_now(),
            "remote": self.client_address[0],
            "payload": sanitize_payload(payload),
        }
        log_file: Path = self.server.log_file  # type: ignore[attr-defined]
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

        response = b'{"ok":true}\n'
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve Beagle Audio Mic Test with logfile diagnostics")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--log-file", type=Path, default=Path.home() / ".local/state/beagle/audio-mic-test.log")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    handler = lambda *handler_args, **handler_kwargs: AudioMicTestHandler(  # noqa: E731
        *handler_args,
        directory=str(args.root),
        **handler_kwargs,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    server.log_file = args.log_file  # type: ignore[attr-defined]
    print(f"serving http://{args.host}:{args.port}/audio-mic-test.html")
    print(f"logging to {args.log_file}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())