# 03 — WebUI: index.html aktualisieren

Stand: 2026-04-20  
Priorität: **Sofort** (April 2026)  
Betroffene Dateien: `website/index.html`

---

## Hintergrund

`website/index.html` referenziert noch `app.js` als klassisches `<script>`-Tag.
Nach Abschluss der JS-Modularisierung (Plan 01) muss der Einstiegspunkt auf `main.js`
als `type="module"` umgestellt werden. Außerdem müssen `browser-common.js` und
`beagle-web-ui-config.js` weiterhin als klassische Scripts vor dem Modul-Import
geladen werden, da sie globale Objekte (`window.BeagleBrowserCommon`,
`window.BEAGLE_WEB_UI_CONFIG`) bereitstellen, die `main.js` beim Start erwartet.

---

## Schritte

### Schritt 1 — Script-Tag von `app.js` auf `main.js` umstellen

- [x] In `index.html`: `<script src="/app.js?v=7.1.0">` ersetzen durch `<script type="module" src="/main.js?v=7.2.0">`.
- [x] Sicherstellen, dass `browser-common.js` und `beagle-web-ui-config.js` als normale `<script>`-Tags **vor** `main.js` stehen.

`type="module"` verändert das Ladeverhalten: Module werden automatisch `defer`-artig
geladen und erst nach dem DOM-Parsing ausgeführt. Zirkuläre Imports zwischen den UI-
Modulen werden von ES-Modulen über Live-Bindings korrekt behandelt solange Querverweise
in Funktionskörpern und nicht auf Top-Level stattfinden. Der Versions-Query-Parameter
(`?v=7.2.0`) bewirkt Cache-Busting bei Browser-Clients. `browser-common.js` bleibt
als klassisches Script weil es kein ES-Modul ist und `window.BeagleBrowserCommon`
als Global setzen muss, bevor `main.js` startet. Die Reihenfolge der Script-Tags
in `index.html` ist damit: 1) `beagle-web-ui-config.js`, 2) `browser-common.js`,
3) `<script type="module" src="/main.js">`.

---

### Schritt 2 — Version-Konstante und Cache-Busting vereinheitlichen

- [x] Version aus `VERSION`-Datei im `package.json` o.ä. als einzige Source-of-Truth definieren.
- [x] Build-Skript oder `sed`-Zeile in `scripts/package.sh` ergänzen, die die Versionsnummer in `index.html` automatisch ersetzt.

Manuell gepflegte Versionsnummern in HTML-Dateien führen regelhaft zu veralteten Ständen.
Ein automatischer Ersatz durch das Release-Skript stellt sicher, dass der Cache-Busting-
Parameter bei jedem Release korrekt aktualisiert wird. Die `VERSION`-Datei im Repo-Root
ist bereits vorhanden und kann als Single Source of Truth dienen. Alternativ kann auch
ein `Content-Hash`-Ansatz genutzt werden wenn später ein Build-Schritt eingeführt wird.

---

### Schritt 3 — `<meta http-equiv="Content-Security-Policy">` prüfen und aktualisieren

- [x] CSP-Header in `index.html` (oder in `nginx.conf`) auf Kompatibilität mit `type="module"` prüfen.
- [x] `script-src 'self'` ist ausreichend — keine `'unsafe-inline'` oder `'unsafe-eval'` hinzufügen.

ES-Module mit `type="module"` von gleichem Origin sind durch `script-src 'self'` abgedeckt.
Die bestehende CSP muss nicht gelockert werden solange kein CDN-Fremddomain-Import erfolgt.
`'nonce'`-basierte CSP wäre die zukunftssichere Alternative falls inline-Styles
oder dynamische Scripts notwendig werden. Derzeit ist `script-src 'self'` ausreichend
und sicher. Kein `'unsafe-inline'` und kein `'unsafe-eval'` dürfen hinzugefügt werden.
Nach der Umstellung in den Browser-DevTools unter "Security" prüfen, ob CSP-Violations
gemeldet werden.

---

### Schritt 4 — Alte `app.js` als Fallback-Stage entfernen

- [x] Nach erfolgreicher Test-Phase `app.js` aus `website/` löschen.
- [x] Referenz in `scripts/package.sh` und `scripts/publish-*.sh` entfernen.

Solange beide Dateien (`app.js` und `main.js`) existieren besteht das Risiko dass ein
versehentlicher Rollback das alte Monolith wieder aktiviert. Nach bestandenem Test
(alle Panels, Login, Provisioning, IAM) wird `app.js` gelöscht. Die `package.sh` und
Publish-Skripte müssen aktualisiert werden, damit sie nicht mehr `app.js` ins
Release-Artefakt kopieren. Der Lösch-Schritt ist ein Breaking Change und muss mit einem
Release-Tag versehen werden.

---

## Testpflicht nach Abschluss

- [ ] Seitenaufruf in Firefox und Chromium erfolgreich, kein JavaScript-Fehler in DevTools.
- [x] Network-Tab: alle Module werden als `(module)` geladen, kein 404.
- [x] Security-Tab: keine CSP-Violations.
- [ ] Login-Flow komplett durchlaufen.
- [x] Browser-Cache nach Update korrekt invalidiert (Versionsstring in URL sichtbar).
