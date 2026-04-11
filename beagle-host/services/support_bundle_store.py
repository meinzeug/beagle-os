from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class SupportBundleStoreService:
    def __init__(
        self,
        *,
        load_json_file: Callable[[Path, Any], Any],
        safe_slug: Callable[[str, str], str],
        support_bundles_dir: Callable[[], Path],
    ) -> None:
        self._load_json_file = load_json_file
        self._safe_slug = safe_slug
        self._support_bundles_dir = support_bundles_dir

    def metadata_path(self, bundle_id: str) -> Path:
        return self._support_bundles_dir() / f"{self._safe_slug(bundle_id, 'bundle')}.json"

    def archive_path(self, bundle_id: str, filename: str) -> Path:
        suffixes = Path(filename or "support-bundle.tar.gz").suffixes
        extension = "".join(suffixes) if suffixes else ".bin"
        return self._support_bundles_dir() / f"{self._safe_slug(bundle_id, 'bundle')}{extension}"

    def find_metadata(self, bundle_id: str) -> dict[str, Any] | None:
        payload = self._load_json_file(self.metadata_path(bundle_id), None)
        return payload if isinstance(payload, dict) else None

    def list_metadata(
        self,
        *,
        node: str | None = None,
        vmid: int | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self._support_bundles_dir().glob("*.json")):
            payload = self._load_json_file(path, None)
            if not isinstance(payload, dict):
                continue
            if node is not None and str(payload.get("node", "")).strip() != str(node).strip():
                continue
            if vmid is not None and int(payload.get("vmid", -1)) != int(vmid):
                continue
            items.append(payload)
        items.sort(key=lambda item: str(item.get("uploaded_at", "")), reverse=True)
        return items
