#!/usr/bin/env python3
"""Replace __BEAGLE_*__ template variables in a rendered copy of public-site."""
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 5:
        sys.exit(
            f"Usage: {sys.argv[0]} <render-dir> <release-tag>"
            " <github-release-url> <public-update-base-url>"
        )

    root = Path(sys.argv[1])
    if not root.is_dir():
        sys.exit(f"render-dir does not exist or is not a directory: {root}")

    release_tag = sys.argv[2]
    github_release_url = sys.argv[3]
    public_update_base_url = sys.argv[4]

    replacements = {
        "__BEAGLE_RELEASE_TAG__": release_tag,
        "__BEAGLE_GITHUB_RELEASE_URL__": github_release_url,
        "__BEAGLE_PUBLIC_UPDATE_BASE_URL__": public_update_base_url,
    }

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".html", ".css", ".js", ".json", ".txt"}:
            continue
        content = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            content = content.replace(old, new)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
