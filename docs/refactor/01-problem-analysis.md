# Beagle OS Refactor - Problem Analysis

Stand: 2026-04-13

## Kernprobleme heute

### 1. Historischer Token-First Zugang
- Web-Zugang ist noch auf API-Token-Feld ausgelegt.
- Kein vollstaendiger username/password Login als Standard.
- Rollenmodell nicht durchgaengig in allen Mutations-Endpunkten erzwungen.

### 2. Unvollstaendige IAM-/RBAC-Durchdringung
- Fehlende zentrale Policy-Engine fuer Aktion + Scope + Objekt.
- Uneinheitliche Trennung zwischen Operator-, Support- und Tenant-Rechten.
- Auditierbarkeit von Berechtigungsentscheidungen nicht ausreichend standardisiert.

### 3. Feature-Silos statt Plattform-Backplane
- VM lifecycle, streaming readiness, endpoint state und provisioning sind technisch vorhanden, aber nicht als einheitlicher Plattformfluss modelliert.
- Task-, Event- und Fehlerbilder variieren zwischen Teilflaechen.

### 4. Noch kein beagle-native Vollbild fuer "so maechtig wie Enterprise-Stacks"
- Es fehlen klar priorisierte Capability-Matrizen fuer Compute, HA, Storage, Network, IAM, Backup, Operations.
- Migrationsplan ist bislang nicht konsequent auf "ohne Proxmox" ausgerichtet.

## Auswirkungen
- Operative Reibung bei Teambetrieb und Berechtigungen.
- Hoher Integrationsaufwand bei neuen Features.
- Risiko fuer regressionsarme Skalierung auf Multi-Node/Enterprise-Setups.

## Architekturursachen
- Historisch inkrementeller Aufbau entlang kurzfristiger Integrationsziele.
- Noch nicht vollendete Entkopplung von UI, Domain-Services und Provider-Adaptern.
- Fehlende kanonische Domain Contracts fuer alle Tier-1 Capabilities.

## Abgeleitete Muss-Ziele
- Login mit username/password + session lifecycle als Primarzugang.
- Serverseitige RBAC-Enforcement-Matrix fuer 100% mutierende APIs.
- Plattformweite Task/Event/Audit-Normalisierung.
- Roadmap auf beagle-native Runtime als Hauptpfad.
