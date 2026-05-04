# Diamond Plan

Stand: 2026-05-04
Version: 8.0.9

Dieser Plan beschreibt den direkten Weg vom aktuellen Beagle-OS-Stand zu einer
Software, die nicht nur technisch beeindruckt, sondern als echtes Produkt einen
Durchbruch schaffen kann.

Er ersetzt keine Detail-Checkliste. Operative Aufgaben bleiben in
`docs/checklists/*`. Der Diamond Plan definiert Reihenfolge, Gates,
Abnahmekriterien und No-Go-Regeln fuer das Endziel.

## Endziel: Diamond State

Beagle OS erreicht den Diamond State, wenn ein externer Betreiber ohne
Entwicklerhilfe diese Kette wiederholt erfolgreich ausfuehren kann:

1. Bare-Metal-Host aus aktuellem Release installieren.
2. Web Console oeffnen, anmelden und Health-Check bestehen.
3. VM ueber WebUI erstellen, Firstboot/Reboot/Desktop abschliessen.
4. VM-spezifischen Thinclient/Live-USB erzeugen.
5. Thinclient bootet, enrollt, aktiviert WireGuard und zeigt den Desktop per
   BeagleStream ohne manuelle PIN.
6. Backup der VM erstellen, auf frischem oder zweitem Host restoren und booten.
7. Update aus Release-Artefakt einspielen und Rollback/Restore beweisen.
8. Zwei-Host-Betrieb mit Join, Drain, Failover/Fencing und Audit-Nachweis
   bestehen.
9. Security-Review ohne offene Critical/High Findings abschliessen.
10. Pilot-Runbook, Incident-Prozess, Supportpfad und kommerzielle Lizenzgrenze
    sind fuer Firmenkunden klar.

Erst dann ist Beagle OS nicht mehr nur ein starkes Engineering-Projekt, sondern
ein pilot- und verkaufsfaehiges Produkt.

## Diamond-Schnitt

Alles, was nicht eines dieser Ziele direkt freischaltet, wird nach hinten
geschoben:

| Prioritaet | Muss jetzt passieren | Wird bewusst verschoben |
|---|---|---|
| Stabilitaet | Clean-Install, VM-Lifecycle, Stream, Restore | neue Komfortfeatures |
| Vertrauen | Security, Runbooks, Update/Rollback | experimentelle UI-Ideen |
| Beweis | echte Hardware, echte Hosts, echte Thinclients | reine Mock-Erfolge |
| Produkt | klare Namen, Supportpfad, Lizenzgrenze | oeffentliche SaaS-Story |
| Wiederholbarkeit | Release-Artefakte, Logs, Checksummen | manuelle Live-Hotfixes |

## Phase D0 - Runtime einfrieren und Drift entfernen ✅ BESTANDEN 2026-05-04

Ziel: Ein stabiler Ausgangspunkt, auf dem alle weiteren Abnahmen aufbauen.

Abnahme:

- ✅ `main`, lokaler Checkout, GitHub Actions, `srv1` und Public-Artefakte zeigen
  dieselbe Version (8.0.9, commit c1f76b1efea8).
- ✅ `srv1` hat keine roten Beagle-Pflichtdienste (systemctl --failed: 0 units).
- ✅ `repo-auto-update-status.json` (state=healthy, installed==remote==8.0.9)
  und `beagle-downloads-status.json` (version=8.0.9) widersprechen sich nicht.
- ✅ Keine Live-Hotfixes existieren nur auf Zielhosts (alle Aenderungen im Repo).
- ✅ 1657 Unit-Tests gruen, Release-Workflow-Versions-Drift repariert.

No-Go:

- Kein neuer Feature-Slice, solange Version, Artefakte oder Pflichtdienste rot
  sind.

Kanonische Detailquellen:

- `docs/lasthope/02-execution-order.md` Welle 0
- `docs/checklists/05-release-operations.md`
- `docs/refactor/06-next-steps.md`

## Phase D1 - R1 Single-Host beweisen

Ziel: Ein leerer Host wird ohne Entwicklerintervention zu einem nutzbaren Beagle
OS Server.

Abnahme:

- Installation aus Release-ISO oder installimage auf leerem Host.
- Erstes Login in der Web Console ohne manuelle Reparatur.
- `scripts/check-beagle-host.sh` meldet PASS.
- Neue VM entsteht aus der WebUI und erreicht `ready`.
- Delete/Recreate derselben VM hinterlaesst keinen stale Runtime-State.
- Installations-Runbook ist mit echtem Befund validiert.

No-Go:

- Kein Firmenpilot, solange Clean-Install oder VM-Lifecycle nur durch manuelle
  SSH-Hotfixes funktioniert.

Kanonische Detailquellen:

- `docs/lasthope/01-enterprise-gap-list.md` P0
- `docs/runbooks/installation.md`
- `docs/checklists/05-release-operations.md` R1

## Phase D2 - BeagleStream als sichtbaren Produktpfad liefern

Ziel: Der Durchbruchsmoment fuer Nutzer: Thinclient einschalten, Desktop sehen.

Abnahme:

- `beagle-stream-server` ist in neuen VMs bevorzugter Runtime-Pfad.
- `beagle-stream-client` ist im Thinclient-Image bevorzugter Runtime-Pfad.
- Thinclient bootet echt, nicht nur im Mock.
- Enrollment schreibt Broker-/WireGuard-Zustand persistent.
- `/api/v1/streams/allocate` liefert ein explizites VM-Ziel.
- WireGuard ist aktiv, `vpn_required` blockiert ohne Tunnel.
- Desktop ist sichtbar ueber Broker/WireGuard.
- Keine PIN-Eingabe und kein Legacy-Direct-State im Standardpfad.
- Keine Tokens oder Secrets in Logs.

No-Go:

- Kein "Streaming erledigt", solange der Desktop nicht auf echter Hardware
  sichtbar ist.
- Kein Rueckfall auf manuelles Pairing als Produkterfolg.

Kanonische Detailquellen:

- `docs/checklists/02-streaming-endpoint.md`
- `fork.md`
- `docs/refactor/06-next-steps.md`

## Phase D3 - Datenrettung und Update-Vertrauen herstellen

Ziel: Betreiber koennen Fehler ueberleben.

Abnahme:

- Backup echter VM-Disk wird erstellt.
- Restore auf frischem oder zweitem Host bootet.
- Datenhash oder definierter Integritaetsnachweis stimmt.
- Update von Vorversion auf Zielversion laeuft aus Release-Artefakten.
- Rollback/Restore nach fehlerhaftem Update ist bewiesen.
- Backup-, Update- und Rollback-Runbooks sind validiert.

No-Go:

- Kein bezahlter Pilot mit produktiven Daten ohne nachgewiesenen Restore.

Kanonische Detailquellen:

- `docs/runbooks/backup-restore.md`
- `docs/runbooks/update.md`
- `docs/runbooks/rollback.md`
- `docs/checklists/01-platform.md`
- `docs/checklists/05-release-operations.md`

## Phase D4 - Zwei-Host-Pilot freischalten

Ziel: Beagle OS wird von "funktioniert auf einem Host" zu "betreibbare
Plattform".

Abnahme:

- `srv1` und `srv2` bilden einen healthy Cluster.
- Join, Drain und Maintenance sind in WebUI/API nachvollziehbar.
- HA/Fencing wird auf Hardware getestet.
- Session-Handover oder kontrollierter Reconnect ist messbar.
- WireGuard-Mesh-Latenz ist direct-vs-tunnel dokumentiert.
- Failover- und Handover-Ereignisse erscheinen im Audit.

No-Go:

- Kein bezahlter Pilot, solange Zwei-Host-Failover nur theoretisch oder nur per
  Unit-Test besteht.

Kanonische Detailquellen:

- `docs/checklists/01-platform.md`
- `docs/checklists/05-release-operations.md` R2
- `docs/lasthope/04-validation-matrix.md` E2

## Phase D5 - Security und Compliance marktreif machen

Ziel: Firmenvertrauen nicht behaupten, sondern belegen.

Abnahme:

- OIDC-ID-Token-Signaturpruefung inklusive JWKS, Issuer, Audience, Expiry und
  Key-Rotation ist umgesetzt.
- SCIM-Token-Rotation nutzt SecretStore.
- Debug-/Trace-Pfade koennen keine Secrets ausgeben.
- Externer Security-Review/Pentest ist abgeschlossen.
- Keine offenen Critical/High Findings.
- AVV/DSGVO-Pilotunterlagen, Incident-Runbook und Supportpfad sind fuer einen
  realen Pilotkunden nutzbar.

No-Go:

- Kein Produktionsangebot ohne externen Review.
- Keine still akzeptierten Security-Risiken ohne Eintrag in
  `docs/refactor/11-security-findings.md`.

Kanonische Detailquellen:

- `docs/checklists/03-security.md`
- `docs/refactor/11-security-findings.md`
- `docs/runbooks/incident-response.md`

## Phase D6 - Hardware- und Performance-Beweis

Ziel: Beagle OS wirkt nicht nur im Labor, sondern auf echter Zielhardware.

Abnahme:

- R3 Bare-Metal-Hardware ist definiert und dokumentiert.
- GPU/NVENC-Streaming-Session hat Latenz- und Qualitaetsmesswerte.
- VFIO-Konfiguration ueberlebt Host-Reboot.
- vGPU/MDEV wird nur mit echter Lizenz/Hardware als bestanden markiert.
- Mindesthardware und empfohlene Hardware sind in der Doku klar.

No-Go:

- Keine GPU-/vGPU-Versprechen im Produkttext ohne echte Hardware-Abnahme.

Kanonische Detailquellen:

- `docs/checklists/01-platform.md`
- `docs/checklists/05-release-operations.md` R3
- `docs/lasthope/01-enterprise-gap-list.md` P2

## Phase D7 - Produktpolitur und Launch-Paket

Ziel: Beagle OS ist fuer externe Nutzer verstaendlich, bedienbar und
kommunizierbar.

Abnahme:

- Standardpfad spricht konsequent von Beagle OS und BeagleStream.
- Legacy-Namen erscheinen nur als bewusst dokumentierter Fallback.
- WebUI hat Loading-, Empty- und Error-States in zentralen Panels.
- i18n-Restmodule sind migriert.
- Mobile/Tablet-Bedienung besteht definierte Lighthouse-/Accessibility-Gates.
- Download-, Lizenz-, Support- und Kontaktpfade sind widerspruchsfrei.
- Pilot-Angebot ist klar von produktivem Enterprise-Angebot getrennt.

No-Go:

- Keine breite Oeffentlichkeitskampagne, solange der erste externe
  Installationspfad nicht ohne Entwicklerkontext funktioniert.

Kanonische Detailquellen:

- `docs/checklists/04-quality-ci.md`
- `docs/lasthope/03-commercial-readiness.md`
- `public-site/`

## Diamond-Gates

| Gate | Freigabe | Muss bestanden sein |
|---|---|---|
| D0 | Weiterentwicklung auf stabiler Basis | Runtime/Version/Artefakte konsistent |
| D1 | technischer Single-Host-Pilot intern | Clean-Install + VM ready |
| D2 | Produktdemo | echter Thinclient zeigt BeagleStream-Desktop |
| D3 | Pilot mit Testdaten | Backup/Restore + Update/Rollback |
| D4 | bezahlter Pilot | Zwei-Host-Cluster + Failover/Handover |
| D5 | Firmenangebot | Security-Review ohne Critical/High |
| D6 | Hardware-Angebot | R3/GPU/VFIO-Nachweise |
| D7 | Launch | Runbooks, Support, UX, Website konsistent |

## Arbeitsregeln bis Diamond State

1. Jede abgeschlossene Phase erzeugt einen reproduzierbaren Nachweis im Repo,
   Runbook, Checklisten-Status oder Progress-Log.
2. Jeder Live-Hotfix wird noch im selben Arbeitsblock ins Repo zurueckgefuehrt.
3. Mock-, Unit- und Integrationstests zaehlen nur als Vorbereitung; Gates mit
   Hardware-/Runtime-Bezug brauchen echte Host-Nachweise.
4. Ein rotes P0-Gate blockiert Komfortfeatures.
5. Security-Funde werden sofort gefixt oder in
   `docs/refactor/11-security-findings.md` mit Risiko und naechstem Schritt
   dokumentiert.
6. Kein Feature gilt als produktreif, solange Installation, Betrieb, Fehlerfall
   und Rueckweg nicht dokumentiert sind.

## Durchbruchskriterium

Der Durchbruch ist erreicht, wenn eine externe Person mit bereitgestellter
Hardware und verlinkten Artefakten innerhalb eines begleiteten Pilotfensters
Beagle OS installiert, eine VM bereitstellt, einen Thinclient startet, den
Desktop nutzt, ein Backup restored und ein Update/Rollback durchfuehrt, ohne
dass ein Entwickler per SSH produktive Hotfixes einspielen muss.

