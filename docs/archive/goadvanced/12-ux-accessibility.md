# Plan 12 — UX, Accessibility, i18n, Mobile

**Dringlichkeit**: LOW–MEDIUM
**Welle**: C (Langfrist)
**Audit-Bezug**: F-001, F-002, F-003, F-004

## Problem

Web-Console (`website/ui/*.js`) hat UX-Defizite:

- Keine Internationalisierung — Strings sind hart-kodiert in Deutsch/Englisch-Mischform
- Fehlende ARIA-Attribute — Screenreader-Nutzer sind ausgeschlossen
- Keine konsistenten Mobile-Breakpoints — auf Smartphone unbenutzbar
- Fehlerausgabe heterogen (mal Toast, mal Alert, mal stiller Console-Log)
- Kein Dark-Mode-Toggle
- Keyboard-Navigation luckenhaft

## Ziel

1. Vollstaendige i18n via Lightweight-Lib (kein React/Vue, da Vanilla-Stack).
2. ARIA-Compliance fuer alle interaktiven Elemente (WCAG 2.1 AA).
3. Mobile-Responsive (>= 360px).
4. Standardisierte Error-Display via `error-handler.js`.
5. Tastaturnavigation fuer alle Workflows.

## Schritte

- [x] **Schritt 1** — i18n-Infrastruktur
  - [x] `website/locales/de.json` + `website/locales/en.json`
  - [x] `website/ui/i18n.js`:
    - `t(key, params={})` → uebersetzter String
    - Fallback: en → key
    - Sprache aus `navigator.language` oder `localStorage.lang`
    - Live-Switch via Settings-Panel
  - [x] Tests: `tests/unit/test_i18n_and_error_handler.py` (21 Tests, alle PASS)
  - [ ] Migration: ein Modul nach dem anderen umstellen, beginnend mit `auth_admin.js`, `vms_panel.js`

- [x] **Schritt 2** — Standardisierte Error-Behandlung
  - [x] `website/ui/error-handler.js`:
    - `showError(err, {context, recoverable})` → konsistenter Toast + Logging
    - `showWarning(msg)`, `showSuccess(msg)`, `showInfo(msg)`, `withErrorHandling(promise, ctx)`
    - `handleFetchError(err, context)` mappt HTTP-Status auf i18n-Texte
    - Stack-Trace nur in Dev-Mode
  - [x] Migration: alle `console.error` und `alert()`-Aufrufe ersetzt
    - `website/ui/cluster.js` (1 Stelle)
    - `website/ui/events.js` (2 Stellen → dynamischer Import)
    - `website/ui/secrets_admin.js` (2 Stellen → dynamischer Import)

- [ ] **Schritt 3** — ARIA + Tastatur
  - [ ] Audit: `axe-core` als CLI gegen `https://srv1/ui` laufen lassen
  - [ ] Pro UI-Modul:
    - Buttons: `aria-label`, `role="button"` wo `<div>`-Buttons existieren
    - Modals: `role="dialog"`, `aria-modal="true"`, Focus-Trap, ESC-Close
    - Tabellen: `<th scope>`, `aria-sort`
    - Forms: `<label for>` ueberall, Error-Mitteilungen via `aria-describedby`
  - [ ] Tab-Reihenfolge sinnvoll (kein `tabindex > 0` ausser begruendet)
  - [ ] Skip-Link "Zum Hauptinhalt"

- [ ] **Schritt 4** — Mobile-Responsive
  - [ ] `website/styles.css` (oder Plan 02 GoFuture Splits) erweitern:
    - Breakpoints: 360px, 600px, 900px, 1200px
    - Sidebar collapsable < 900px
    - Tabellen → Card-Layout < 600px
    - Touch-Targets >= 44x44 px
  - [ ] Test: Lighthouse Mobile-Score > 90

- [ ] **Schritt 5** — Dark-Mode
  - [ ] CSS-Variablen fuer Farbpalette
  - [ ] Toggle in Settings-Panel + `prefers-color-scheme`-Default
  - [ ] LocalStorage-Persistenz

- [ ] **Schritt 6** — Loading + Empty States
  - [ ] Skeleton-Loader fuer alle Listen
  - [ ] Empty-State mit konkreter Action ("Noch keine VMs — Erste VM erstellen")
  - [ ] Error-State mit Retry-Button

- [ ] **Schritt 7** — Doku
  - [ ] `docs/ux/style-guide.md`: Farben, Typo, Spacing, Components
  - [ ] `docs/ux/i18n-guide.md`: Wie neue Strings hinzufuegen
  - [ ] `docs/ux/accessibility-checklist.md`: Pre-Merge-Check

- [ ] **Schritt 8** — Verifikation
  - [ ] axe-core: 0 Critical/Serious Violations
  - [ ] Lighthouse: Performance > 80, Accessibility > 90, Best Practices > 90
  - [ ] Manuelle Screenreader-Tests (NVDA + VoiceOver)
  - [ ] Mobile-Test auf Pixel-emuliertem Viewport

## Abnahmekriterien

- [ ] Alle UI-Module nutzen `t()` statt Hard-Coded Strings.
- [ ] axe-core findet 0 Critical Issues.
- [ ] Mobile (Pixel 5 Viewport): alle Workflows ausfuehrbar.
- [ ] Dark-Mode produktiv.
- [ ] Standardisierte Error-Toasts in allen Modulen.

## Risiko

- i18n-Migration ist arbeitsintensiv → schrittweise pro Modul, kein Big-Bang
- Mobile-Layouts koennen Desktop-UX brechen → progressive Enhancement statt Refactor
- Screenreader-Tests sind manuell — nicht in CI automatisierbar
