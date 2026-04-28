from __future__ import annotations

import json
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def parse_csv_series(value: Any) -> list[float]:
    if not isinstance(value, str):
        return []
    values: list[float] = []
    for item in value.split(","):
        item = str(item).strip()
        if not item:
            continue
        try:
            values.append(float(item))
        except ValueError:
            continue
    return values


def fetch_energy_feed_payload(feed_url: str, timeout_seconds: float) -> dict[str, list[float]]:
    parsed = urlparse(feed_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("feed_url must use http or https")

    request = Request(feed_url, method="GET", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 200) or 200)
            if status >= 400:
                raise RuntimeError(f"feed returned HTTP {status}")
            raw = response.read().decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(str(exc)) from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("feed did not return valid JSON") from exc

    candidate = payload
    if isinstance(payload, dict) and isinstance(payload.get("hourly_profile"), dict):
        candidate = payload.get("hourly_profile")
    if not isinstance(candidate, dict):
        raise ValueError("feed JSON must contain hourly profile object")

    if "hours" in candidate and isinstance(candidate.get("hours"), list):
        co2_values = [0.0] * 24
        price_values = [0.0] * 24
        for item in candidate.get("hours", []):
            if not isinstance(item, dict):
                continue
            try:
                hour = int(item.get("hour"))
            except (TypeError, ValueError):
                continue
            if hour < 0 or hour > 23:
                continue
            try:
                co2_values[hour] = float(item.get("co2_grams_per_kwh", item.get("co2", co2_values[hour])))
            except (TypeError, ValueError):
                pass
            try:
                price_values[hour] = float(
                    item.get(
                        "electricity_price_per_kwh",
                        item.get("price", price_values[hour]),
                    )
                )
            except (TypeError, ValueError):
                pass
        candidate = {
            "co2_grams_per_kwh": co2_values,
            "electricity_price_per_kwh": price_values,
        }

    co2_raw = candidate.get("co2_grams_per_kwh")
    price_raw = candidate.get("electricity_price_per_kwh")
    if not isinstance(co2_raw, list) or not isinstance(price_raw, list):
        raise ValueError("feed profile must provide co2_grams_per_kwh and electricity_price_per_kwh arrays")
    if len(co2_raw) < 24 or len(price_raw) < 24:
        raise ValueError("feed profile arrays must contain at least 24 values")

    co2 = [round(float(co2_raw[idx]), 2) for idx in range(24)]
    price = [round(float(price_raw[idx]), 4) for idx in range(24)]
    return {
        "co2_grams_per_kwh": co2,
        "electricity_price_per_kwh": price,
    }


def collect_import_payload(
    payload: dict[str, Any],
    *,
    retries_default: int,
    timeout_default: float,
    retry_backoff_default: float,
    node_id: str,
    fetch_payload_fn: Callable[[str, float], dict[str, list[float]]] = fetch_energy_feed_payload,
    sleep_fn: Callable[[float], None] = time.sleep,
    alert_fn: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    profile_payload = payload.get("hourly_profile") if isinstance(payload.get("hourly_profile"), dict) else {}
    imported: dict[str, Any] = {}

    feed_url = str(payload.get("feed_url") or "").strip()
    retries = max(1, int(payload.get("retries") or retries_default))
    timeout_seconds = max(0.5, float(payload.get("timeout_seconds") or timeout_default))
    retry_backoff_seconds = max(
        0.0,
        float(payload.get("retry_backoff_seconds") or retry_backoff_default),
    )

    if feed_url:
        last_error = ""
        for attempt in range(1, retries + 1):
            try:
                profile_payload = fetch_payload_fn(feed_url, timeout_seconds)
                imported["co2_grams_per_kwh"] = profile_payload.get("co2_grams_per_kwh")
                imported["electricity_price_per_kwh"] = profile_payload.get("electricity_price_per_kwh")
                break
            except Exception as exc:
                last_error = str(exc)
                if attempt >= retries:
                    message = (
                        f"Energy feed import failed after {retries} attempts "
                        f"for {feed_url}: {last_error}"
                    )
                    if alert_fn:
                        alert_fn(message)
                    raise RuntimeError(
                        f"energy feed import failed after {retries} attempts: {last_error}"
                    ) from exc
                if retry_backoff_seconds > 0:
                    sleep_fn(retry_backoff_seconds)

    if "co2_csv" in payload:
        imported["co2_grams_per_kwh"] = parse_csv_series(payload.get("co2_csv"))
    if "price_csv" in payload:
        imported["electricity_price_per_kwh"] = parse_csv_series(payload.get("price_csv"))
    if "co2_grams_per_kwh" in profile_payload:
        imported["co2_grams_per_kwh"] = profile_payload.get("co2_grams_per_kwh")
    if "electricity_price_per_kwh" in profile_payload:
        imported["electricity_price_per_kwh"] = profile_payload.get("electricity_price_per_kwh")
    return imported
