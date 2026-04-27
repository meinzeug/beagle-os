"""Shared request-/origin-related helpers for host-side HTTP handlers."""

from __future__ import annotations

from typing import Callable
from urllib.parse import urlparse


class RequestSupportService:
    def __init__(
        self,
        *,
        cache_get: Callable[[str, float], object | None],
        cache_put: Callable[[str, tuple[str, ...]], tuple[str, ...]],
        cors_allowed_origins_raw: str,
        current_public_stream_host: Callable[[], str],
        listify: Callable[[object], list[str]],
        public_downloads_port: int,
        public_manager_url: str,
        public_server_name: str,
        public_stream_host_raw: str,
        web_ui_url: str,
    ) -> None:
        self._cache_get = cache_get
        self._cache_put = cache_put
        self._cors_allowed_origins_raw = str(cors_allowed_origins_raw or "")
        self._current_public_stream_host = current_public_stream_host
        self._listify = listify
        self._public_downloads_port = int(public_downloads_port)
        self._public_manager_url = str(public_manager_url or "")
        self._public_server_name = str(public_server_name or "")
        self._public_stream_host_raw = str(public_stream_host_raw or "")
        self._web_ui_url = str(web_ui_url or "")

    @staticmethod
    def extract_bearer_token(header_value: str) -> str:
        header = str(header_value or "").strip()
        if header.startswith("Bearer "):
            return header[7:].strip()
        return ""

    @staticmethod
    def normalized_origin(value: str) -> str:
        parsed = urlparse(str(value or "").strip())
        if not parsed.scheme or not parsed.hostname:
            return ""
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https"}:
            return ""
        host = str(parsed.hostname or "").strip().lower()
        if not host:
            return ""
        default_port = 443 if scheme == "https" else 80
        port = parsed.port
        origin = f"{scheme}://{host}"
        if port and port != default_port:
            origin += f":{port}"
        return origin

    def cors_allowed_origins(self) -> set[str]:
        cache_key = "cors-allowed-origins"
        cached = self._cache_get(cache_key, 60)
        if cached is not None:
            return set(cached)

        public_downloads_origin = f"https://{self._public_server_name}"
        if self._public_downloads_port != 443:
            public_downloads_origin = f"{public_downloads_origin}:{self._public_downloads_port}"

        candidates: set[str] = {
            self._web_ui_url,
            self._public_manager_url,
            f"https://{self._public_server_name}",
            public_downloads_origin,
        }
        hostnames = {
            self._public_server_name.strip(),
            self._public_stream_host_raw.strip(),
            str(self._current_public_stream_host() or "").strip(),
            str(urlparse(self._web_ui_url).hostname or "").strip(),
            str(urlparse(self._public_manager_url).hostname or "").strip(),
        }
        for origin in self._listify(self._cors_allowed_origins_raw):
            candidates.add(origin)

        normalized = tuple(sorted(origin for origin in (self.normalized_origin(item) for item in candidates) if origin))
        self._cache_put(cache_key, normalized)
        return set(normalized)
