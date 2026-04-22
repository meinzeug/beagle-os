from __future__ import annotations

import os
import sys
from pathlib import Path

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from endpoint_token_store import EndpointTokenStoreService


def test_tokens_dir_ignores_chmod_errors(tmp_path, monkeypatch):
    store = EndpointTokenStoreService(
        data_dir=lambda: tmp_path,
        load_json_file=lambda *_args, **_kwargs: None,
        write_json_file=lambda *_args, **_kwargs: None,
        utcnow=lambda: "2026-01-01T00:00:00+00:00",
    )

    def _raise_chmod_error(_path, _mode):
        raise PermissionError("no chmod permission")

    monkeypatch.setattr(os, "chmod", _raise_chmod_error)
    path = store.tokens_dir()

    assert isinstance(path, Path)
    assert path == tmp_path / "endpoint-tokens"
    assert path.exists()
