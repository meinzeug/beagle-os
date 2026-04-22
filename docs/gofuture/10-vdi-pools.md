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
- [ ] Template-Builder: Snapshot → Sysprep/cloud-init → sealed Backing-Image.

Umgesetzt (2026-04-22, Teil 1/2):
- Neues Core-Modul `core/virtualization/desktop_template.py` erstellt.
- Provider-neutrales `DesktopTemplate`-Protocol eingefuehrt (build/get/list/delete).
- Dataclass-Typen `DesktopTemplateBuildSpec` und `DesktopTemplateInfo` ergaenzt
	(Template-ID, Source-VM, Snapshot, Backing-Image, CPU/RAM, Software-Metadaten).
- Unit-Test `tests/unit/test_desktop_template_contract.py` hinzugefuegt (2/2 gruen).
- srv1-Smoke erfolgreich: Modul nach `/opt/beagle/core/virtualization/desktop_template.py` deployt,
	Import/Instanziierung per `python3` verifiziert.

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

- [ ] `core/virtualization/desktop_pool.py` anlegen.
- [ ] `beagle-host/services/pool_manager.py` implementiert Pool-Lifecycle: provisioning, scaling, recycling.

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

- [ ] `DesktopPool.mode` Enum: `floating_non_persistent | floating_persistent | dedicated`.
- [ ] Pool-Manager implementiert alle drei Modi korrekt.

Floating-Non-Persistent ist das klassische VDI-Modell: Jeder Nutzer bekommt einen
freien Desktop aus dem Pool; beim Logout wird der Desktop auf den Template-Stand
zurückgesetzt (Linked Clone vom Snapshot). Floating-Persistent: Nutzer bekommt
beim ersten Login einen Desktop zugewiesen, beim nächsten Login denselben Desktop.
Dedicated: Jeder Nutzer hat exklusiv eine eigene VM die dauerhaft läuft. Das Modi-
Modell muss bei Pool-Erstellung festgelegt werden; eine nachträgliche Änderung
ist nur mit explizitem Datenverlust-Hinweis erlaubt.

---

### Schritt 4 — Entitlements (User/Gruppe → Pool) implementieren

- [ ] `beagle-host/services/entitlement_service.py` anlegen.
- [ ] API: `POST /api/v1/pools/{pool}/entitlements` mit User-ID oder Gruppe.

Entitlements steuern wer auf welchen Pool zugreifen darf. Ein User ohne
Entitlement für einen Pool sieht diesen Pool in seiner Session-Auswahl nicht.
Entitlements können per User oder per Gruppe (LDAP-Gruppe, SCIM-Gruppe) gesetzt werden.
Die Gruppen-basierte Entitlement-Vergabe ist besonders effiziell für große Nutziezahlen.
Der Entitlement-Service prüft bei jedem Session-Request ob der anfragende User
einen gültigen Entitlement für den angefragten Pool hat.

---

### Schritt 5 — Pool-Wizard in Web Console

- [ ] Mehrschrittiger Pool-Wizard: Template auswählen → Pool-Größe → Modus → Entitlements → Bestätigung.
- [ ] Pool-Übersicht: Status jeder VM im Pool (free, in-use, recycling, error).

Der Pool-Wizard macht das Anlegen eines neuen Desktop-Pools für Betreiber
ohne Config-File-Kenntnisse zugänglich. Schritt 1: Verfügbare Templates aus dem
Template-Storage laden und darstelllen. Schritt 2: Pool-Name, CPU/RAM pro Desktop,
Min/Max-Pool-Größe. Schritt 3: Modus wählen. Schritt 4: Entitlements per User-/Gruppen-
Multiselect. Schritt 5: Zusammenfassung und Bestätigung. Nach Bestätigung startet
der Pool-Manager asynchron die ersten VMs und zeigt Progress in der Pool-Übersicht.

---

### Schritt 6 — Template-Builder in Web Console

- [ ] "Neue VM als Template konvertieren"-Aktion in der VM-Detailansicht.
- [ ] Builder-Status-Dialog zeigt Sysprep/Seal-Fortschritt.

Betreiber sollen Templates direkt aus der Web Console heraus erstellen können
ohne CLI-Befehle ausführen zu müssen. Der Template-Builder-Dialog erscheint wenn
der Betreiber eine gestoppte VM als Template markiert. Er wählt dann einen
Template-Namen, eine Beschreibung und ob Sysprep/cloud-init Seal ausgeführt werden soll.
Nach Bestätigung läuft der Builder-Prozess asynchron mit Progress-Anzeige.
Das fertige Template erscheint in der Template-Bibliothek und kann sofort für neue Pools
verwendet werden.

---

## Testpflicht nach Abschluss

- [ ] Pool von 5 Floating-Non-Persistent-VMs erstellen, alle starten, User bekommt freie VM.
- [ ] Logout recycelt VM (reset auf Template-Stand) innerhalb von 60 Sekunden.
- [ ] Persistent-Pool: User bekommt bei zweitem Login dieselbe VM.
- [ ] Template-Builder: Golden-Image → Template → Pool ohne Fehler.
- [ ] Entitlement: User ohne Entitlement sieht Pool nicht.
