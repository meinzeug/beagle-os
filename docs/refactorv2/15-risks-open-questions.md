# 15 — Risiken und offene Fragen

Stand: 2026-04-20

## Hochrisiko

### R1 — Cluster-Store-Wahl

- Risiko: falsche Wahl (etcd vs. SQLite-Litestream vs. Corosync) blockt jede weitere Welle.
- Massnahme: PoC mit etcd in Welle 7.0.0; falls Operatoren-Footprint zu hoch, Litestream als Fallback evaluieren.
- Eintrag in `docs/refactor/07-decisions.md` Pflicht.

### R2 — Live-Migration auf lokal-only Storage

- Risiko: ohne shared storage ist Live-Migration langsam und unzuverlaessig.
- Massnahme: 7.0.0 begrenzt Live-Migration auf shared storage. 7.0.1 liefert ZFS-/Ceph-Pfad. Doku klar trennen.

### R3 — Apollo-Patches nicht upstream

- Risiko: Apollo-Fork koennte stagnieren; Beagle wird Inhouse-Maintainer.
- Massnahme: Apollo-Integration als Build-Layer ueber Sunshine-Mainline halten; Fallback-Pfad auf Sunshine ohne virtual display dokumentieren.

### R4 — Linux Virtual Display

- Risiko: SudoVDA ist Windows-only. Linux braucht eigenen Pfad (vkms / DRM virtual / xvfb).
- Massnahme: Welle 7.1.1 PoC-Phase. Bei Blockern: Fallback auf x11vnc-Path (heutige Loesung) und HDR-Verzicht in v1.

### R5 — GPU-Lizenzierung (NVIDIA vGPU)

- Risiko: NVIDIA NLS Lizenzpflicht fuer mdev.
- Massnahme: vGPU als Optional-Feature dokumentieren; Default ist Full-Passthrough oder Software-Encoder.

### R6 — Mandanten-Isolation

- Risiko: Tenant-Scope-Bypass durch fehlende Filter in einzelnen Endpoints.
- Massnahme: `tenant`-Argument im RBAC-Middleware Pflicht; Test-Suite mit "cross-tenant access denied"-Fixtures.

## Mittleres Risiko

### R7 — Bestehende v1-API kann bei Cluster-Migration brechen

- Massnahme: v1 explizit "single-node-compatibility-shim" wenn cluster-size = 1; Cluster-State-Quelle ueber Adapter, sodass v1 weiterlaeuft.

### R8 — Backup-Konsistenz ohne Guest Agent

- Massnahme: `qemu-guest-agent` als Default in alle Templates aufnehmen; ohne Agent nur crash-consistent Backup, klar markiert.

### R9 — Endpoint A/B-Updates erhoehen Image-Footprint

- Massnahme: kompakte rootfs (squashfs / OSTree); Storage-Budget pro Endpoint dokumentieren.

### R10 — Watermark-Overlay verlangsamt Encoder

- Massnahme: Watermark als Apollo-Plug-in oder guest-side compositor mit minimaler Komplexitaet; Performance-Test pro Encoder.

## Niedriges Risiko

- R11 — Terraform-Provider-Wartung: Go-Modul muss separat releast werden.
- R12 — OpenTelemetry-Footprint im Python-Prozess (geringer Memory-Aufschlag).
- R13 — Zusaetzliche Doku-Pflege; loesbar durch Doc-Linter und Skill-basiertes Reviews.

## Offene Entscheidungen (zu fuehren in `docs/refactor/07-decisions.md`)

1. Cluster-Store: etcd vs. SQLite-Litestream vs. Corosync.
2. Default-Storage-Backend fuer Welle 7.0.1: ZFS oder NFS oder beides.
3. Streaming-Backend in 7.1.1: Apollo-only oder Apollo+Sunshine selektierbar.
4. Linux Virtual Display: vkms vs. xvfb vs. xrandr-virtual.
5. Backup-Format: PBS-kompatibel vs. Restic-kompatibel vs. eigenes Format.
6. SDN-Implementierung: nftables-only vs. nftables+OVS.
7. CLI-Sprache: Python (`beagle-host` Codebase reuse) vs. Go (deploy als Single-Binary).
8. Web Console UI-Stack-Refresh oder inkrementeller Ausbau.

## Annahmen

- Die bestehenden Welle-1-Komponenten (`beagle-host/services/*`, `core/`, `providers/`) bleiben strukturell stabil.
- Beagle Server OS bleibt Debian-basiert.
- KVM/QEMU/libvirt-Stack bleibt der primaere Compute-Layer.
- Sunshine/Apollo + Moonlight bleibt der primaere Streaming-Layer.

## Out of Scope fuer 7.0

- ARM-Hosts (kommt fruehestens in 8.x).
- Container-Workloads als first-class Citizens (heute ist es Hypervisor + Streaming + Endpoint; Container koennen via VM laufen).
- Public-SaaS-Variante "Beagle Cloud" (separates Produktthema).
- Eigenes Beagle-Hypervisor-Forking (KVM/QEMU bleibt; eigener Hypervisor frueheste 9.x).
