#!/usr/bin/env python3
"""Render __BEAGLE_*__ placeholders in a copied public-site tree."""

from __future__ import annotations

import sys
from pathlib import Path


TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".txt"}


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit(
            f"Usage: {sys.argv[0]} <render-dir> <release-tag> "
            "<github-release-url> <public-update-base-url>"
        )

    root = Path(sys.argv[1])
    if not root.is_dir():
        raise SystemExit(f"render-dir does not exist or is not a directory: {root}")

    replacements = {
        "__BEAGLE_RELEASE_TAG__": sys.argv[2],
        "__BEAGLE_GITHUB_RELEASE_URL__": sys.argv[3],
        "__BEAGLE_PUBLIC_UPDATE_BASE_URL__": sys.argv[4],
    }

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        content = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            content = content.replace(old, new)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
