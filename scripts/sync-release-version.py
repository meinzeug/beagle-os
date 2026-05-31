#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


ROOT_DIR = Path(os.environ.get("BEAGLE_ROOT_DIR", Path(__file__).resolve().parents[1]))
VERSION_RE = re.compile(r"(?P<core>\d+\.\d+\.\d+)(?:-(?P<label>alpha|beta|rc)\.(?P<num>\d+))?")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sync_root_version(version: str) -> None:
    (ROOT_DIR / "VERSION").write_text(f"{version}\n", encoding="utf-8")


def _sync_extension_manifest(*, product_version: str, extension_version: str) -> None:
    path = ROOT_DIR / "extension" / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    if payload.get("version") != extension_version:
        payload["version"] = extension_version
        changed = True
    if payload.get("version_name") != product_version:
        payload["version_name"] = product_version
        changed = True
    if changed:
        _write_json(path, payload)


def _sync_kiosk_package(version: str) -> None:
    path = ROOT_DIR / "beagle-kiosk" / "package.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") == version:
        return
    payload["version"] = version
    _write_json(path, payload)


def _sync_kiosk_package_lock(version: str) -> None:
    path = ROOT_DIR / "beagle-kiosk" / "package-lock.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    if payload.get("version") != version:
        payload["version"] = version
        changed = True
    packages = payload.get("packages")
    if isinstance(packages, dict):
        root_package = packages.get("")
        if isinstance(root_package, dict) and root_package.get("version") != version:
            root_package["version"] = version
            changed = True
    if changed:
        _write_json(path, payload)


def _sync_web_ui_version(version: str) -> None:
    path = ROOT_DIR / "website" / "index.html"
    content = path.read_text(encoding="utf-8")
    updated = re.sub(r'/styles\.css\?v=[^"\']+', f"/styles.css?v={version}", content)
    updated = re.sub(r'/main\.js\?v=[^"\']+', f"/main.js?v={version}", updated)
    if updated != content:
        path.write_text(updated, encoding="utf-8")


def _parse_release_version(raw: str) -> tuple[str, str]:
    normalized = raw.strip().removeprefix("v")
    match = VERSION_RE.fullmatch(normalized)
    if not match:
        raise SystemExit(f"invalid version: {normalized}")
    core = str(match.group("core"))
    return normalized, core


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: sync-release-version.py VERSION")
    product_version, extension_version = _parse_release_version(sys.argv[1])

    _sync_root_version(product_version)
    _sync_extension_manifest(product_version=product_version, extension_version=extension_version)
    _sync_kiosk_package(product_version)
    _sync_kiosk_package_lock(product_version)
    _sync_web_ui_version(product_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
