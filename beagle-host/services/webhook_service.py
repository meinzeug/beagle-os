from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib import error as urlerror
from urllib import request as urlrequest

from core.persistence.json_state_store import JsonStateStore


_ALLOWED_EVENT_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._:-")


class WebhookService:
    def __init__(
        self,
        *,
        data_dir: Path,
        utcnow: Callable[[], str],
    ) -> None:
        self._data_dir = data_dir
        self._utcnow = utcnow
        self._store_path = self._data_dir / "webhooks.json"
        self._store = JsonStateStore(self._store_path, default_factory=lambda: {"webhooks": []}, mode=0o600)

    def _load(self) -> dict[str, Any]:
        try:
            data = self._store.load()
            if isinstance(data, dict):
                return data
        except OSError:
            pass
        return {"webhooks": []}

    def _save(self, data: dict[str, Any]) -> None:
        self._store.save(data)

    @staticmethod
    def _normalize_event_name(value: Any) -> str:
        name = str(value or "").strip().lower()
        if not name:
            return ""
        if any(ch not in _ALLOWED_EVENT_CHARS for ch in name):
            return ""
        return name

    @staticmethod
    def _normalize_events(raw: Any) -> list[str]:
        values: list[str]
        if isinstance(raw, list):
            values = [str(item) for item in raw]
        elif raw is None:
            values = []
        else:
            values = [str(raw)]
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            event_name = WebhookService._normalize_event_name(value)
            if not event_name:
                continue
            if event_name in seen:
                continue
            seen.add(event_name)
            normalized.append(event_name)
        return normalized

    @staticmethod
    def _normalize_url(raw: Any) -> str:
        url = str(raw or "").strip()
        if url.startswith("https://") or url.startswith("http://"):
            return url
        return ""

    def _sanitize_webhook(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(item.get("id") or ""),
            "url": str(item.get("url") or ""),
            "events": list(item.get("events") or []),
            "enabled": bool(item.get("enabled", True)),
            "has_secret": bool(item.get("secret")),
            "created_at": str(item.get("created_at") or ""),
            "updated_at": str(item.get("updated_at") or ""),
            "last_delivery_at": str(item.get("last_delivery_at") or ""),
            "last_status": int(item.get("last_status") or 0),
            "last_error": str(item.get("last_error") or ""),
        }

    def list_webhooks(self) -> list[dict[str, Any]]:
        data = self._load()
        webhooks = data.get("webhooks")
        if not isinstance(webhooks, list):
            return []
        out: list[dict[str, Any]] = []
        for item in webhooks:
            if isinstance(item, dict):
                out.append(self._sanitize_webhook(item))
        return out

    def replace_webhooks(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, list):
            return {"ok": False, "error": "webhooks must be a list"}

        existing = self._load()
        existing_by_id: dict[str, dict[str, Any]] = {}
        for item in existing.get("webhooks", []):
            if isinstance(item, dict):
                hook_id = str(item.get("id") or "").strip()
                if hook_id:
                    existing_by_id[hook_id] = item

        now = self._utcnow()
        next_list: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        errors: list[str] = []

        for idx, raw_item in enumerate(payload, start=1):
            if not isinstance(raw_item, dict):
                errors.append(f"item {idx}: webhook must be an object")
                continue
            hook_id = str(raw_item.get("id") or "").strip()
            if hook_id and hook_id in seen_ids:
                errors.append(f"item {idx}: duplicate id")
                continue

            url = self._normalize_url(raw_item.get("url"))
            if not url:
                errors.append(f"item {idx}: invalid webhook url")
                continue
            if len(url) > 512:
                errors.append(f"item {idx}: webhook url too long")
                continue

            events = self._normalize_events(raw_item.get("events"))
            if not events:
                errors.append(f"item {idx}: at least one event is required")
                continue

            enabled = bool(raw_item.get("enabled", True))
            prior = existing_by_id.get(hook_id) if hook_id else None
            secret = str(raw_item.get("secret") or "").strip()
            if not secret and isinstance(prior, dict):
                secret = str(prior.get("secret") or "")
            if not secret:
                errors.append(f"item {idx}: secret is required for new webhooks")
                continue
            if len(secret) < 12:
                errors.append(f"item {idx}: secret too short (min 12 chars)")
                continue
            if len(secret) > 512:
                errors.append(f"item {idx}: secret too long")
                continue

            if not hook_id:
                hook_id = uuid.uuid4().hex
            seen_ids.add(hook_id)

            created_at = str(prior.get("created_at") or now) if isinstance(prior, dict) else now
            next_item = {
                "id": hook_id,
                "url": url,
                "events": events,
                "enabled": enabled,
                "secret": secret,
                "created_at": created_at,
                "updated_at": now,
                "last_delivery_at": str(prior.get("last_delivery_at") or "") if isinstance(prior, dict) else "",
                "last_status": int(prior.get("last_status") or 0) if isinstance(prior, dict) else 0,
                "last_error": str(prior.get("last_error") or "") if isinstance(prior, dict) else "",
            }
            next_list.append(next_item)

        if errors:
            return {"ok": False, "errors": errors}

        self._save({"webhooks": next_list})
        return {"ok": True, "webhooks": [self._sanitize_webhook(item) for item in next_list]}

    @staticmethod
    def _event_matches(webhook_events: list[str], event_type: str) -> bool:
        if "*" in webhook_events:
            return True
        return event_type in webhook_events

    @staticmethod
    def _signature(secret: str, body: bytes) -> str:
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    @staticmethod
    def _request_json(url: str, headers: dict[str, str], body: bytes) -> int:
        req = urlrequest.Request(url, data=body, headers=headers, method="POST")
        with urlrequest.urlopen(req, timeout=5) as response:
            return int(response.getcode() or 0)

    def dispatch_event(self, *, event_type: str, event_payload: dict[str, Any]) -> dict[str, Any]:
        hooks_raw = self._load().get("webhooks")
        if not isinstance(hooks_raw, list):
            hooks_raw = []

        now = self._utcnow()
        attempted = 0
        delivered = 0
        updated_hooks: list[dict[str, Any]] = []

        for item in hooks_raw:
            if not isinstance(item, dict):
                continue
            hook = dict(item)
            events = self._normalize_events(hook.get("events"))
            enabled = bool(hook.get("enabled", True))
            if not enabled or not self._event_matches(events, event_type):
                updated_hooks.append(hook)
                continue

            url = self._normalize_url(hook.get("url"))
            secret = str(hook.get("secret") or "")
            if not url or not secret:
                hook["last_status"] = 0
                hook["last_error"] = "invalid webhook configuration"
                hook["last_delivery_at"] = now
                updated_hooks.append(hook)
                continue

            delivery_id = uuid.uuid4().hex
            envelope = {
                "event": event_type,
                "delivery_id": delivery_id,
                "occurred_at": now,
                "data": event_payload,
            }
            body = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
            signature = self._signature(secret, body)
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "beagle-webhook/1.0",
                "X-Beagle-Event": event_type,
                "X-Beagle-Delivery-Id": delivery_id,
                "X-Beagle-Signature": signature,
            }

            attempted += 1
            status = 0
            error_message = ""
            for attempt in range(1, 6):
                try:
                    status = self._request_json(url, headers, body)
                    if 200 <= status < 300:
                        error_message = ""
                        break
                    error_message = f"http {status}"
                except (urlerror.URLError, TimeoutError, ValueError) as exc:
                    status = 0
                    error_message = str(exc)
                if attempt < 5:
                    time.sleep(0.2 * (2 ** (attempt - 1)))

            hook["last_delivery_at"] = now
            hook["last_status"] = int(status)
            hook["last_error"] = error_message[:300]
            hook["updated_at"] = now
            if 200 <= status < 300:
                delivered += 1
            updated_hooks.append(hook)

        self._save({"webhooks": updated_hooks})
        return {
            "ok": True,
            "attempted": attempted,
            "delivered": delivered,
            "event": event_type,
        }

    def send_test_event(self, webhook_id: str) -> dict[str, Any]:
        webhook_id = str(webhook_id or "").strip()
        if not webhook_id:
            return {"ok": False, "error": "missing webhook id"}
        hooks_raw = self._load().get("webhooks")
        if not isinstance(hooks_raw, list):
            return {"ok": False, "error": "webhook not found"}

        matched = None
        for item in hooks_raw:
            if isinstance(item, dict) and str(item.get("id") or "") == webhook_id:
                matched = item
                break
        if matched is None:
            return {"ok": False, "error": "webhook not found"}

        payload = {
            "reason": "manual-test",
            "webhook_id": webhook_id,
            "timestamp": self._utcnow(),
        }
        return self.dispatch_event(event_type="beagle.webhook.test", event_payload=payload)
