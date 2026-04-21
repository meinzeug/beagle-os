# 02 — WebUI: styles.css → Teilmodule aufteilen

Stand: 2026-04-20  
Priorität: **Sofort** (April 2026)  
Betroffene Dateien: `website/styles.css`, `website/styles/*.css` (neu)

---

## Hintergrund

`website/styles.css` hat 2 358 Zeilen ohne Struktur-Grenzen außer Kommentar-Headern.
Durch die Aufteilung in thematische Teildateien unter `website/styles/` wird es möglich,
gezielt einzelne Bereiche zu bearbeiten ohne die gesamte Datei lesen zu müssen.
`styles.css` wird zum reinen `@import`-Barrel, der alle Teilmodule zusammenzieht.
Native CSS `@import` ist ohne Build-Toolchain verfügbar und im Browser unterstützt.
Für den Produktionsbetrieb kann später ein einfaches `cat`-Concat-Schritt oder
`postcss --no-import` das Barrel in eine einzelne Datei falten.

---

## Schritte

### Schritt 1 — Verzeichnis `website/styles/` anlegen und CSS-Tokens extrahieren

- [x] Verzeichnis `website/styles/` erzeugen.
- [x] Datei `website/styles/_tokens.css` anlegen mit allen `:root`-CSS-Custom-Properties (Zeilen 1–88 der `styles.css`).

Die CSS-Custom-Properties (Design-Tokens) sind der Ausgangspunkt jeder visuellen
Änderung und müssen als erstes isoliert werden, damit alle anderen Module sie einfach
referenzieren können. Darin enthalten sind Farb-Tokens für Dark- und Light-Mode,
Spacing-Werte, Border-Radius, Schatten und Typographie-Skala. Der Light-Mode-Override
auf Zeile 70 (`.light-mode :root { ... }`) gehört ebenfalls in diese Datei. Änderungen
am Farbschema oder Spacing-System passieren dann ausschließlich in `_tokens.css`.
Das vereinfacht Theme-Austausch und macht Branding-Updates trivial. Der Underscore-
Prefix signalisiert konventionsgemäß "Partial" (importiert, nicht direkt serviert).

---

### Schritt 2 — `_reset.css` und `_scrollbar.css` extrahieren

- [x] Datei `website/styles/_reset.css` anlegen (Zeilen 89–141 der `styles.css`).
- [x] Scrollbar-Styling in `_reset.css` als Abschnitt integrieren (Zeilen 133–141).

Der Reset setzt browser-default Margins/Paddings zurück, setzt `box-sizing: border-box`
global und stellt eine konsistente Basis für alle Komponenten her. Das Scrollbar-Styling
ist eng mit dem Reset verbunden (globale Erscheinung) und wird deshalb nicht in eine
separate Datei ausgelagert sondern als Abschnitt in `_reset.css` belassen. Reset-Änderungen
betreffen die gesamte Anwendung und sollten daher besonders sparsam vorgenommen werden.

---

### Schritt 3 — `_layout.css` und `_shell.css` extrahieren

- [x] Datei `website/styles/_layout.css` anlegen (App-Shell, Sidebar, Main-Column, Zeilen 142–400).

Die Anwendungsschale (App-Shell) mit Sidebar und Main-Column-Layout ist das strukturelle
Gerüst der gesamten UI. Alle Flex/Grid-Kontainer auf oberster Ebene, die Sidebar-Navigation,
der mobile Close-Button und die Hauptspalte gehören in diese Datei. Änderungen hier haben
breite visuelle Auswirkungen, weshalb der Scope klar definiert sein muss. Das mobile
Overlay-Backdrop und der Hamburger-Button gehören ebenfalls hierher da sie direkt mit
dem Sidebar-Verhalten zusammenhängen. Das Responsive-Verhalten für die Shell kommt
separat in `_responsive.css`.

---

### Schritt 4 — `_buttons.css` und `_account.css` extrahieren

- [x] Datei `website/styles/_buttons.css` anlegen (Zeilen 401–571).
- [x] Account-Menu-Styles ebenfalls in diese Datei (Zeilen 496–572).

Alle Button-Varianten (primary, secondary, danger, ghost, icon) sind in diesem Modul
gesammelt. Das Account-Dropdown-Menü ist eng an die primären Button-Styles gekoppelt
und wird deshalb in derselben Datei gehalten. Neue Button-Varianten müssen hier
angelegt werden, niemals als Inline-Style oder in einem Panel-spezifischen Modul.
Button-Styles gelten global und sind damit von Panel-spezifischen Styles zu trennen.

---

### Schritt 5 — `_cards.css`, `_stats.css` und `_chips.css` extrahieren

- [x] Datei `website/styles/_cards.css` anlegen (Zeilen 638–820 ohne Table).
- [x] Stats/KPI-Tiles in `_cards.css` als eigenen Abschnitt behalten (Zeilen 675–734).
- [x] Datei `website/styles/_chips.css` anlegen (Zeilen 820–851 + 2251–2269).

Karten sind das wichtigste visuelle Container-Muster der Anwendung und erscheinen in
nahezu allen Panels. Die Stats/KPI-Tiles sind eine spezialisierte Karten-Variante für
das Dashboard und werden als Abschnitt in `_cards.css` gehalten um Import-Overhead
zu vermeiden. Chips/Badges werden auf Status-Anzeigen (VM-Status, Rollen, Typen)
verwendet; alle Chip-Varianten in einer einzelnen Datei macht Farb-Konsistenz leichter.

---

### Schritt 6 — `_tables.css` und `_forms.css` und `_toolbar.css` extrahieren

- [x] Datei `website/styles/_tables.css` anlegen (Zeilen 735–851).
- [x] Datei `website/styles/_forms.css` anlegen (Zeilen 852–922 + 957).
- [x] Datei `website/styles/_toolbar.css` anlegen (Zeilen 923–956).

Tabellen haben eigene Hover-, Zebra- und Inline-Action-Button-Styles die ausschließlich
in `_tables.css` leben. Formulare (Input, Select, Textarea, Label, Checkbox) sind in
`_forms.css` normiert; das Toolbar/Filter-Bar-Pattern ist eine eigene Komponente die
Formulare und Buttons kombiniert und deshalb ein eigenes Modul verdient. Das Trennen
dieser drei Bereiche macht CSS-Only-Tests für Form-Layouts deutlich einfacher.

---

### Schritt 7 — Panel-spezifische CSS-Dateien in `website/styles/panels/` extrahieren

- [x] Unterverzeichnis `website/styles/panels/` erstellen.
- [x] `_inventory.css` (Workspace-Grid, Key-Value-Blocks, Action-Cards, USB/Bundles, Zeilen 957–1221).
- [x] `_virtualization.css` (Zeilen 1117–1231).
- [x] `_provisioning.css` (Zeilen 1222–1287).
- [x] `_policies.css` (Zeilen 1288–1324).
- [x] `_iam.css` (Zeilen 1325+IAM-Abschnitt).
- [x] `_sessions.css` (Zeilen 2270+Sessions-Panel).
- [x] `_settings.css` (Zeilen 2109–2192).
- [x] `_scope-switcher.css` (Zeilen 2193–2250).

Panel-spezifische Styles die ausschließlich für ein Panel gelten haben im globalen
Stylesheet nichts zu suchen. Durch die Extraktion in `panels/`-Unterverzeichnis ist
auf den ersten Blick klar, welche Styles welchem Feature-Bereich gehören. Das macht
das Löschen eines Panels in Zukunft trivial: Datei weg, Import-Zeile weg. Jede
Panel-Datei darf nur Selektoren verwenden die innerhalb dieses Panels auftreten.
Globale Token-Variablen aus `_tokens.css` sind überall verwendbar.

---

### Schritt 8 — `_modals.css` und `_banners.css` und `_inspector.css` extrahieren

- [x] Datei `website/styles/_modals.css` anlegen (Zeilen 1325–1552).
- [x] Datei `website/styles/_banners.css` anlegen (Banner/Activity-Log-Styles).
- [x] Datei `website/styles/_inspector.css` anlegen (Zeilen 1553–1562).

Das Modal-System ist die komplexeste Overlay-Komponente mit eigener Backdrop-,
Scroll- und Animationslogik und verdient ein eigenes Modul. Confirm-Dialog-Styles
kommen mit in `_modals.css` da Confirm-Dialoge Modal-Varianten sind. Banner (Erfolg,
Fehler, Warnung) und das Activity-Log-Panel haben ähnliche Erscheinungsbilder und
teilen sich `_banners.css`. Das Inspector-Panel (live VM-Stats) ist klein genug für
eine einzelne kurze Datei.

---

### Schritt 9 — `_nav.css`, `_helpers.css` und `_nav-badge.css` extrahieren

- [x] Datei `website/styles/_nav.css` anlegen (Scope-Switcher + Nav-Items + Zeilen 2193–2250).
- [x] Datei `website/styles/_helpers.css` anlegen (Spacing-Helpers, Hidden-Helper, Zeilen 1557–1576).
- [x] Nav-Badge in `_nav.css` integrieren (Zeilen 2237–2250).

> srv1-Validierung 2026-04-21: alle 16 CSS-Partials (globale Layer) + alle 8 Panel-Partials liefern HTTP 200, styles.css barrel mit `@import` korrekt, keine Browserblock-Fehler.

Navigations-Styles (Sidebar-Nav-Items, aktive Zustände, Nav-Badges für "Coming Soon")
gehören in `_nav.css`. Layout-Hilfsklassen (`.hidden`, `.sr-only`, `.mt-*`) kommen in
`_helpers.css`. Diese Trennung verhindert, dass Utility-Klassen in Panel-spezifischen
Dateien landen und global nicht gefunden werden.

---

### Schritt 10 — `_responsive.css` und `_reduced-motion.css` extrahieren, `styles.css` zum Barrel umbauen

- [x] Datei `website/styles/_responsive.css` anlegen (alle drei Breakpoint-Blöcke, Zeilen 1621–2108).
- [x] Datei `website/styles/_reduced-motion.css` anlegen (Zeilen 2101–2108).
- [x] `website/styles.css` auf reines `@import`-Barrel reduzieren.

Das Responsive-Stylesheet ist mit über 400 Zeilen der größte einzelne Abschnitt.
Die Breakpoints (920px, 600px, 380px) sind in einem Modul, sodass Anpassungen für
alle Viewports an einem Ort passieren. `prefers-reduced-motion` wird in einer eigenen
kleinen Datei isoliert damit Accessibility-Anpassungen leicht auffindbar sind.
Abschließend wird `styles.css` auf eine reine Liste von `@import`-Statements reduziert.
Die Import-Reihenfolge in `styles.css` ist: tokens → reset → layout → nav → buttons →
cards → chips → tables → forms → toolbar → modals → banners → inspector → helpers →
panels/* → responsive → reduced-motion. Diese Reihenfolge entspricht der CSS-Spezifitäts-
Hierarchie von global nach spezifisch.

---

## Testpflicht nach Abschluss

- [ ] Alle Panels visuell unverändert (Screenshot-Vergleich Light/Dark Mode).
- [x] Keine Konsolen-Fehler durch fehlende CSS-Klassen.
- [x] Mobile-Breakpoints korrekt (920px, 600px, 380px).
- [x] Dark Mode funktioniert nach Seiten-Reload.
- [x] CSP meldet keine Blocked-Ressourcen für CSS.
