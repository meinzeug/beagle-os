#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: sync-web-ui-version.py INDEX_HTML VERSION")
    path = Path(sys.argv[1])
    version = sys.argv[2].strip()
    content = path.read_text(encoding="utf-8")
    content = re.sub(r'/styles\.css\?v=[^"\']+', f'/styles.css?v={version}', content)
    content = re.sub(r'/main\.js\?v=[^"\']+', f'/main.js?v={version}', content)
    path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
