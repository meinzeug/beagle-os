"""Shared VM metadata and hostname helpers for the host control plane.

This service owns the pure helper semantics for parsing description metadata
and deriving a stable guest hostname from a VM name. Keeping these helpers out
of the HTTP entrypoint makes the behavior explicit for extracted host services.
"""

from __future__ import annotations

import re


class MetadataSupportService:
    def parse_description_meta(self, description: str) -> dict[str, str]:
        meta: dict[str, str] = {}
        text = str(description or "").replace("\\r\\n", "\n").replace("\\n", "\n")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key and key not in meta:
                meta[key] = value
        return meta

    def safe_hostname(self, name: str, vmid: int) -> str:
        cleaned = re.sub(r"[^a-z0-9-]+", "-", str(name or "").strip().lower()).strip("-")
        if not cleaned:
            cleaned = f"beagle-{int(vmid)}"
        return cleaned[:63].strip("-") or f"beagle-{int(vmid)}"
