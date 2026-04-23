from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import beaglectl


class BeagleCtlClusterTests(unittest.TestCase):
    def test_join_token_roundtrip(self) -> None:
        payload = {"cluster_id": "abc", "leader_api_url": "https://leader.example.test/beagle-api", "secret": "xyz"}
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        self.assertEqual(beaglectl.decode_join_token(token), payload)
    
    def test_join_api_url_avoids_duplicate_api_prefix(self) -> None:
        self.assertEqual(
            beaglectl._join_api_url("http://127.0.0.1:9088/api/v1", "/api/v1/cluster/join"),
            "http://127.0.0.1:9088/api/v1/cluster/join",
        )

    def test_join_api_url_keeps_regular_paths(self) -> None:
        self.assertEqual(
            beaglectl._join_api_url("http://127.0.0.1:9088", "/api/v1/cluster/status"),
            "http://127.0.0.1:9088/api/v1/cluster/status",
        )

    def test_infer_rpc_url_from_api_url(self) -> None:
        self.assertEqual(
            beaglectl.infer_rpc_url("http://127.0.0.1:9191/api/v1", "127.0.0.1"),
            "https://127.0.0.1:9192/rpc",
        )