# 05 — Provider-Abstraction + Proxmox dauerhaft entfernen

Stand: 2026-04-20 (Status 2026-04-29: vollstaendig erledigt — siehe `docs/MASTER-PLAN.md` Abschnitt 4)
Priorität: Welle 6.x (April–Mai 2026)
Betroffene Verzeichnisse: `core/`, `providers/`, `beagle-host/providers/`, `proxmox-ui/` (entfernt)
Referenz: `docs/refactor/09-provider-abstraction.md`

---

## Hintergrund

Proxmox wird dauerhaft aus dem Repo entfernt. Es gibt keine Variante
"Beagle OS with Proxmox" mehr. Der einzige aktive Provider ist `providers/beagle/`
(libvirt/KVM). `providers/proxmox/` und `proxmox-ui/` werden nach vollständiger
Migration gelöscht. Provider-Seams existieren bereits in `beagle-host/providers/`
und `providers/`. Ziel dieses Plans ist es, alle verbleibenden Proxmox-Direktaufrufe
in den Beagle-Provider zu migrieren und die Proxmox-Verzeichnisse danach vollständig
zu löschen.

Achtung: `beagle-host/` (die aktive Control-Plane) und `beagle-host/providers/`
(Provider-Contract) bleiben bestehen und werden ausgebaut. Nur Proxmox geht weg.

---

## Schritte

### Schritt 1 — Provider-Contract in `core/` vollständig definieren

- [x] Beagle-Host-Contract geprüft und ergänzt: `beagle-host/providers/host_provider_contract.py` enthält jetzt Snapshot/Clone/Console-Proxy/VNC-Token-fähige Methoden.
- [x] Fehlende Methoden ergänzt (`snapshot_vm`, `clone_vm`, `get_console_proxy`) und in Providern implementiert.

Das Contract-Interface in `core/` definiert was jeder Provider implementieren muss.
Wenn das Interface unvollständig ist werden Provider-Autoren gezwungen undokumentierte
Methoden direkt aufzurufen. Jede Methode im Contract braucht einen Docstring mit
Input-/Output-Typen und erlaubten Fehlern. Das Python-Protokoll (`typing.Protocol`)
oder eine abstrakte Basisklasse (`abc.ABC`) sind geeignete Implementierungsformen.
Dieser Schritt muss vor jedem neuen Provider-Code abgeschlossen sein.

---

### Schritt 2 — Alle Proxmox-Direktaufrufe im Repo identifizieren und in Beagle-Provider migrieren

- [x] `grep -r "qm\|pvesh\|/api2/json\|PVEAuthCookie" beagle-host/ --include="*.py"` ausführen.
- [x] Jeden Fund als Methode im Beagle-Provider (`providers/beagle/`) neu implementieren, Service auf Interface-Aufruf umschreiben.

Dieser Grep-Lauf ist der schnellste Weg die aktuelle Verletzungslage zu erfassen.
Jeder Fund ist ein Architekturverstoß der behoben werden muss — die Proxmox-Aufrufe
werden nicht in `providers/proxmox/` bewahrt, sondern durch Beagle-Provider-Methoden
(libvirt/KVM) ersetzt. Der Fix-Pfad: Contract-Interface erweitern, Beagle-Provider
implementieren, Service auf Interface-Aufruf umschreiben. Alle Funde werden in
`docs/refactor/09-provider-abstraction.md` dokumentiert. Nach der Migration wird
der Grep nochmals ausgeführt und muss 0 Treffer liefern.

> Umsetzung 2026-04-21: Dead-Code-Pfade entfernt — `VmConsoleAccessService` Proxmox-Console-Access-Logik (Zeilen 258–274), `_legacy_ui_port()` Methode und `legacy_ui_ports_raw` Parameter aus beiden Services entfernt. `LEGACY_UI_PORTS_RAW` aus `beagle-control-plane.py` entfernt. Syntax check lokal erfolgreich, Smoke-Tests auf `srv1.beagle-os.com` alle 13/13 bestanden. Grep-Endstand: 0 Treffer für direkte Proxmox-API-Aufrufe (qm, pvesh, /api2/json, PVEAuthCookie).

---

### Schritt 3 — Beagle-nativen Provider (`providers/beagle/`) ausbauen

- [x] Beagle-Provider implementiert alle Contract-Methoden über libvirt/QEMU/KVM.
- [x] Fehlende Methoden ergänzt (Snapshot, Clone, Console-Proxy via VNC/noVNC-Pattern).

Der Beagle-eigene Provider wird die primäre Implementierung wenn Beagle OS standalone
läuft ohne Proxmox. Libvirt bietet über `libvirt-python` eine stabile API für
VM-Lifecycle, Storage-Pool-Operationen und Netzwerkverwaltung. Console-Proxy über
VNC/SPICE wird über das bestehende `beagle-novnc-proxy`-Pattern realisiert.
Snapshot und Clone sind in libvirt mit Domain-Snapshots (`virDomainSnapshotCreateXML`)
implementierbar. Der Beagle-Provider muss dasselbe Contract-Interface wie der
frueher vorhandene Proxmox-Provider implementieren damit Services ohne Anpassung zwischen Providern wechseln koennen.

---

### Schritt 4 — Provider-Registry vereinfachen: nur noch `beagle`-Provider

- [x] beagle-control-plane.py: BEAGLE_HOST_PROVIDER default von "proxmox" auf "beagle" geändert.
- [x] `beagle-host/providers/registry.py` angepasst: nur noch `providers/beagle/` wird geladen, Legacy-Keys (`proxmox`, `pve`) normalisieren auf `beagle`.
- [x] Config-Key `BEAGLE_HOST_PROVIDER` effektiv auf `beagle` eingeschränkt (Legacy-Werte werden auf `beagle` gemappt).

Da es nur noch einen Provider gibt wird die Registry maximal einfach: sie instanziiert
den Beagle-Provider und gibt ihn zurück. Kein dynamisches Laden, kein Proxmox-Zweig.
Services sprechen ausschließlich gegen das Contract-Interface in `core/` und wissen
nichts von libvirt oder KVM-Details. Beim Start des Control Planes wird der Provider
instanziiert und auf Verfügbarkeit geprüft (libvirt-Socket erreichbar). Tests können
mit einem Mock-Provider laufen der das Interface implementiert ohne echte Systemaufrufe.

---

### Schritt 5a — Provider-neutrale Tests schreiben

- [x] Für jeden Service in `beagle-host/services/` mindestens einen Unit-Test mit Mock-Provider anlegen.
- [x] `tests/unit/` Verzeichnis anlegen falls nicht vorhanden.

Ohne Tests ist nicht verifizierbar ob der Refactoring-Schritt das Verhalten erhalten hat.
Mock-Provider implementieren das Contract-Interface mit vorprogrammierten Antworten
statt echte Systemaufrufe zu machen. Das erlaubt Tests in CI ohne Proxmox- oder
libvirt-Setup. Jeder Service-Test prüft Happy-Path und mindestens einen Error-Path.
Der CI-Lauf muss mindestens `pytest tests/unit/` erfolgreich ausführen können.

---

### Schritt 5b — `providers/proxmox/` und `proxmox-ui/` dauerhaft löschen

- [x] Nach erfolgreicher Beagle-Provider-Verifikation: `rm -rf providers/proxmox/`.
- [x] `rm -rf proxmox-ui/`.
- [x] Alle Referenzen in `scripts/`, CI-Konfiguration und Dokumentation entfernen.
- [x] `git commit` mit Message: "chore: permanently remove providers/proxmox/ and proxmox-ui/".

Das Löschen ist ein einmaliger, irreversibler Schritt und muss erst dann ausgeführt
werden wenn alle Funktionen des Proxmox-Providers im Beagle-Provider reimplementiert
sind und die Tests grün sind. Vor dem Löschen muss ein finaler Grep bestätigen dass
keine Referenz auf `providers/proxmox/` oder `proxmox-ui/` in aktiv genutztem Code
verbleibt. Referenzen in reinen Kommentaren oder Migrations-Dokumenten dürfen bestehen
bleiben. Nach dem Commit wird `docs/refactor/09-provider-abstraction.md` mit dem
Löschdatum und dem Verifikationsergebnis aktualisiert.

---

### Schritt 6 — Provider-Abstraction in Dokumentation festschreiben

- [x] `docs/refactor/09-provider-abstraction.md` mit aktuellem Stand aktualisieren.
- [x] Begründung für jede neue Provider-Kopplung die nicht vermeidbar war dokumentieren.

Die Dokumentation muss den aktuellen Ist-Stand widerspiegeln nicht den geplanten Soll-Stand.
Neue Direktkopplungen die aus technischen Gründen kurzfristig notwendig waren
werden mit Begründung, Risiko und Migrations-Ticket dokumentiert. Ein Agent der dieses
Dokument liest muss in 5 Minuten verstehen wo Provider-Grenzen verlaufen. Die Regel
"Neue direkte Provider-Kopplung nur mit Eintrag in 09-provider-abstraction.md" aus
`AGENTS.md` wird damit durchsetzbar.

---

## Testpflicht nach Abschluss

- [x] `grep -r "qm\|pvesh\|/api2/json\|PVEAuthCookie" . --include="*.py" --include="*.js"` → 0 Treffer.
- [x] `providers/proxmox/` und `proxmox-ui/` existieren nicht mehr im Repo.
- [x] Beagle-Provider alle Contract-Methoden implementiert (kein `NotImplementedError`).
- [x] `pytest tests/unit/` grün.
- [x] `beagle-control-plane.py` startet ohne Fehler.
