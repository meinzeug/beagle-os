# 09 — Backup und DR

Stand: 2026-04-20

## Stand heute

- Kein integriertes Backup. Snapshots sind ad hoc.
- Update-/Release-Stream ist artifact-zentriert, nicht VM-Backup.

## Ziel 7.0

### Backup-Modell

- `BackupJob` ist first-class:

```yaml
BackupJob:
  id: bj-engineering-nightly
  tenant: acme
  selector:
    pools: [pool-engineering]
    tags: ["backup:nightly"]
  schedule: "0 2 * * *"
  target: target-s3-acme
  mode: incremental
  consistency: fs-freeze | crash-consistent
  retention:
    daily: 14
    weekly: 8
    monthly: 6
  encryption: client-side:age
  notify_on_failure: webhook:ops-pager
```

- `BackupTarget` Beispiele: `local`, `nfs`, `s3`, `restic-repo`, optional `pbs-datastore`.

### Inkrementelle Backups

- qcow2: dirty bitmap fuer differential backups.
- ZFS: send/recv inkrementell zwischen Snapshots.
- Ceph RBD: rbd export-diff.
- Konsistenz: optional `qemu-guest-agent` fs-freeze hook fuer applikationskonsistente Snapshots.

### Storage-Effizienz

- Server-side dedup nur dort, wo das Backend das hergibt (restic, PBS).
- Komprimierung default zstd.
- Verschluesselung client-side (Schluessel in Tenant-KMS, nicht im Backup-Target).

### Restore

- **Full Restore**: VM aus Backup-Image neu materialisieren.
- **Live-Restore** (PBS-Stil): VM startet sofort, Daten werden im Hintergrund nachgereicht.
- **Single-File-Restore**: Backup-Image wird via libguestfs gemountet, einzelne Dateien koennen aus Web Console gezogen werden.
- **Cross-Tenant-Restore** ist explizit verboten ohne Plattform-Admin-Override.

### Replication

- Pro Pool / VM ein optionales `ReplicationProfile`:

```yaml
ReplicationProfile:
  id: rep-acme-dr
  source_cluster: cluster-fra
  target_cluster: cluster-ber
  schedule: "*/15 * * * *"
  mode: zfs-send | rbd-mirror | qcow2-diff
  bandwidth_limit_mbps: 100
```

- Zielcluster kann passiver Standby sein. DR-Failover-Workflow:
  1. Source-Cluster wird als unhealthy markiert.
  2. Operator triggert `failover` auf Zielcluster.
  3. Replizierte VMs werden boot-bar gemacht (image-promote).
  4. Streaming-Endpoints werden auf neue IPs umgesteckt (DNS / Endpoint-Reconfig).

### Audit + Compliance

- Jeder Backup-Run schreibt Audit-Event mit Hash-Fingerprint des erzeugten Artefakts.
- Optionaler "immutable" Modus (S3 object lock) fuer Compliance-Backups.
- Restore-Operationen werden pro Datei auditiert (Single-File-Restore).

### Akzeptanzkriterien fuer 7.3.0

- 80 GB Desktop-VM nightly inkrementell, durchschnittliche Inkrement-Dauer <= 5 min.
- Live-Restore startet die VM in <= 60 s (Hintergrund-Copy laeuft danach).
- Single-File-Restore aus 7-Tage-altem Backup ueber Web Console.
- Verschluesselte Backups, Schluesselrotation getestet.
- Replication-Failover Probelauf zwischen zwei Test-Clustern erfolgreich.

## Migration

- 6.7.0 hat noch keine Backups. 7.0 baut Backup-Plane greenfield.
- Bestehende Snapshot-Workflows (ad hoc) werden in `BackupJob`-Objekte gehoben.
