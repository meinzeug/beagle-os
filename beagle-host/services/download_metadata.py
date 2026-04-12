from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


class DownloadMetadataService:
    def __init__(
        self,
        *,
        cache_get: Callable[[str, float], Any] | None,
        cache_put: Callable[[str, Any], Any] | None,
        dist_sha256sums_file: Path,
        downloads_status_file: Path,
        load_json_file: Callable[[Path, Any], Any],
        manager_pinned_pubkey: str,
        public_downloads_path: str,
        public_downloads_port: int,
        public_manager_url: str,
        public_server_name: str,
        public_update_base_url: str,
        version: str,
    ) -> None:
        self._cache_get = cache_get
        self._cache_put = cache_put
        self._dist_sha256sums_file = dist_sha256sums_file
        self._downloads_status_file = downloads_status_file
        self._load_json_file = load_json_file
        self._manager_pinned_pubkey = str(manager_pinned_pubkey or "")
        self._public_downloads_path = str(public_downloads_path or "").strip() or "/beagle-downloads"
        self._public_downloads_port = int(public_downloads_port)
        self._public_manager_url = str(public_manager_url or "")
        self._public_server_name = str(public_server_name or "")
        self._public_update_base_url = str(public_update_base_url or "").rstrip("/")
        self._version = str(version or "").strip()

    def _hosted_download_url(self, filename: str) -> str:
        return (
            f"https://{self._public_server_name}:{self._public_downloads_port}"
            f"{self._public_downloads_path}/{filename}"
        )

    def _get_cached(self, key: str, ttl_seconds: float) -> Any:
        if not key or ttl_seconds <= 0 or self._cache_get is None:
            return None
        return self._cache_get(key, ttl_seconds)

    def _put_cached(self, key: str, value: Any) -> Any:
        if not key or self._cache_put is None:
            return value
        return self._cache_put(key, value)

    def public_installer_iso_url(self) -> str:
        return self._hosted_download_url("beagle-os-installer-amd64.iso")

    def public_windows_installer_url(self) -> str:
        return self._hosted_download_url("pve-thin-client-usb-installer-host-latest.ps1")

    def public_update_sha256sums_url(self) -> str:
        return f"{self._public_update_base_url}/SHA256SUMS"

    def public_versioned_payload_url(self, version: str) -> str:
        return f"{self._public_update_base_url}/pve-thin-client-usb-payload-v{version}.tar.gz"

    def public_versioned_bootstrap_url(self, version: str) -> str:
        return f"{self._public_update_base_url}/pve-thin-client-usb-bootstrap-v{version}.tar.gz"

    def public_payload_latest_download_url(self) -> str:
        return self._hosted_download_url("pve-thin-client-usb-payload-latest.tar.gz")

    def public_bootstrap_latest_download_url(self) -> str:
        return self._hosted_download_url("pve-thin-client-usb-bootstrap-latest.tar.gz")

    def public_latest_payload_url(self) -> str:
        downloads_status = self._load_json_file(self._downloads_status_file, {})
        published_version = str(downloads_status.get("version", "")).strip() or self._version
        payload = self.update_payload_metadata(published_version)
        payload_url = str(payload.get("payload_url", "") or "").strip()
        if payload_url:
            return payload_url
        return self.public_versioned_payload_url(published_version)

    def public_latest_bootstrap_url(self) -> str:
        downloads_status = self._load_json_file(self._downloads_status_file, {})
        published_version = str(downloads_status.get("version", "")).strip() or self._version
        bootstrap_url = str(downloads_status.get("bootstrap_url", "") or "").strip()
        if bootstrap_url:
            return bootstrap_url
        return self.public_versioned_bootstrap_url(published_version)

    def url_host_matches(self, left: str, right: str) -> bool:
        left_host = str(urlparse(str(left or "")).hostname or "").strip().lower()
        right_host = str(urlparse(str(right or "")).hostname or "").strip().lower()
        return bool(left_host and right_host and left_host == right_host)

    def checksum_for_dist_filename(self, filename: str) -> str:
        cache_key = f"dist-checksum::{filename}"
        cached = self._get_cached(cache_key, 30)
        if cached is not None:
            return str(cached)
        checksum = ""
        try:
            for raw_line in self._dist_sha256sums_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw_line.strip()
                if not line or "  " not in line:
                    continue
                digest, name = line.split("  ", 1)
                if name.strip() == filename:
                    checksum = digest.strip()
                    break
        except FileNotFoundError:
            checksum = ""
        return str(self._put_cached(cache_key, checksum))

    def update_payload_metadata(self, version: str) -> dict[str, str]:
        downloads_status = self._load_json_file(self._downloads_status_file, {})
        latest_version = str(downloads_status.get("version", "")).strip()
        filename = f"pve-thin-client-usb-payload-v{version}.tar.gz"
        payload_url = self.public_versioned_payload_url(version)
        payload_sha256 = self.checksum_for_dist_filename(filename)
        if not payload_sha256 and version == latest_version:
            payload_sha256 = str(downloads_status.get("payload_sha256", "")).strip()
        payload_pin = self._manager_pinned_pubkey if self.url_host_matches(payload_url, self._public_manager_url) else ""
        return {
            "version": version,
            "filename": filename,
            "payload_url": payload_url,
            "payload_sha256": payload_sha256,
            "sha256sums_url": self.public_update_sha256sums_url(),
            "payload_pinned_pubkey": payload_pin,
        }
