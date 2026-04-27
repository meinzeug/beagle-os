# 11 — Endpoint-/Thin-Client-Strategie

Stand: 2026-04-20

## Stand heute

- `beagle-os/` baut Endpoint-OS (Live-/Installer-ISO).
- `thin-client-assistant/` enthaelt Runtime, Installer, USB-Builder.
- `beagle-kiosk/` als Gaming-Kiosk-Variante.
- Provisioning-Bootstrap in `beagle-host/services/endpoint_*` und Token-Store.

## Ziel 7.0

### Drei Endpoint-Profile

| Profil | Use Case | Default-UI |
|---|---|---|
| `desktop-thin-client` | Office-Desktop ueber Streaming | Beagle Endpoint OS + Moonlight Wrapper |
| `gaming-kiosk` | Spielelobby (heutiges `beagle-kiosk`) | Electron Kiosk |
| `engineering-station` | GPU-/Wacom-tauglich, Multi-Monitor | Beagle Endpoint OS + Moonlight + Tablet-Stack |

Alle drei teilen denselben Beagle-Endpoint-Kern; Profile aktivieren spezifische Pakete und systemd-Targets.

### Enrollment-Flow

```
1. Operator legt Endpoint-Token in Web Console an (scope: tenant, profile, validity).
2. Endpoint bootet Live-ISO oder installierte Beagle Endpoint OS Instanz.
3. Endpoint zeigt einen QR-Code und kurzen Code (z.B. ABCD-1234).
4. User scannt im User-Portal -> Code wird mit Token gepaart.
5. Endpoint enrollt sich beim Cluster, erhaelt Endpoint-ID + Cluster-CA + Pairing-Material.
6. Endpoint zeigt User-Login (lokal/OIDC/SAML) -> User bekommt seinen Pool/Desktop.
```

### Updates (A/B)

- Endpoint OS bekommt zwei System-Slots (A/B) plus Boot-Loader-Slot-Switch.
- Update-Service (`thin-client-assistant/runtime/update_*`) zieht signiertes Image vom Cluster oder vom Public Update Feed.
- Bei Boot-Failure automatisches Rollback in alten Slot.
- Optional OSTree als Implementation; Mindestanforderung ist eine reproduzierbare A/B-Strategie.

### Pairing- und Streaming-Pfad

- Endpoint nutzt **denselben Pairing-Token-Flow** wie der Browser (siehe [05-streaming-protocol-strategy.md](05-streaming-protocol-strategy.md)).
- Moonlight-Embedded mit Beagle-Pairing-Plug-in oder beagle-eigener Wrapper.
- Stream-Health wird zurueckgemeldet -> Session-Object.

### Offline / Edge

- Endpoint speichert letzte erfolgreiche Pool-Konfiguration und kann mit kurzem Cache offline starten (zeigt z.B. "Cluster nicht erreichbar" UI).
- Bootstrap-Token-Renewal vor Ablauf, sonst Re-Enrollment-Flow.

### Sicherheit

- TPM-/Disk-Encryption-Default fuer installierte Endpoints (`thin-client-assistant/installer`).
- Hardened Default-User: kein Root-Login per Default, SSH disabled per Default, optional ueber Tenant-Policy aktivierbar.
- Endpoint-Identity ueber Cluster-CA-signiertes Zertifikat.

### Web-Endpoint-Variante

- Beagle Web Portal kann Streaming auch im Browser anbieten (WebRTC + Moonlight-Web-Client).
- Sinnvoll fuer BYOD/Gast-Zugang.
- Pairing-Flow identisch.

### Provider-Neutralitaet

- Endpoint-Pfad spricht nur mit der **Beagle Cluster API**, nie direkt mit Beagle host/Libvirt.
- Pool-/Session-Auswahl ist Cluster-API-getrieben.

### Akzeptanzkriterien

- Frischer Thin Client von ISO bis erstem Stream: <= 10 min.
- A/B-Update-Test: erfolgreiches Update + erzwungenes Rollback bei Boot-Fail.
- Endpoint-Re-Enrollment nach Token-Ablauf ohne USB-Touch.
