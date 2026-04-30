# Beagle OS — Data Retention & Compliance

This document covers all personal data categories processed by Beagle OS,
their retention rules, and the approach to PII redaction.

It applies to the control plane (`beagle-control-plane`), the KVM/libvirt
hypervisor layer, and the thin-client endpoint stack.

---

## 1. Data Categories

| Category | Description | Storage Location | Contains PII? |
|---|---|---|---|
| **Users / Credentials** | Admin and operator accounts (username, hashed password, TOTP secret, OIDC sub) | `/var/lib/beagle/beagle-manager/auth-state.json` + SQLite sessions table | Yes (username) |
| **Sessions / Tokens** | Bearer tokens, refresh tokens, session metadata | `auth-state.json` (in-memory expiry) | Yes (username, IP) |
| **Audit Events** | All admin actions: logins, VM ops, policy changes, RBAC changes | `audit-log.json` / audit export targets | Yes (username, IP, resource ID) |
| **VM State** | VM inventory, IDs, names, status, node assignment | `state.db` → `vms` table + `provider-state/` | No |
| **Pool State** | VDI pool definitions, assignments, prewarm events | `state.db` → `pools` table | Indirect (pool/user assignment) |
| **Device Registry** | Enrolled thin clients: device ID, fingerprint, hostname, status, last seen | `state.db` → `devices` table | Yes (hostname, fingerprint) |
| **Stream / Session Health** | Sunshine/Moonlight pairing, stream health metrics | `stream-health.json`, in-memory | Yes (client IP) |
| **Endpoint HW Info** | CPU, RAM, disk, GPU, NIC reported by thin client | `fleet-telemetry/`, `device-registry.json` | No (hardware only) |
| **Backup Targets** | S3/SFTP credentials used for backup exports | `/etc/beagle/credentials.env` (operator-managed) | Yes (secrets) |
| **GPU Inventory** | PCIe GPU IDs, driver, vGPU profile | `state.db` → `gpus` table | No |
| **Session Recordings** | Optional session video recordings | Configurable path / S3 bucket | Yes (screen content) |
| **Energy / Usage Metrics** | Power consumption, usage hours per VM/user | `energy/`, `usage/` directories | Indirect (VM→user mapping) |

---

## 2. Retention Rules

| Data Category | Retention Period | Deletion Mechanism |
|---|---|---|
| Users / Credentials | Until explicitly deleted by admin | Manual via API / admin UI |
| Active Sessions / Tokens | 15 minutes (access) / 7 days (refresh) | Automatic expiry on next request |
| Audit Events | **90 days** (default) | Configurable via `BEAGLE_AUDIT_RETENTION_DAYS` env var; purge job runs on every startup and daily cron |
| VM State | Until VM is deleted | Cascades on `DELETE /api/v1/vms/{vmid}` |
| Pool State | Until pool is deleted | Cascades on pool delete API |
| Device Registry | Until device is unenrolled | Manual via API or auto-expiry after `BEAGLE_MANAGER_STALE_ENDPOINT_SECONDS` (default 600 s) |
| Stream / Session Health | Session lifetime (in-memory) | Cleared on session end |
| Endpoint HW Info | Latest snapshot only; overwritten on next check-in | No accumulation |
| Backup Target Credentials | Until operator removes from `/etc/beagle/credentials.env` | Manual |
| Session Recordings | `BEAGLE_RECORDING_RETENTION_DEFAULT_DAYS` (default 30 days) | Retention cron (`BEAGLE_RECORDING_RETENTION_CRON_SECONDS`, default 1 h) |
| Energy / Usage Metrics | Rolling window, 30 days | Purge in `energy_service` on start |

### Override via Environment Variables

```
BEAGLE_AUDIT_RETENTION_DAYS=90         # audit log max age (days)
BEAGLE_RECORDING_RETENTION_DEFAULT_DAYS=30  # session recording max age (days)
BEAGLE_MANAGER_STALE_ENDPOINT_SECONDS=600   # device registry expiry
```

---

## 3. PII Redaction

### In Audit Logs

- IP addresses are stored as-is in the internal audit log.
- When exporting via `BEAGLE_AUDIT_EXPORT_*` targets (S3, syslog, webhook), the
  export pipeline masks IPs by default: the last octet is set to `.0`
  (e.g., `192.168.1.42` → `192.168.1.0`).
- Usernames in audit events are hashed in exports if
  `BEAGLE_AUDIT_EXPORT_PSEUDONYMIZE_USERS=1` is set (default: off for
  traceability in small deployments).

### In Session Recordings

- Recordings are end-to-end stored as-is (screen capture).
- No automatic redaction of on-screen content.
- Operators are responsible for classifying recording storage as restricted data.

### In Device Registry

- Device fingerprint is a hardware-derived hash; not directly PII but can be
  used to track a device.
- Hostname may contain user-identifying strings (e.g., `dennis-laptop`).
- Both fields are purged when a device is unenrolled.

---

## 4. GDPR / Data Processing Basis

Beagle OS is an on-premises product. The operator (customer) is the data controller.
Beagle OS (the software vendor) does not receive, process, or store any customer data.

- **Lawful basis**: Legitimate interest (operator infrastructure management).
- **Data subject rights**: Fulfilled by the operator using the API (export/delete user, audit, device).
- **Sub-processors**: None built-in. Operator-configured export targets (S3, syslog, webhook) are
  the operator's own sub-processors.

For pilot customers requiring a Data Processing Agreement (DPA), contact the operator team.

---

## 5. Secrets Handling

- TLS certificates: `/etc/beagle/manager-ssl.pem` (operator-managed).
- Backup/export credentials: `/etc/beagle/credentials.env` (chmod 0600, not versioned).
- Admin bootstrap credentials: `/root/beagle-firstboot-credentials.txt` (chmod 0600 on srv1).
- No secrets are stored in the repository or release artifacts.

---

## 6. Audit Export Targets (Production)

Current configuration on `srv1.beagle-os.com`:

- **Syslog**: not configured (set via `BEAGLE_AUDIT_EXPORT_SYSLOG_ADDRESS`)
- **S3**: not configured (set via `BEAGLE_AUDIT_EXPORT_S3_BUCKET`)
- **Webhook**: not configured (set via `BEAGLE_AUDIT_EXPORT_WEBHOOK_URL`)

To activate audit export for pilot customers, configure the relevant env vars in
`/etc/beagle/beagle-manager.env` and restart the control plane.

---

*Last updated: 2026-04-30 — verified against Beagle OS 8.0 on srv1.beagle-os.com*
