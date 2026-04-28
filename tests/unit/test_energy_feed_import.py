from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

import energy_feed_import


class _FakeHttpResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.status = status
        self._buffer = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self) -> bytes:
        return self._buffer.read()

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeAlertService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def fire_alert(self, **kwargs):
        self.calls.append(kwargs)


def test_fetch_energy_feed_payload_supports_hourly_profile_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = {
        "hourly_profile": {
            "co2_grams_per_kwh": [310.0] * 24,
            "electricity_price_per_kwh": [0.22] * 24,
        }
    }

    monkeypatch.setattr(energy_feed_import, "urlopen", lambda _request, timeout=5: _FakeHttpResponse(profile))

    imported = energy_feed_import.fetch_energy_feed_payload("https://feed.example/profile.json", 1.0)
    assert imported["co2_grams_per_kwh"][0] == pytest.approx(310.0)
    assert imported["electricity_price_per_kwh"][0] == pytest.approx(0.22)


def test_import_energy_hourly_profile_retries_external_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    def _fetch(_url: str, _timeout: float) -> dict[str, list[float]]:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary upstream error")
        return {
            "co2_grams_per_kwh": [299.0] * 24,
            "electricity_price_per_kwh": [0.19] * 24,
        }

    alerts: list[str] = []

    imported = energy_feed_import.collect_import_payload(
        {
            "feed_url": "https://feed.example/hourly.json",
            "retries": 3,
            "retry_backoff_seconds": 0,
            "timeout_seconds": 1,
        },
        retries_default=3,
        timeout_default=1,
        retry_backoff_default=0,
        node_id="srv1",
        fetch_payload_fn=_fetch,
        sleep_fn=lambda _seconds: None,
        alert_fn=lambda message: alerts.append(message),
    )

    assert attempts["count"] == 3
    assert not alerts
    assert imported["co2_grams_per_kwh"][0] == pytest.approx(299.0)
    assert imported["electricity_price_per_kwh"][0] == pytest.approx(0.19)


def test_import_energy_hourly_profile_alerts_on_retry_exhaustion(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_alerts = _FakeAlertService()

    with pytest.raises(RuntimeError):
        energy_feed_import.collect_import_payload(
            {
                "feed_url": "https://feed.example/hourly.json",
                "retries": 2,
                "retry_backoff_seconds": 0,
                "timeout_seconds": 1,
            },
            retries_default=2,
            timeout_default=1,
            retry_backoff_default=0,
            node_id="srv1",
            fetch_payload_fn=lambda _url, _timeout: (_ for _ in ()).throw(RuntimeError("upstream timeout")),
            sleep_fn=lambda _seconds: None,
            alert_fn=lambda message: fake_alerts.fire_alert(
                rule_id="energy_feed_import_failed",
                device_id="srv1",
                metric="energy_feed_import",
                current_value=2.0,
                message=message,
            ),
        )

    assert len(fake_alerts.calls) == 1
    assert fake_alerts.calls[0]["rule_id"] == "energy_feed_import_failed"
    assert fake_alerts.calls[0]["metric"] == "energy_feed_import"
