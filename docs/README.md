# Beagle OS — Dokumentation

**Stand**: 2026-04-29 · **Version**: 8.0 · **Quelle der Wahrheit**: [`MASTER-PLAN.md`](MASTER-PLAN.md)

Beagle OS ist eine Open-Source Desktop-Virtualisierungs- und Streaming-Plattform
auf KVM/libvirt-Basis. Diese Dokumentation ist **bewusst klein gehalten**: wenige
kanonische Dateien, alles andere ist im Archiv.

---

## Operative Checklisten (Quelle der Wahrheit fuer offene Arbeit)

Genau **5 Dateien**. Jede Aufgabe lebt nur in einer dieser Listen.

| # | Datei | Thema |
|---|---|---|
| 01 | [checklists/01-platform.md](checklists/01-platform.md) | Cluster, Storage, HA, VDI, GPU, Netzwerk |
| 02 | [checklists/02-streaming-endpoint.md](checklists/02-streaming-endpoint.md) | BeagleStream, Endpoint OS, Thin Client, Kiosk |
| 03 | [checklists/03-security.md](checklists/03-security.md) | Auth, RBAC, Secrets, Audit, TLS, Compliance |
| 04 | [checklists/04-quality-ci.md](checklists/04-quality-ci.md) | CI, Tests, Observability, Datenintegritaet, UX/i18n |
| 05 | [checklists/05-release-operations.md](checklists/05-release-operations.md) | Release-Gates R0..R4, Runbooks, Operations |

---

## Strategie + Architektur

| Datei | Inhalt |
|---|---|
| [MASTER-PLAN.md](MASTER-PLAN.md) | Kanonische Gesamtsicht (Vision, Layer-Modell, Themen-Zuordnung) |
| [architecture/overview.md](architecture/overview.md) | System-Architektur (Bestand) |
| [architecture/endpoint-update.md](architecture/endpoint-update.md) | Endpoint-Update-Architektur |

---

## Operatives Logbuch (chronologisch, nicht abhakbar)

| Datei | Inhalt |
|---|---|
| [refactor/05-progress.md](refactor/05-progress.md) | Append-only Run-Log |
| [refactor/06-next-steps.md](refactor/06-next-steps.md) | Aktueller Stand (oben) + naechste Schritte |
| [refactor/07-decisions.md](refactor/07-decisions.md) | Architektur-/Arbeitsregel-Entscheidungen |
| [refactor/11-security-findings.md](refactor/11-security-findings.md) | Security-Funde + Restrisiken |

Hinweis: `refactor/00-09-*.md` sind historisch und werden nicht mehr aktiv gepflegt
(Inhalte aufgegangen in `MASTER-PLAN.md` + Checklisten).

---

## Referenzen

| Bereich | Datei |
|---|---|
| Contributing | [contributing.md](contributing.md) |
| API | [api/openapi-v1-coverage.md](api/openapi-v1-coverage.md), [api/breaking-change-policy.md](api/breaking-change-policy.md) |
| Deployment | [deployment/](deployment/) (Hetzner installimage, beagle-os build, thin client, PXE) |
| Security | [security/](security/) (overview, secret-inventory, secret-lifecycle, tls-bypass-allowlist) |
| Observability | [observability/setup.md](observability/setup.md) |

---

## Archiv

`docs/archive/` enthaelt die historischen Mehrfach-Pl?ne (`gofuture/`, `goenterprise/`,
`goadvanced/`, `gorelease/`, `refactorv2/`). Sie sind **nicht aktive Auftraege**,
sondern Hintergrund-/Recherchematerial. Wenn ein Punkt aus dem Archiv noch relevant
ist, gehoert er in eine der 5 Checklisten — sonst bleibt er archiviert.

---

## Regeln fuer Aenderungen

1. Neue Aufgaben kommen in **eine** der 5 Checklisten — niemals in eine neue Datei.
2. Erledigte Aufgaben werden auf `[x]` gesetzt, nicht geloescht.
3. Chronologische Notizen kommen in `refactor/05-progress.md`.
4. Architektur-/Arbeitsregel-Entscheidungen in `refactor/07-decisions.md`.
5. Wenn ein Bereich keine offenen `[ ]`-Items mehr hat, bleibt die Datei leer-aber-existent.
