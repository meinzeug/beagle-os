from __future__ import annotations

import hashlib
import hmac
import json
import logging
import logging.handlers
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request as urllib_request


@dataclass(frozen=True)
class AuditExportConfig:
    s3_bucket: str = ""
    s3_prefix: str = "audit"
    s3_region: str = "us-east-1"
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    syslog_address: str = ""
    syslog_transport: str = "udp"
    webhook_url: str = ""
    webhook_secret: str = ""
    webhook_timeout_seconds: float = 5.0


class AuditExportService:
    def __init__(
        self,
        *,
        config: AuditExportConfig,
        data_dir: Path,
        now_utc,
    ) -> None:
        self._config = config
        self._data_dir = Path(data_dir)
        self._now_utc = now_utc

    def _failure_log_file(self) -> Path:
        return self._data_dir / "audit" / "export-failures.log"

    @staticmethod
    def _redact_failure_payload(value: Any) -> Any:
        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                if any(marker in key_text.lower() for marker in ("password", "token", "secret", "key")):
                    redacted[key_text] = "[REDACTED]"
                else:
                    redacted[key_text] = AuditExportService._redact_failure_payload(item)
            return redacted
        if isinstance(value, list):
            return [AuditExportService._redact_failure_payload(item) for item in value]
        return value

    def _queue_failure(self, target: str, payload: dict[str, Any], error: Exception) -> None:
        entry = {
            "target": str(target or "unknown"),
            "timestamp": str(self._now_utc() or ""),
            "error": str(error),
            "event_id": str(payload.get("id") or ""),
            "payload": self._redact_failure_payload(payload),
        }
        line = json.dumps(entry, separators=(",", ":"), ensure_ascii=True) + "\n"
        path = self._failure_log_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def _export_s3(self, payload: dict[str, Any]) -> None:
        bucket = str(self._config.s3_bucket or "").strip()
        if not bucket:
            return
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 not installed for S3 audit export") from exc

        kwargs: dict[str, Any] = {
            "region_name": str(self._config.s3_region or "us-east-1"),
        }
        endpoint = str(self._config.s3_endpoint or "").strip()
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        access_key = str(self._config.s3_access_key or "").strip()
        secret_key = str(self._config.s3_secret_key or "").strip()
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key

        client = boto3.client("s3", **kwargs)
        event_id = str(payload.get("id") or uuid.uuid4())
        prefix = str(self._config.s3_prefix or "audit").strip().strip("/")
        timestamp = str(payload.get("timestamp") or self._now_utc())
        date_folder = timestamp[:10] if len(timestamp) >= 10 else "unknown-date"
        key = f"{prefix}/{date_folder}/{event_id}.json"
        body = (json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
        client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")

    def _parse_syslog_address(self) -> tuple[str, int] | None:
        text = str(self._config.syslog_address or "").strip()
        if not text:
            return None
        if ":" not in text:
            return text, 514
        host, _, port_text = text.rpartition(":")
        host = host.strip()
        try:
            port = int(port_text.strip())
        except ValueError:
            port = 514
        return host, max(1, min(port, 65535))

    def _export_syslog(self, payload: dict[str, Any]) -> None:
        address = self._parse_syslog_address()
        if address is None:
            return
        transport = str(self._config.syslog_transport or "udp").strip().lower()
        socktype = socket.SOCK_STREAM if transport == "tcp" else socket.SOCK_DGRAM
        handler = logging.handlers.SysLogHandler(address=address, facility=logging.handlers.SysLogHandler.LOG_LOCAL0, socktype=socktype)
        logger = logging.getLogger("beagle.audit-export")
        logger.setLevel(logging.INFO)
        logger.handlers = []
        logger.addHandler(handler)
        try:
            logger.info("beagle_audit_event %s", json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
        finally:
            handler.close()
            logger.handlers = []

    def _export_webhook(self, payload: dict[str, Any]) -> None:
        url = str(self._config.webhook_url or "").strip()
        if not url:
            return
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "beagle-audit-export/1",
        }
        secret = str(self._config.webhook_secret or "")
        if secret:
            signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            headers["X-Beagle-Signature"] = f"sha256={signature}"
        req = urllib_request.Request(url=url, data=body, headers=headers, method="POST")
        timeout = float(self._config.webhook_timeout_seconds or 5.0)
        with urllib_request.urlopen(req, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            if status < 200 or status >= 300:
                raise RuntimeError(f"webhook export failed with HTTP {status}")

    def export_event(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        for target, fn in (
            ("s3", self._export_s3),
            ("syslog", self._export_syslog),
            ("webhook", self._export_webhook),
        ):
            try:
                fn(payload)
            except Exception as exc:
                self._queue_failure(target, payload, exc)

    def get_targets_status(self) -> list[dict]:
        """Return configured export targets with their enabled status."""
        failures = self.get_failure_queue(limit=100)

        def last_error(target_type: str) -> str:
            for entry in failures:
                if str(entry.get("target") or "") == target_type:
                    return str(entry.get("error") or "")
            return ""

        targets = []
        if str(self._config.s3_bucket or "").strip():
            endpoint = str(self._config.s3_endpoint or "").strip()
            targets.append({
                "type": "s3",
                "label": "S3 / Minio",
                "enabled": True,
                "detail": endpoint if endpoint else f"s3://{self._config.s3_bucket}/{self._config.s3_prefix}",
                "last_error": last_error("s3"),
            })
        else:
            targets.append({"type": "s3", "label": "S3 / Minio", "enabled": False, "detail": "", "last_error": last_error("s3")})
        if self._parse_syslog_address():
            targets.append({
                "type": "syslog",
                "label": "Syslog",
                "enabled": True,
                "detail": str(self._config.syslog_address or ""),
                "last_error": last_error("syslog"),
            })
        else:
            targets.append({"type": "syslog", "label": "Syslog", "enabled": False, "detail": "", "last_error": last_error("syslog")})
        if str(self._config.webhook_url or "").strip():
            targets.append({
                "type": "webhook",
                "label": "Webhook",
                "enabled": True,
                "detail": str(self._config.webhook_url or ""),
                "last_error": last_error("webhook"),
            })
        else:
            targets.append({"type": "webhook", "label": "Webhook", "enabled": False, "detail": "", "last_error": last_error("webhook")})
        return targets

    def get_failure_queue(self, limit: int = 100) -> list[dict]:
        """Return the most recent export failure entries."""
        path = self._failure_log_file()
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        entries = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(entries) >= limit:
                break
        return entries

    def test_target(self, target: str) -> dict[str, Any]:
        target_name = str(target or "").strip().lower()
        payload = {
            "id": f"test-{uuid.uuid4()}",
            "timestamp": str(self._now_utc() or ""),
            "action": "audit.export.test",
            "result": "success",
            "resource_type": "audit-export-target",
            "resource_id": target_name,
        }
        if target_name == "s3":
            self._export_s3(payload)
        elif target_name == "syslog":
            self._export_syslog(payload)
        elif target_name == "webhook":
            self._export_webhook(payload)
        else:
            raise ValueError("unknown audit export target")
        return {"target": target_name, "event_id": payload["id"]}

    def replay_failures(self, *, limit: int = 100) -> dict[str, Any]:
        replayed = 0
        skipped = 0
        errors: list[str] = []
        for entry in self.get_failure_queue(limit=limit):
            payload = entry.get("payload")
            target = str(entry.get("target") or "").strip().lower()
            if not isinstance(payload, dict) or not target:
                skipped += 1
                continue
            try:
                if target == "s3":
                    self._export_s3(payload)
                elif target == "syslog":
                    self._export_syslog(payload)
                elif target == "webhook":
                    self._export_webhook(payload)
                else:
                    skipped += 1
                    continue
                replayed += 1
            except Exception as exc:
                errors.append(f"{target}:{entry.get('event_id') or ''}:{exc}")
        return {"replayed": replayed, "skipped": skipped, "errors": errors[:20]}
