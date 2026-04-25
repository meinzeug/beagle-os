"""TPM Attestation Service — validates thin-client integrity reports.

GoEnterprise Plan 02, Schritt 2
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AttestationReport:
    """Report sent by thin-client containing TPM PCR measurements."""
    device_id: str
    reported_at: str
    pcr_values: dict[str, str]   # {"pcr0": "<hex>", "pcr1": "...", ...}
    signature: str               # base64 signature by TPM endorsement key
    firmware_version: str = ""
    kernel_cmdline_hash: str = ""


@dataclass
class AttestationRecord:
    device_id: str
    status: str          # "attested" | "compromised" | "unknown"
    last_checked: str
    failure_reason: str = ""
    trusted_pcr_values: dict[str, str] = field(default_factory=dict)


def attestation_record_from_dict(d: dict[str, Any]) -> AttestationRecord:
    return AttestationRecord(
        device_id=d["device_id"],
        status=d.get("status", "unknown"),
        last_checked=d.get("last_checked", ""),
        failure_reason=d.get("failure_reason", ""),
        trusted_pcr_values=d.get("trusted_pcr_values", {}),
    )


class AttestationService:
    """
    Validates TPM attestation reports from thin-clients.

    Workflow:
    1. Admin registers trusted PCR baseline for a device model/image.
    2. Thin-client sends `AttestationReport` at enrollment + periodically.
    3. Service compares PCRs against baseline.
    4. If mismatch → device marked `compromised`, session allocation blocked.
    """

    STATE_FILE = Path("/var/lib/beagle/beagle-manager/attestation.json")

    def __init__(self, state_file: Path | None = None, utcnow: Any = None) -> None:
        self._state_file = state_file or self.STATE_FILE
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._utcnow = utcnow or self._default_utcnow
        self._state = self._load()

    # ------------------------------------------------------------------
    # Baseline management
    # ------------------------------------------------------------------

    def register_baseline(self, image_id: str, pcr_values: dict[str, str]) -> None:
        """Register known-good PCR values for an image/device-model."""
        self._state["baselines"][image_id] = pcr_values
        self._save()

    def get_baseline(self, image_id: str) -> dict[str, str] | None:
        return self._state["baselines"].get(image_id)

    # ------------------------------------------------------------------
    # Report validation
    # ------------------------------------------------------------------

    def validate_report(
        self,
        report: AttestationReport,
        image_id: str,
    ) -> AttestationRecord:
        """
        Validate an attestation report against the baseline.

        Returns AttestationRecord with status="attested" or "compromised".
        If no baseline registered → status="unknown" (pass-through for now).
        """
        now = self._utcnow()
        baseline = self._state["baselines"].get(image_id)

        if baseline is None:
            record = AttestationRecord(
                device_id=report.device_id,
                status="unknown",
                last_checked=now,
                failure_reason="no_baseline_registered",
            )
        else:
            # Compare security-critical PCRs (0=UEFI firmware, 4=bootloader, 7=secure-boot)
            critical_pcrs = {"pcr0", "pcr4", "pcr7"}
            mismatches = []
            for pcr in critical_pcrs:
                expected = baseline.get(pcr)
                actual = report.pcr_values.get(pcr)
                if expected and actual and expected.lower() != actual.lower():
                    mismatches.append(f"{pcr}: expected={expected[:8]}… got={actual[:8]}…")

            if mismatches:
                status = "compromised"
                reason = "; ".join(mismatches)
            else:
                status = "attested"
                reason = ""

            record = AttestationRecord(
                device_id=report.device_id,
                status=status,
                last_checked=now,
                failure_reason=reason,
                trusted_pcr_values=report.pcr_values if status == "attested" else {},
            )

        self._state["records"][report.device_id] = asdict(record)
        self._save()
        return record

    def get_record(self, device_id: str) -> AttestationRecord | None:
        d = self._state["records"].get(device_id)
        return attestation_record_from_dict(d) if d else None

    def is_session_allowed(self, device_id: str) -> tuple[bool, str]:
        """Return (allowed, reason) — blocks sessions for compromised devices."""
        record = self.get_record(device_id)
        if record is None:
            return True, "no_attestation_record (pass)"
        if record.status == "compromised":
            return False, f"device_compromised: {record.failure_reason}"
        return True, f"status={record.status}"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if self._state_file.exists():
            return json.loads(self._state_file.read_text())
        return {"baselines": {}, "records": {}}

    def _save(self) -> None:
        self._state_file.write_text(json.dumps(self._state, indent=2))

    @staticmethod
    def _default_utcnow() -> str:
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
