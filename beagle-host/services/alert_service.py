"""Alert Service — Fleet-Alerts + Notification Dispatch.

GoEnterprise Plan 07, Schritt 3
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
from typing import Any, Callable

from core.persistence.json_state_store import JsonStateStore

_LOG = logging.getLogger("beagle.alerts")


@dataclass
class AlertRule:
    rule_id: str
    name: str
    metric: str                  # e.g. "disk_reallocated_sectors", "cpu_temp_c"
    threshold: float
    severity: str = "warning"    # "warning" | "critical"
    channels: list[str] = field(default_factory=list)  # ["console", "email", "webhook"]
    enabled: bool = True


@dataclass
class AlertEvent:
    alert_id: str
    rule_id: str
    device_id: str
    metric: str
    current_value: float
    threshold: float
    severity: str
    message: str
    fired_at: str
    resolved: bool = False
    resolved_at: str = ""


class AlertService:
    """
    Fleet-wide alert rules + notification dispatch.

    Ingests AnomalyReport objects from FleetTelemetryService and fires
    alerts via configured channels.

    Channels:
      - "console": logs to stdout
      - "email": calls email_fn(subject, body) if configured
      - "webhook": calls webhook_fn(payload) if configured

    GoEnterprise Plan 07, Schritt 3
    """

    STATE_FILE = Path("/var/lib/beagle/alert-service/state.json")

    def __init__(
        self,
        state_file: Path | None = None,
        utcnow: Callable[[], str] | None = None,
        email_fn: Callable[[str, str], None] | None = None,
        webhook_fn: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._store = JsonStateStore(
            state_file or self.STATE_FILE,
            default_factory=lambda: {"rules": {}, "events": []},
        )
        self._utcnow = utcnow or self._default_utcnow
        self._email_fn = email_fn
        self._webhook_fn = webhook_fn
        self._state = self._store.load()

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: AlertRule) -> AlertRule:
        self._state["rules"][rule.rule_id] = asdict(rule)
        self._save()
        return rule

    def get_rule(self, rule_id: str) -> AlertRule | None:
        d = self._state["rules"].get(rule_id)
        return AlertRule(**d) if d else None

    def list_rules(self) -> list[AlertRule]:
        return [AlertRule(**d) for d in self._state["rules"].values()]

    def delete_rule(self, rule_id: str) -> bool:
        if rule_id not in self._state["rules"]:
            return False
        del self._state["rules"][rule_id]
        self._save()
        return True

    def update_rule(self, rule_id: str, updates: dict[str, Any]) -> AlertRule:
        if rule_id not in self._state["rules"]:
            raise KeyError(f"Rule {rule_id!r} not found")
        self._state["rules"][rule_id].update(updates)
        self._save()
        return AlertRule(**self._state["rules"][rule_id])

    def ensure_default_rules(self) -> list[AlertRule]:
        defaults = [
            AlertRule(
                rule_id="disk_failure_predicted",
                name="Disk failure predicted",
                metric="disk_reallocated_sectors",
                threshold=5.0,
                severity="critical",
                channels=["console", "webhook"],
            ),
            AlertRule(
                rule_id="gpu_thermal_limit_approaching",
                name="GPU thermal limit approaching",
                metric="gpu_temp_c",
                threshold=85.0,
                severity="warning",
                channels=["console", "webhook"],
            ),
            AlertRule(
                rule_id="thin_client_hardware_degradation",
                name="Thin-client hardware degradation",
                metric="reboot_count_7d",
                threshold=5.0,
                severity="warning",
                channels=["console", "webhook"],
            ),
            AlertRule(
                rule_id="node_memory_ecc_errors",
                name="Node memory ECC errors",
                metric="ram_ecc_errors",
                threshold=10.0,
                severity="critical",
                channels=["console", "webhook"],
            ),
            AlertRule(
                rule_id="energy_feed_import_failed",
                name="Energy feed import failed",
                metric="energy_feed_import",
                threshold=1.0,
                severity="warning",
                channels=["console", "webhook"],
            ),
        ]
        created: list[AlertRule] = []
        for rule in defaults:
            if self.get_rule(rule.rule_id) is None:
                self.add_rule(rule)
                created.append(rule)
        return created

    # ------------------------------------------------------------------
    # Alert firing
    # ------------------------------------------------------------------

    def check_anomalies(self, device_id: str, anomaly_reports: list[Any]) -> list[AlertEvent]:
        """
        Check anomaly reports against rules and fire matching alerts.
        anomaly_reports: list of AnomalyReport objects (from FleetTelemetryService).
        Returns list of newly fired AlertEvent objects.
        """
        fired = []
        for report in anomaly_reports:
            for rule in self.list_rules():
                if not rule.enabled:
                    continue
                if rule.metric != report.metric:
                    continue
                if report.current_value < rule.threshold:
                    continue
                # Check deduplication: don't re-fire if same (device, rule) is already open
                existing = self._find_open_alert(device_id, rule.rule_id)
                if existing:
                    continue
                event = AlertEvent(
                    alert_id=f"{device_id}:{rule.rule_id}:{self._utcnow()}",
                    rule_id=rule.rule_id,
                    device_id=device_id,
                    metric=rule.metric,
                    current_value=report.current_value,
                    threshold=rule.threshold,
                    severity=rule.severity,
                    message=f"{device_id}: {rule.metric}={report.current_value} ≥ threshold {rule.threshold} ({rule.severity})",
                    fired_at=self._utcnow(),
                )
                self._state["events"].append(asdict(event))
                self._dispatch(event, rule.channels)
                fired.append(event)
        if fired:
            self._save()
        return fired

    def fire_alert(
        self,
        *,
        rule_id: str,
        device_id: str,
        metric: str,
        current_value: float,
        message: str = "",
    ) -> AlertEvent:
        """Manually fire an alert (used for custom checks outside anomaly detection)."""
        rule = self.get_rule(rule_id)
        severity = rule.severity if rule else "warning"
        channels = rule.channels if rule else []
        event = AlertEvent(
            alert_id=f"{device_id}:{rule_id}:{self._utcnow()}",
            rule_id=rule_id,
            device_id=device_id,
            metric=metric,
            current_value=current_value,
            threshold=rule.threshold if rule else 0.0,
            severity=severity,
            message=message or f"{device_id}: {metric}={current_value} alert",
            fired_at=self._utcnow(),
        )
        self._state["events"].append(asdict(event))
        self._dispatch(event, channels)
        self._save()
        return event

    def resolve_alert(self, alert_id: str) -> AlertEvent | None:
        for ev_dict in self._state["events"]:
            if ev_dict["alert_id"] == alert_id and not ev_dict.get("resolved"):
                ev_dict["resolved"] = True
                ev_dict["resolved_at"] = self._utcnow()
                self._save()
                return AlertEvent(**ev_dict)
        return None

    def get_open_alerts(self, device_id: str | None = None) -> list[AlertEvent]:
        events = [AlertEvent(**d) for d in self._state["events"] if not d.get("resolved")]
        if device_id:
            events = [e for e in events if e.device_id == device_id]
        return events

    def get_all_alerts(self, device_id: str | None = None) -> list[AlertEvent]:
        events = [AlertEvent(**d) for d in self._state["events"]]
        if device_id:
            events = [e for e in events if e.device_id == device_id]
        return events

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _find_open_alert(self, device_id: str, rule_id: str) -> AlertEvent | None:
        for ev in self._state["events"]:
            if (ev.get("device_id") == device_id
                    and ev.get("rule_id") == rule_id
                    and not ev.get("resolved")):
                return AlertEvent(**ev)
        return None

    def _dispatch(self, event: AlertEvent, channels: list[str]) -> None:
        for channel in channels:
            if channel == "console":
                _LOG.warning("[ALERT][%s] %s", event.severity.upper(), event.message)
            elif channel == "email" and self._email_fn:
                try:
                    self._email_fn(f"[Beagle Alert] {event.severity}: {event.metric}", event.message)
                except Exception:
                    pass
            elif channel == "webhook" and self._webhook_fn:
                try:
                    self._webhook_fn(asdict(event))
                except Exception:
                    pass

    def _save(self) -> None:
        self._store.save(self._state)

    @staticmethod
    def _default_utcnow() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
