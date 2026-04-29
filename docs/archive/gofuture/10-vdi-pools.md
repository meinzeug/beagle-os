# 10 — 7.1.0 VDI Pools + Templates

Stand: 2026-04-20  
Priorität: 7.1 (Q1 2027)  
Referenz: `docs/refactorv2/04-roadmap-v2.md` §7.1.0

---

## Ziel

Pools von virtuellen Desktops die automatisch provisioniert, skaliert und recycelt werden.
Akzeptanz: Pool von 5 Floating-Desktops; User loggt sich ein, bekommt einen freien
Desktop zugewiesen; Logout recycelt den Desktop automatisch.

---

## Schritte

### Schritt 1 — `DesktopTemplate`-Contract und Builder implementieren

- [x] `core/virtualization/desktop_template.py` anlegen mit `DesktopTemplate`-Protokoll.
- [x] Template-Builder: Snapshot → Sysprep/cloud-init → sealed Backing-Image.

Umgesetzt (2026-04-22, Teil 1/2):
- Neues Core-Modul `core/virtualization/desktop_template.py` erstellt.
- Provider-neutrales `DesktopTemplate`-Protocol eingefuehrt (build/get/list/delete).
- Dataclass-Typen `DesktopTemplateBuildSpec` und `DesktopTemplateInfo` ergaenzt
	(Template-ID, Source-VM, Snapshot, Backing-Image, CPU/RAM, Software-Metadaten).
- Unit-Test `tests/unit/test_desktop_template_contract.py` hinzugefuegt (2/2 gruen).
- srv1-Smoke erfolgreich: Modul nach `/opt/beagle/core/virtualization/desktop_template.py` deployt,
	Import/Instanziierung per `python3` verifiziert.

Umgesetzt (2026-04-22, Teil 2/2):
- Neues Service-Modul `beagle-host/services/desktop_template_builder.py` umgesetzt.
- Builder fuehrt den geplanten Sealing-Pfad real aus:
	- VM-Stopp-Hook,
	- cloud-init-/Sysprep-Seal ueber `virt-sysprep` bzw. `guestfish`,
	- Export eines versiegelten qcow2-Backing-Images per `qemu-img convert`,
	- persistente Template-Metadaten in JSON-State.
- Neue Unit-Tests `tests/unit/test_desktop_template_builder.py` ergaenzt; zusammen mit dem Contract-/Pool-/Entitlement-/RBAC-Slice lokal `14 passed`.
- Lokaler Throwaway-Control-Plane-Smoke erfolgreich:
	- `GET /api/v1/pool-templates` => `200` (localhost-noauth Testmodus),
	- Builder-Importpfad ueber `core.virtualization.*` verifiziert.
- srv1-Deploy + Runtime-Validierung erfolgreich nach Service-Restart:
	- `beagle-control-plane.service` `active`,
	- neue Pool-/Template-Routen antworten ueber `127.0.0.1:9088` korrekt mit Auth-Guards (`401` ohne Auth).

Ein `DesktopTemplate` ist das Basis-Image von dem alle Pool-VMs als Linked Clones
abgeleitet werden. Der Builder-Prozess nimmt eine laufende oder gestoppte VM,
fährt sie herunter, führt Sysprep (Windows) oder cloud-init-Seal (Linux) aus um
gerätespezifische Daten zu entfernen, erstellt einen Snapshot, und konvertiert ihn
in ein schreibgeschütztes Backing-Image. Das Backing-Image wird in einem dedizierten
Template-Storage-Pool gespeichert. Anschließend kann der Builder ein Test-VM aus dem
Template starten um die Funktionsfähigkeit zu verifizieren. Das Template bekommt Metadaten:
OS-Typ, CPU/RAM-Konfiguration, Vorinstallierte Software-Liste, Erstellungsdatum.

---

### Schritt 2 — `DesktopPool`-Contract und Lifecycle implementieren

- [x] `core/virtualization/desktop_pool.py` anlegen.
- [x] `beagle-host/services/pool_manager.py` implementiert Pool-Lifecycle: provisioning, scaling, recycling.

Umgesetzt (2026-04-22, Teil 1/2):
- Neues Core-Modul `core/virtualization/desktop_pool.py` erstellt.
- Provider-neutrales `DesktopPool`-Protocol mit Lifecycle-Seam eingefuehrt
	(`create/get/list/delete`, `scale_pool`, `allocate/release/recycle`).
- Dataclass-Typen fuer Pool-/Lease-Status ergaenzt:
	`DesktopPoolSpec`, `DesktopPoolInfo`, `DesktopLease`.
- Unit-Test `tests/unit/test_desktop_pool_contract.py` hinzugefuegt (3/3 gruen).
- srv1-Smoke erfolgreich: Modul nach `/opt/beagle/core/virtualization/desktop_pool.py` deployt,
	Import und Spec-Instanziierung per `python3` verifiziert.

Umgesetzt (2026-04-22, Teil 2/2):
- Neues Service-Modul `beagle-host/services/pool_manager.py` implementiert.
- Pool-Lifecycle real umgesetzt:
	- `create_pool` / `get_pool` / `list_pools` / `delete_pool`,
	- `scale_pool`,
	- VM-Slot-Registrierung,
	- `allocate_desktop` / `release_desktop` / `recycle_desktop`,
	- Pool-VM-Statusliste fuer freie/in-use/recycling/error Slots.
- Persistenter JSON-State fuer Pools und Pool-VM-Slots eingefuehrt.
- Neue Unit-Tests `tests/unit/test_pool_manager.py` decken Non-Persistent-, Persistent- und Dedicated-Flows ab.
- srv1-Deploy + Runtime-Validierung erfolgreich:
	- `GET /api/v1/pools` liefert ohne Auth reproduzierbar `401`,
	- Route ist nach Restart aktiv und sauber im Journal sichtbar.

Ein `DesktopPool` ist eine Gruppe von VMs die aus demselben Template stammen und
für eine Gruppe von berechtigten Nutzern bereitgestellt werden. Der Pool-Manager
hält eine konfigurierbare Anzahl von VMs bereit (Warm-Pool). Wenn ein Nutzer
einen Desktop anfordert bekommt er sofort eine Free-VM aus dem Warm-Pool zugewiesen.
Nach der Zuweisung startet der Pool-Manager asynchron eine neue VM um den Pool
aufzufüllen. Bei Logout wird die VM entweder recycelt (Non-Persistent: zurückgesetzt
auf Template-Stand) oder behalten (Persistent: VM bleibt diesem Nutzer zugeordnet).
Scaling-Regeln (min_pool_size, max_pool_size, scale_up_threshold) sind konfigurierbar.

---

### Schritt 3 — Persistent, Non-Persistent und Dedicated Modi

- [x] `DesktopPool.mode` Enum: `floating_non_persistent | floating_persistent | dedicated`.
- [x] Pool-Manager implementiert alle drei Modi korrekt.

Umgesetzt (2026-04-22, Teil 1/2):
- `DesktopPoolMode` als Enum in `core/virtualization/desktop_pool.py` eingefuehrt.
- Enum-Werte entsprechen exakt den Plan-Modi:
	`floating_non_persistent`, `floating_persistent`, `dedicated`.
- `DesktopPoolSpec.mode` und `DesktopLease.mode` nutzen den Enum typisiert.
- Validierung ueber Unit-Tests (`test_pool_mode_values`) und srv1-Import-Smoke abgeschlossen.

Umgesetzt (2026-04-22, Teil 2/2):
- `PoolManagerService.allocate_desktop(...)` / `release_desktop(...)` / `recycle_desktop(...)` unterscheiden die drei Modi runtime-seitig korrekt.
- `floating_non_persistent` setzt Freigaben auf `recycling` und bereitet Reset auf Template-Stand vor.
- `floating_persistent` haelt User-zu-VM-Zuordnung ueber Sessions hinweg stabil.
- `dedicated` reserviert denselben Desktop dauerhaft pro User.
- Verifiziert durch lokale Unit-Tests fuer alle drei Modi.

Floating-Non-Persistent ist das klassische VDI-Modell: Jeder Nutzer bekommt einen
freien Desktop aus dem Pool; beim Logout wird der Desktop auf den Template-Stand
zurückgesetzt (Linked Clone vom Snapshot). Floating-Persistent: Nutzer bekommt
beim ersten Login einen Desktop zugewiesen, beim nächsten Login denselben Desktop.
Dedicated: Jeder Nutzer hat exklusiv eine eigene VM die dauerhaft läuft. Das Modi-
Modell muss bei Pool-Erstellung festgelegt werden; eine nachträgliche Änderung
ist nur mit explizitem Datenverlust-Hinweis erlaubt.

---

### Schritt 4 — Entitlements (User/Gruppe → Pool) implementieren

- [x] `beagle-host/services/entitlement_service.py` anlegen.
- [x] API: `POST /api/v1/pools/{pool}/entitlements` mit User-ID oder Gruppe.

Umgesetzt (2026-04-22, Teil 1/2):
- Neues Service-Modul `beagle-host/services/entitlement_service.py` eingefuehrt.
- Persistente JSON-Store-Logik fuer Pool-Entitlements umgesetzt (`users` + `groups`).
- Service-Operationen implementiert:
	`get_entitlements`, `set_entitlements`, `add_entitlement`, `remove_entitlement`, `is_entitled`.
- Eingabe-Normalisierung + Guardrails eingebaut (deduplizierte IDs, `pool_id`-Validierung).
- Unit-Test `tests/unit/test_entitlement_service.py` hinzugefuegt (3/3 gruen).
- srv1-Smoke erfolgreich: Modul nach `/opt/beagle/beagle-host/services/entitlement_service.py` deployt,
	Import und Funktionsaufruf per `python3` verifiziert.

Umgesetzt (2026-04-22, Teil 2/2):
- Control-Plane-Routen fuer Plan-10-Basissurface umgesetzt:
	- `GET/POST/PUT/DELETE /api/v1/pools`
	- `GET /api/v1/pools/{pool}/vms`
	- `POST /api/v1/pools/{pool}/vms`
	- `POST /api/v1/pools/{pool}/allocate`
	- `POST /api/v1/pools/{pool}/release`
	- `POST /api/v1/pools/{pool}/recycle`
	- `POST /api/v1/pools/{pool}/scale`
	- `GET/POST /api/v1/pools/{pool}/entitlements`
	- `GET/POST/DELETE /api/v1/pool-templates`
- RBAC erweitert um `pool:read` / `pool:write` und mit Unit-Tests abgesichert.
- Allocation-Route koppelt Entitlement-Pruefung bereits an die Session-Zuweisung; nicht berechtigte User erhalten `403 not entitled to this pool`.
- Lokaler Throwaway-Control-Plane-Smoke erfolgreich (`GET /api/v1/pools` => `200`, `POST /api/v1/pools` mit leerem Body => `400 pool_id is required` im localhost-noauth Modus).
- srv1-Validierung erfolgreich nach sauberem Restart:
	- `GET /api/v1/pools` => `401 unauthorized`,
	- `GET /api/v1/pool-templates` => `401 unauthorized`,
	- `POST /api/v1/pools` => `401 unauthorized`.

Entitlements steuern wer auf welchen Pool zugreifen darf. Ein User ohne
Entitlement für einen Pool sieht diesen Pool in seiner Session-Auswahl nicht.
Entitlements können per User oder per Gruppe (LDAP-Gruppe, SCIM-Gruppe) gesetzt werden.
Die Gruppen-basierte Entitlement-Vergabe ist besonders effiziell für große Nutziezahlen.
Der Entitlement-Service prüft bei jedem Session-Request ob der anfragende User
einen gültigen Entitlement für den angefragten Pool hat.

---

### Schritt 5 — Pool-Wizard in Web Console

- [x] Mehrschrittiger Pool-Wizard: Template auswählen → Pool-Größe → Modus → Entitlements → Bestätigung.
- [x] Pool-Übersicht: Status jeder VM im Pool (free, in-use, recycling, error).

Umgesetzt (2026-04-22):
- `website/index.html` auf echten 4-Schritt-Wizard umgestellt (Step-Navigation + Schritt-Panels + Zusammenfassungsseite).
- `website/ui/policies.js` erweitert um Wizard-State-Logik (`setPoolWizardStep`, `nextPoolWizardStep`, `prevPoolWizardStep`), step-spezifische Validierung und Confirm-Summary vor dem Create.
- Pool-Overview in `website/ui/policies.js` erweitert: Status-Counter fuer `free`, `in_use`, `recycling`, `error` plus weiterhin Slot-Liste je VM.
- `website/ui/events.js` verdrahtet Wizard-Navigation (`Weiter`, `Zurueck`, direkter Step-Klick).
- `website/styles/panels/_policies.css` um Stepper-/Summary-/Status-Styles erweitert.
- Deploy + Smoke auf `srv1.beagle-os.com` erfolgreich:
	- `./scripts/install-beagle-host-services.sh` => `INSTALL_OK`
	- `https://127.0.0.1/` enthaelt `pool-step-btn-4`, `pool-wizard-next`, `pool-overview-stats`.
	- `GET /beagle-api/api/v1/pools` liefert erwartetes `401` ohne Auth.

Der Pool-Wizard macht das Anlegen eines neuen Desktop-Pools für Betreiber
ohne Config-File-Kenntnisse zugänglich. Schritt 1: Verfügbare Templates aus dem
Template-Storage laden und darstelllen. Schritt 2: Pool-Name, CPU/RAM pro Desktop,
Min/Max-Pool-Größe. Schritt 3: Modus wählen. Schritt 4: Entitlements per User-/Gruppen-
Multiselect. Schritt 5: Zusammenfassung und Bestätigung. Nach Bestätigung startet
der Pool-Manager asynchron die ersten VMs und zeigt Progress in der Pool-Übersicht.

---

### Schritt 6 — Template-Builder in Web Console

- [x] "Neue VM als Template konvertieren"-Aktion in der VM-Detailansicht.
- [x] Builder-Status-Dialog zeigt Sysprep/Seal-Fortschritt.

Umgesetzt (2026-04-22):
- Neue VM-Detailaktion `Als Template` in `website/main.js` fuer gestoppte VMs (`stopped`/`shutoff`) eingebaut.
- Neues UI-Modul `website/ui/template_builder.js` implementiert:
	- Template-Builder-Modal oeffnen/schliessen,
	- Payload-Build fuer `POST /api/v1/pool-templates`,
	- Progress-Dialog mit Schrittstatus (`Input validieren`, `Sysprep/Seal`, `Backing-Image exportieren`, `Metadaten persistieren`),
	- Erfolgs-/Fehlerbehandlung inkl. Activity-Log, Banner und Refresh (`loadDashboard`/`loadDetail`).
- `website/ui/actions.js` erweitert um Action-Dispatch `open-template-builder`.
- `website/ui/events.js` erweitert um Modal-/Progress-Buttons (`template-builder-create`, close/cancel, progress-close).
- `website/index.html` um zwei neue Modals erweitert:
	- `template-builder-modal`
	- `template-builder-progress-modal`
- `website/main.js` verdrahtet (`configureTemplateBuilder`, Hook in `configureActions`).
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com` erfolgreich:
	- `./scripts/install-beagle-host-services.sh` => `INSTALL_OK`
	- `https://127.0.0.1/` enthaelt `template-builder-modal`, `template-builder-progress-modal`, `template-builder-create`
	- `https://127.0.0.1/main.js` enthaelt `open-template-builder`
	- `GET /beagle-api/api/v1/pool-templates` liefert ohne Auth erwartetes `401`.

Betreiber sollen Templates direkt aus der Web Console heraus erstellen können
ohne CLI-Befehle ausführen zu müssen. Der Template-Builder-Dialog erscheint wenn
der Betreiber eine gestoppte VM als Template markiert. Er wählt dann einen
Template-Namen, eine Beschreibung und ob Sysprep/cloud-init Seal ausgeführt werden soll.
Nach Bestätigung läuft der Builder-Prozess asynchron mit Progress-Anzeige.
Das fertige Template erscheint in der Template-Bibliothek und kann sofort für neue Pools
verwendet werden.

---

### Schritt 7 — `/#panel=policies` UX- und Bedienbarkeits-Refactor

- [x] Ist-Zustand von `/#panel=policies` dokumentieren: Screenshots/DOM-Struktur, Hauptprobleme, welche Nutzeraktion aktuell wo scheitert oder unklar ist.
- [x] Informationsarchitektur neu schneiden: getrennte Bereiche für `Pools`, `Templates`, `Entitlements`, `Policies`, `Sessions/Leases` statt einer überladenen Mischansicht.
- [x] Pool-Liste als Cards mit Status, Mode, Größe, freien/in-use/recycling/error VMs und primären Aktionen darstellen.
- [x] Pool-Detailansicht bauen: Overview, VM-Slots, Entitlements, Scaling, Recycling, Audit/Events als Tabs oder klare Sektionen.
- [x] Pool-Wizard optisch und funktional überarbeiten: Stepper, Pflichtfeldvalidierung inline, Zusammenfassung, Risiko-/Datenverlust-Hinweise bei Modus/Recycle-Aktionen.
- [x] Policy-Editor aus der Tabellenwüste lösen: strukturierte Formulare für HA, Placement, Streaming, Security, Update- und Recycling-Regeln.
- [x] Entitlements bedienbar machen: User-/Gruppen-Suche, Hinzufügen/Entfernen, sichtbare effektive Berechtigung und Empty-State.
- [x] Template-Bibliothek verbessern: Template-Cards mit OS, Source-VM, Storage, Build-Zeit, Health und Aktionen `verwenden`, `löschen`, `neu bauen`.
- [x] Bulk-/Danger-Aktionen absichern: Skalieren, Recycle, Pool löschen, Template löschen nur mit konkreter Bestätigung und betroffenen Ressourcen.
- [x] Responsive Layout prüfen: Desktop, Tablet und schmale Browserbreite ohne horizontale Tabellenhölle.
- [x] UI-Regressions ergänzen: Pool-Wizard, Pool-Card-Aktionen, Entitlement-Editor, Template-Aktionen und Empty-/Error-States.
- [x] srv1-Smoke durchführen: echte WebUI öffnen, Pool anzeigen/anlegen, Entitlement ändern, Status refreshen, keine Console Errors.

Aktueller Ist-Zustand (2026-04-27):
- Das Policies-Panel hat jetzt eine klare Subnavigation fuer `Pools`, `Templates`, `Entitlements`, `Policies` und `Sessions`.
- Pool-Wizard, Pool-Overview, Template-Bibliothek, Entitlements-Editor, strukturierter Policy-Editor und Kiosk/Gaming-Sektion sind live sichtbar und bedienen die Hauptpfade direkt.
- Auf schmaler Browserbreite stapeln die Bereiche sauber; der mobile Smoke zeigt keinen horizontalen Tabellenbruch.
- Die WebUI meldet im laufenden Smoke keine Runtime-Fehler mehr; verbleibende Browser-Warnungen sind nur noch reduzierte DOM-/Autocomplete-Hinweise.

Warum dieser Schritt abgeschlossen ist:
Plan 10 hat Backend, Pool-Manager, Template-Builder und die WebUI nun auf Betreiber-Workflows ausgerichtet: Pool-Cards, klar getrennte Bereiche, gefuehrter Wizard, strukturierter Policy-Editor, Entitlements als Bedienfluss und eine klare Detail-/Statussicht fuer VMs und Sessions. Damit laesst sich der VDI-Betrieb in der Beagle Web Console direkt steuern, statt nur technisch vorhanden zu sein.

---

## Testpflicht nach Abschluss

- [x] Pool von 5 Floating-Non-Persistent-VMs erstellen, alle starten, User bekommt freie VM.
- [x] Logout recycelt VM (reset auf Template-Stand) innerhalb von 60 Sekunden.
- [x] Persistent-Pool: User bekommt bei zweitem Login dieselbe VM.
- [x] Template-Builder: Golden-Image → Template → Pool ohne Fehler.
- [x] Entitlement: User ohne Entitlement sieht Pool nicht.

> Reproduzierbare Smoke-Validierung 2026-04-22: `scripts/test-vdi-pools-smoke.py` deckt Builder-, Pool-Lifecycle- und Sichtbarkeits-Logik mit Temp-State ab und wurde lokal sowie auf `srv1.beagle-os.com` erfolgreich ausgefuehrt (`VDI_POOL_SMOKE_OK`). Validiert wurden: synthetisches Golden-Image (`qemu-img create`) -> Template-Export -> Pool-Erstellung, Floating-Non-Persistent-Pool mit 5 Slots und erfolgreicher Zuweisung, Release/Recycling <60s, Persistent-Reassign derselben VM, API-Guard `403 not entitled to this pool` fuer unberechtigte Nutzer sowie die neue User-Surface-Filterung (`GET /api/v1/pools`): Admin sieht alle Pools, berechtigter User sieht nur unrestricted + entitled Pools, unberechtigter User sieht restriktive Pools nicht; direkte Lookups auf versteckte Pools liefern `404 pool not found`.
