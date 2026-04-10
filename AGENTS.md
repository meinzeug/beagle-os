# Beagle OS – Refactor & Architecture Agent Guide

## 🎯 Ziel

Dieses Repository (`meinzeug/beagle-os`) soll strukturell, technisch und architektonisch umfassend refactored werden, ohne die Produktidee zu verändern.

Beagle OS bleibt:

- Proxmox-native Endpoint-/Thin-Client-OS  
- Moonlight/Sunshine-Streaming-Plattform  
- Gaming-Kiosk (GeForce NOW etc.)  
- Host-Installer + Artifact-/Fleet-/Provisioning-System  

Langfristiger Nordstern:

- Beagle OS soll zu einem **eigenen Virtualisierungsprodukt** wachsen.
- Proxmox soll langfristig **nur noch einer von mehreren Providern** sein.
- Provider-Neutralitaet ist daher **Zwischenschritt**, nicht das Endziel.
- Die Architektur muss einen spaeteren **Beagle-eigenen Virtualisierungsstrang** ermoeglichen; externe Provider bleiben optional.

Architekturregel ab jetzt:

- Proxmox ist ein **temporärer erster Provider**, nicht das dauerhafte Architekturzentrum.
- Neue Architektur MUSS provider-neutral bleiben.
- Neue direkte Proxmox-Kopplung darf nur noch in klar benannten Provider-Schichten entstehen.

---

## ⚠️ Grundregeln

- Arbeite **schrittweise**, niemals Big-Bang.
- Jede Änderung muss:
  - den Build erhalten ODER verbessern
  - die Runtime nicht brechen
- Keine Kernfeatures zerstören:
  - Proxmox Host Install
  - Thin Client Install
  - Moonlight Runtime
  - Gaming Kiosk
  - Packaging / Release
  - Proxmox UI Integration
- Fokus:
  - Modularität
  - Wartbarkeit
  - Sicherheit
  - Testbarkeit
  - Provider-Neutralität

## 🧩 Provider-Prinzip (NEU, verbindlich)

- Neue Geschäftslogik darf **nicht** direkt an Proxmox-APIs, `qm`, `pvesh`, `/api2/json`, `PVE.*` oder Proxmox-Dateipfade gekoppelt werden.
- Stattdessen immer zuerst über generische Schichten arbeiten, z. B.:
  - `core/provider/`
  - `core/virtualization/`
  - `core/platform/`
  - `providers/proxmox/`
- Neue Abstraktionen muessen so geschnitten werden, dass spaeter auch ein **Beagle-eigener Provider** dieselben Vertraege implementieren kann.
- Proxmox-spezifische Implementierungen gehören nur in `providers/proxmox/` oder klar markierte Migrations-Shims.
- UI-Logik soll gegen generische Services/Contracts arbeiten, nicht gegen Proxmox direkt.
- Host-/Provisioning-/Inventory-Logik soll schrittweise auf dieselben provider-neutralen Verträge umgestellt werden.
- Browser-Extension-Code soll direkte Proxmox-Zugriffe nur noch in klaren Provider-Dateien wie `extension/providers/*` kapseln, nicht in `extension/content.js`.
- Browser-seitige Endpoint-/Profil-Synthese gehoert in dedizierte `state/*`- oder `services/*`-Module, nicht inline in Runtime-Einstiegspunkte wie `proxmox-ui/beagle-ui.js` oder `extension/content.js`.
- Browser-seitige Endpoint-Export-/Notes-/Formatter-Helfer, die bewusst in Proxmox UI und Extension gleich sind, gehoeren in gemeinsame Shared-Module wie `extension/shared/*`, nicht doppelt in `proxmox-ui/components/*` und `extension/services/*`.
- Groessere Browser-Extension-Renderer und Modal-Logik gehoeren nach `extension/components/*`, nicht zurueck in `extension/content.js`.
- Gemeinsame Proxmox-UI-Overlay-/Loading-/Modal-Shell-Logik gehoert in dedizierte `proxmox-ui/components/*`-Module wie `modal-shell.js`, nicht als Inline-CSS oder Inline-Loading-Markup zurueck in `proxmox-ui/beagle-ui.js`.
- Proxmox-UI-spezifische ExtJS-/Toolbar-/Menu-/Create-VM-Integration gehoert in dedizierte `proxmox-ui/components/*`-Module, nicht zurueck in `proxmox-ui/beagle-ui.js`.
- Host-seitige browser-/installer-facing Endpoint-Profile und oeffentliche Payload-Contracts gehoeren in dedizierte Contract-Module, nicht verteilt in mehrere Handler oder Hilfsfunktionen im Control-Plane-Monolithen.
- Die generische Host-/Control-Plane-Oberflaeche heisst im Repo `beagle-host/`, nicht `proxmox-host/`; provider-spezifische Logik bleibt darunter nur in `providers/*`.
- Host-Provider-Auswahl und Host-Provider-Contracts gehoeren in `beagle-host/providers/registry.py` und `beagle-host/providers/host_provider_contract.py`; `beagle-host/bin/beagle-control-plane.py` soll keine konkreten Provider-Klassen mehr direkt importieren.
- Host-seitige provider-gestuetzte Read-/Inventory-Helfer fuer VM-, Node-, Bridge-, Config- und Guest-IP-Abfragen gehoeren in `beagle-host/services/*`, nicht zurueck in `beagle-host/bin/beagle-control-plane.py`.
- Host-seitige VM-State-/Compliance-/Read-Model-Zusammenbau-Helfer gehoeren ebenfalls in `beagle-host/services/*`, nicht verteilt zwischen HTTP-Handlern und dem Control-Plane-Einstiegspunkt.
- Host-seitige VM-Profil-, Assignment-, Policy- und Public-Stream-Synthese gehoert ebenfalls in `beagle-host/services/*`, nicht in den HTTP-Einstiegspunkt.
- Host-Control-Plane-Code soll neue direkte `qm`-/`pvesh`-Nutzung nur noch in dedizierten Provider-Modulen wie `beagle-host/providers/*` einführen.
- Host-Control-Plane-Helfer fuer `qm guest exec`, `qm guest exec-status` und geplante VM-Restarts gehoeren ebenfalls in diese Provider-Module, nicht in HTTP-Handler oder Feature-Flows.
- Groessere Proxmox-UI-Renderer und Modal-Logik gehoeren nach `proxmox-ui/components/*`, nicht zurueck in `proxmox-ui/beagle-ui.js`.

---

## 🤖 MULTI-AI / CONTINUATION MODE (KRITISCH)

Dieses Projekt wird von mehreren AI-Agents bearbeitet.

### Daher MUSS IMMER gelten:

Jeder Agent muss so arbeiten, dass ein anderer Agent **nahtlos übernehmen kann**.

### Das bedeutet konkret:

- KEIN implizites Wissen
- KEINE "gedachten" Schritte
- ALLES muss im Repo dokumentiert sein

Jeder neue Agent muss innerhalb von 30 Sekunden verstehen:

- Wo stehen wir?
- Was wurde gemacht?
- Was ist kaputt / riskant?
- Was ist der nächste Schritt?

---

## 📁 Pflicht-Dokumentation (immer aktuell halten)

Erstelle und pflege:

docs/refactor/

- 00-system-overview.md
- 01-problem-analysis.md
- 02-target-architecture.md
- 03-refactor-plan.md
- 04-risk-register.md
- 05-progress.md
- 06-next-steps.md
- 07-decisions.md
- 08-todo-global.md
- 09-provider-abstraction.md

### 🔴 KRITISCHE REGEL:

Nach JEDEM größeren Schritt:

- `05-progress.md` aktualisieren
- `06-next-steps.md` neu definieren
- `08-todo-global.md` aktualisieren
- `07-decisions.md` ergänzen (wenn Architektur betroffen)
- `09-provider-abstraction.md` ergänzen (wenn Provider-/Backend-Kopplungen betroffen sind)

---

## 🧭 Arbeitsphasen

---

### PHASE 0 – Analyse

Analysiere:

- komplette Repo-Struktur
- Module
- Bash-Skripte
- UI
- Runtime
- Build-System
- Secrets / Tokens / Configs

Dokumentiere:

- Monolith-Dateien
- Sicherheitsprobleme
- Kopplungen
- technische Schulden

Schreibe:

- 00-system-overview.md
- 01-problem-analysis.md

---

### PHASE 1 – Zielarchitektur

Definiere klare Module:

- Beagle Host / Control Plane  
- Proxmox UI Integration  
- Thin Client Runtime  
- Gaming Kiosk  
- Build / Packaging  
- Shared Core  

Definiere:

- Verantwortlichkeiten
- APIs
- Abhängigkeiten
- Migrationsstrategie
- provider-neutrale Kernverträge
- Trennung von Business-Logik und Provider-Implementierungen

Schreibe:

- 02-target-architecture.md
- 09-provider-abstraction.md

---

### QUERSCHNITT – Provider-Abstraktion

Ziel:

- Proxmox kurzfristig voll unterstützen
- Proxmox langfristig austauschbar machen
- keine neue Business-Logik direkt an Proxmox koppeln

Regeln:

- generische Verträge zuerst
- Proxmox nur als Implementierung hinter dem Vertrag
- neue direkte Proxmox-Kopplung nur mit Dokumentation in `09-provider-abstraction.md`

---

### PHASE 2 – Proxmox UI Refactor

Ziel:

Monolith (z.B. beagle-ui.js) zerlegen in:

- api-client/
- state/
- components/
- provisioning/
- usb/
- utils/

Regeln:

- Verhalten bleibt identisch
- KEINE Feature-Verluste

---

### PHASE 3 – Thin Client Runtime

Ziel:

Strukturieren:

- config
- runtime
- network
- pairing
- moonlight-launch

Optional:

- komplexe Logik aus Bash extrahieren

WICHTIG:

- Moonlight darf NICHT kaputtgehen

---

### PHASE 4 – Security

Verbessere:

- Token-Handling
- Secret-Storage
- Frontend-Sicherheit

Vermeide:

- Tokens im Frontend
- Klartext-Secrets

---

### PHASE 5 – Packaging / Build

Ziel:

- klare Build-Pipeline
- reproduzierbare Builds
- getrennte Artefakte

---

### PHASE 6 – Modularisierung

Trenne klar:

- Host
- Client
- UI
- Kiosk

---

## 🧠 Arbeitsprinzip

- Kleine Schritte > große Umbauten
- Immer lauffähig bleiben
- Jede Änderung erklärbar machen
- Code + Doku gehören zusammen

---

## 🔁 Übergabe an nächsten Agent

Am Ende jedes Runs MUSST du:

1. `05-progress.md` aktualisieren
2. `06-next-steps.md` schreiben
3. `08-todo-global.md` aktualisieren
4. `09-provider-abstraction.md` aktualisieren, wenn Provider-/Backend-Grenzen berührt wurden
5. Offene Probleme dokumentieren

Schreibe IMMER:

- Was wurde gemacht
- Was ist kaputt (falls etwas kaputt ist)
- Was ist als nächstes zu tun (konkret, nicht allgemein)

---

## 🚫 Verboten

- große unstrukturierte Refactors
- stilles Löschen von Logik
- Breaking Changes ohne Dokumentation
- "TODO später" ohne Eintrag in TODO-Dateien

---

## ✅ Zielbild

Am Ende soll Beagle OS sein:

- modular
- wartbar
- sicher
- erweiterbar
- multi-agent-fähig

---

ENDE DER DATEI
