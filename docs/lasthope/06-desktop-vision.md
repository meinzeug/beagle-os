# Beagle OS — Desktop Vision: Der beste Open-Source-Desktop für die Menschheit

Stand: 2026-05-06
Version: 8.1.0

Dieses Dokument beschreibt die Langzeitvision für den Beagle OS Desktop —
was er sein soll, was die Konkurrenz macht, wo die Lücke liegt und welche
konkreten Schritte zum besten Open-Source-Desktop der Welt führen.

---

## Die Vision

> **Beagle OS Desktop ist der erste Open-Source-Desktop, der echte lokale
> Hardware-Erfahrung durch eine Stream-VM ersetzt — ohne dass der Nutzer
> jemals merkt, dass er nicht lokal arbeitet.**

Das ist der Kern: kein Thin-Client-Gefühl, kein VDI-Kompromiss, keine
sichtbare Latenz-Abweichung. Ein Desktop, der schneller, schöner und stabiler
wirkt als jede lokale Installation, dabei zentral verwaltbar und vollständig
Open Source ist.

---

## Markt-Analyse: Wo die Konkurrenz steht

Stand: 2026-05

### Elementary OS 8.1 (April 2026)
- **Stärke**: Konsequentes iOS-ähnliches Design (Pantheon DE), App-Qualität vor App-Menge,
  eigener AppCenter mit Pay-What-You-Want-Modell, ausgezeichnetes Onboarding.
  Neueste Version 8.1: verbesserte "Secure Session", Dock-Fixes, 1.100+ Issue-Reports
  gefixt, Accessibility-Verbesserungen.
- **Schwäche**: Eng ans eigene Ökosystem gebunden, kein Remote-/VDI-Szenario, kein
  Enterprise-Betrieb, langsame Updates, kaum Customization.
- **Beagle-Lücke**: Elementary hat keinen Server, kein Streaming, keinen Thin-Client.

### Zorin OS 18.1 (April 2026)
- **Stärke**: Windows-/macOS-ähnliches Gefühl für Umsteiger, visuell poliert,
  Pro-Tier finanziert die Free-Edition, sehr gutes Out-of-Box-Erlebnis.
  "Zorin Connect" verbindet Android-Phone mit Desktop (Dateiübertragung, Sync, Benachrichtigungen).
  Referenzfall: Stadt Vicenza verlängert PC-Lebensdauer um 30-40%.
- **Schwäche**: Proprietäres Look&Feel-Addon (Pro), kein Enterprise-Server-Stack,
  kein zentrales Management, kein Streaming.
- **Beagle-Lücke**: Zorin kann nicht zentral bereitgestellt und verwaltet werden.
  → **Beagle-Idee**: "BeagleConnect" als Phone-to-VM Clipboard/Datei-Sync analog Zorin Connect.

### Pop!_OS / COSMIC DE 1.0 Beta (System76, 2025)
- **Stärke**: COSMIC (Rust-based, Wayland-first) ist der mutigste DE-Neustart seit Jahren.
  Tiling-Workflows, Auto-Tiling-WM, GPU-Offload-Architektur für NVLink, Performanz-Fokus.
  **Modulares Custom-Theming-System**: Organisationen können ihr eigenes Farbpaletten-Theme
  ohne Qualitätsverlust deployen — genau das macht Beagle mit BeagleCyberpunk.
  **Custom-Applets**: COSMIC betont, dass Panels/Applets/Shell-Komponenten alle
  dasselbe Toolkit verwenden → Beagle braucht eigene KDE-Plasmoids (BeagleStream-Widget).
  **Sicherheit**: Wayland-nativ verhindert Keylogging und Input-Spoofing.
  System76 verkauft Hardware und OS zusammen — starke vertikale Integration.
- **Schwäche**: COSMIC ist noch in Beta (Pop!_OS 24.04 Beta), kein Thin-Client, kein VDI,
  kein Streaming-Protokoll, keine zentrale Fleet-Verwaltung.
- **Beagle-Lücke**: COSMIC ist ein lokaler Desktop. BeagleStream macht denselben
  Desktop remote nutzbar, ohne ihn neu bauen zu müssen.
  → **Key Learning**: Beagles Custom-Theming (BeagleCyberpunk) ist strategisch richtig —
  COSMIC validiert diesen Ansatz als state-of-the-art.

### KDE Plasma 6 (Vanilla)
- **Stärke**: Mächtigstes Open-Source-DE: umfangreichste Konfigurierbarkeit,
  bestes Multi-Monitor-Handling, Plasma Mobile, Wayland-Migration abgeschlossen
  (Plasma 6.0+), KWin-Compositor mit exzellenter Performance.
- **Schwäche**: Kein vorkonfigurierter Desktop für End-Nutzer — zu viele Optionen,
  zu viel Default-Rauschen, kein zentrales Remote-Management, kein Streaming-Stack.
- **Beagle-Lücke**: Plasma ist das perfekte Fundament — Beagle OS liefert die
  fehlende Schicht: zentral provisioniert, remote gestreammt, mit fester UX-Baseline.

### Nitrux OS
- **Stärke**: Visuell sehr eigenständig (NX Desktop), Maui-Apps in Qt/QML mit
  modernster Optik, AppImage-first, rolling release.
- **Schwäche**: Nische, kein Enterprise, kein VDI, kein Streaming.

### Citrix / VMware Horizon / Windows 365
- **Stärke**: Industriestandard für VDI, Active Directory-Integration, GPU-Support,
  massive Enterprise-Präsenz.
- **Schwäche**: Komplett proprietär, extrem teuer (pro Nutzer-Lizenz), Windows-only
  auf Server-Seite, keine echte Open-Source-Option, Abhängigkeit von Vendor-Lock-in.
- **Beagle-Lücke**: Beagle OS ist das erste vollständig Open-Source-VDI-System mit
  nativem Streaming-Protokoll und eigenem Thin-Client-OS.

---

## Was Beagle OS einzigartig macht

| Merkmal | Beagle OS | Elementary | Zorin | COSMIC | Citrix/VMware |
|---|---|---|---|---|---|
| Open Source 100% | ✅ | ✅ | teilweise | ✅ | ❌ |
| Streaming-nativer Desktop | ✅ | ❌ | ❌ | ❌ | ✅ (proprietär) |
| Eigener Thin-Client | ✅ | ❌ | ❌ | ❌ | ✅ (proprietär) |
| KVM/libvirt-Hypervisor | ✅ | ❌ | ❌ | ❌ | ❌ |
| Zentrale Fleet-Verwaltung | ✅ | ❌ | ❌ | ❌ | ✅ (proprietär) |
| WireGuard Zero-Trust VPN | ✅ | ❌ | ❌ | ❌ | teilweise |
| Cyberpunk-Branding | ✅ | ❌ | ❌ | ❌ | ❌ |
| Keine Vendor-Lock-in | ✅ | ✅ | teilweise | ✅ | ❌ |

---

## Desktop-Optimierungs-Roadmap

### Phase A — Baseline UX (jetzt) ✅ begonnen

Die Grundlage muss stimmen: Window Manager, Panels, Taskbar, System-Tray,
Uhr und Keyboard-Capture laufen korrekt.

- [x] `kwin_x11` als Pflichtpaket in Plasma-Profile
- [x] Vollständiges Panel: Kickoff, Task Manager, System Tray, Clock, Show Desktop
- [x] Keyboard-Capture: nur ein Escape-Kürzel (`Ctrl+Alt+Shift+F12`), alle anderen zur VM
- [x] `beagle-plasma-desktop-repair` Autostart als WM-Fallback
- [x] Fensteranimationen aktivieren (KWin Compositing, Blur-Effekte)
- [x] Plasma-Aktivitäten auf 1 virtual desktop reduziert (kein Workspace-Wirrwarr im Stream)
- [ ] Plasma-Aktivitäten vollständig deaktivieren (optional, nur wenn nötig)

### Phase B — Cyberpunk-Identität ✅ begonnen

Beagle OS soll sofort erkennbar sein. Kein generisches Breeze-Dark.

- [x] **BeagleCyberpunk.colors** KDE-Color-Scheme installiert und aktiv:
  - Basis: Dark Navy `#0a0e1a`
  - Accent: Electric Cyan `#00f5ff`
  - Sekundär: Neon Magenta `#ff006e`
  - Text: Bright White `#e8f4f8`
  - Selection: Cyan-Highlight
- [x] IBM Plex Sans als Beagle-Standardfont (Branding-Font + H.264-tauglich)
- [x] Hack als Monospace-Font (Terminal + Code)
- [x] `fonts-ibm-plex` + `fonts-hack-ttf` via apt in firstboot installiert
- [ ] Eigenes Icon-Theme (Beagle-Fork von Papirus-Dark mit Cyan-Akzent)
- [x] KDE Plasma Splash Screen deaktiviert (Engine=none, Theme=none → schnellerer Login im Stream)
- [ ] Login-Screen (`sddm`) mit Beagle-Cyberpunk-Theme
- [x] Terminal-Preset (Konsole): BeagleCyberpunk.colorscheme + Hack 12pt + cyan Cursor-Blink (5ca7f00)
- [ ] App-Launcher (Kickoff oder Krunner) mit Beagle-Logo und Dark-Glass-Look
- [ ] Cursor-Theme: Breeze-Snow oder eigener Cyberpunk-Cursor

### Phase C — Smart Defaults für den Streaming-Use-Case ✅ begonnen

Ein Desktop für eine gestreamte VM hat andere Prioritäten als ein lokaler Desktop.

- [x] **Global Menu** (`org.kde.plasma.appmenu`) — ENTFERNT: nicht Windows-like.
  AppletOrder ist jetzt Windows-10/11-Style: Kickoff → IconTasks → Separator → SysTray → Clock → ShowDesktop
- [x] Single-Click zum Öffnen von Dateien (Dolphin-Default für Streaming)
- [ ] Super+Escape als Beagle-Escape aus dem VM-Stream (in Openbox rc.xml aktiv)
- [ ] Maximiere-Fenster-Policy: Neu geöffnete Apps direkt maximiert
- [x] Desktop-Symbole deaktiviert: containment=org.kde.plasma.desktop statt org.kde.plasma.folder
- [ ] Notifications-Center an statt floating Popups
- [ ] Night Color (Blaulicht-Filter) konfigurierbar ohne System-Settings öffnen
- [x] Drag-Lock deaktiviert: DragToMaximize=false, ElectricBorderDelay=150ms (8d4c6b3)
- [ ] Clipboard-Sync zwischen Host und VM über BeagleStream (KDE Clipboard Manager)

### Phase D — Performance und Latenz ✅ begonnen

Für Streaming ist wahrgenommene Geschwindigkeit entscheidend.

- [x] KWin Animations: speed=3 (von 5 auf 3 reduziert, schnellere Übergänge)
- [x] **AnimationDurationFactor=0.5** in KWin Compositing → alle Animationen halbiert
- [x] Fonts: Sub-Pixel-Hinting für scharfe Schrift bei verlustbehaftetem H.264-Stream
  (Hint: `Full`, RGB-Sub-Pixel, DPI 96)
- [x] Power-Save deaktiviert (alle DPMS, Suspend, Dimming via kscreenlockerrc)
- [x] KWin Compositor: Backend=OpenGL, VSync=true, TearingPrevention=2, LatencyPolicy=Low (8d4c6b3)
- [ ] Startup-Zeit: Plasma-Splash unterdrücken oder auf <1s verkürzen
- [ ] systemd-inhibit für BeagleStream (kein Schlaf während aktiver Session)

### Phase G — Windows Migration Experience ✅ begonnen (9b1d1ca)

Windows-Nutzer sind die größte potenzielle Benutzergruppe. Beagle OS muss für
sie der einfachste Umstieg aller Zeiten sein — nicht weil wir Windows kopieren,
sondern weil wir das Beste aus Win10/11 nehmen und es Open-Source-würdig machen.

**Design-Prinzip**: Windows 10/11-Hybrid. Ab Windows 10 haben die meisten
User aufgehört, UI-Änderungen zu mögen. Wir nehmen diesen Stand, verfeinern
ihn mit AI-Integration und Beagle-Streaming — und lassen ihn dabei besser
aussehen als das Original.

- [x] **BeagleWindows.colors** KDE-Farbschema:
  - Basis: Dark `#1C1C1C` (Win11 Dunkelgrau)
  - Accent: Windows Blue `#0078D4`
  - Text: Weiß/Hellgrau (Win-Standard)
- [x] **plasma-windows** Profil in `service_registry.py` (visible_in_ui=True)
- [x] kwinrc windows-Variante: AnimationDurationFactor=0.3, Snapping aktiv,
  Fenster-Buttons rechts (_, □, X) — exakt Win-Stil
- [x] kdeglobals: Double-Click zum Öffnen (Windows-Standard), ScaleFactor=1
- [x] kwriteconfig apply-script: vollständige Branch-Logik
  für `cyberpunk`, `windows`, `classic`
- [ ] Taskbar mittig (Windows 11 Style) — KDE Kickoff mittig ausrichten
- [ ] Start-Menü-Look: Kickoff mit Kacheln statt Liste
- [x] Windows-kompatible Tastenkürzel: Win+E → Dolphin, Win+D → Show Desktop,
  Win+I → System Settings, Win+R/Alt+F2 → KRunner (alle in kglobalshortcutsrc)
- [ ] "Willkommen bei Beagle OS" Setup-Wizard für neue Windows-Umsteiger
- [ ] Rechtsklick → "Weitere Optionen anzeigen" (Win11-Stil) via KDE Servicemenus

### Phase H — Auflösungen und Skalierung ✅ implementiert (9b1d1ca)

Auflösung darf kein Hardware-Problem mehr sein. Der VKMS-Virtual-Display
unterstützt beliebige Auflösungen via xrandr — wir müssen sie nur registrieren.

- [x] **beagle-vkms-xrandr-setup** registriert alle gängigen Auflösungen:
  - 1280×720, 1366×768, 1440×900, 1600×900
  - 1920×1080 (Standard-Default), 1920×1200
  - 2560×1440, 3840×2160@30, 3840×2160@60
  - Alle erscheinen sofort in KDE System Settings → Anzeige → Auflösung
  - Kein Hardware-abhängiger Fix — rein xrandr/VKMS
- [x] **KDE Display Scaling**: `ScaleFactor=1` als Default in kdeglobals
  (Nutzer kann über System Settings → Anzeige anpassen — 100%, 125%, 150%, 200%)
- [x] Live auf beagle-100/srv1 angewendet — 21 Auflösungen bestätigt
- [ ] Skalierungsprofile pro Client-Auflösung (z.B. HiDPI-Clients automatisch erkennen)
- [ ] Auflösungs-Wizard im firstboot: Client-Auflösung erkennen und Default setzen
- [ ] BeagleStream-seitige automatische Auflösungsanpassung wenn Client sich verbindet

### Phase I — AI-Integration ✅ begonnen (9b1d1ca)

AI ist keine optionale Zukunft mehr — es ist die Erwartungshaltung jedes
neuen Nutzers. Beagle OS integriert AI nativ, nicht als Browser-Tab.

- [x] **beagle-ai Launcher** (`/usr/local/bin/beagle-ai`):
  - Prüft zuerst lokales Ollama (localhost:11434) → Open WebUI (localhost:3000)
  - Fallback: ChatGPT (chatgpt.com) in Chrome App-Mode
  - Tastenkürzel: **Meta+A** (kglobalshortcutsrc)
  - Im Taskbar gepinnt (icontasks launchers=)
  - `/usr/share/applications/beagle-ai.desktop` system-wide
- [ ] **Lokales Ollama optional installierbar** via `beagle-ai-setup`-Skript
  (`ollama pull llama3.2` + `open-webui` als systemd-User-Service)
- [ ] **BeagleStream + AI**: AI-Overlay direkt im Stream-Client (Phase E/F)
- [ ] **AI-gestütztes Desktop-Onboarding**: KI erklärt beim ersten Start
  Funktionen des Desktops (lokaler Ollama oder API)
- [ ] **Sprachsteuerung**: Whisper.cpp lokal für Voice-to-Text in Konsole/Browser
- [ ] **Smart Clipboard**: AI fasst kopierten Text zusammen / übersetzt ihn

### Phase E — Beagle-eigene Panel-Widgets

Beagle OS braucht eigene Panel-Applets, die keine andere Distribution hat.

- [ ] **BeagleStream-Status-Widget**: zeigt Verbindungsqualität (FPS, Latenz, Bitrate)
  direkt im System-Tray — ähnlich wie ein VPN-Status-Indicator
- [ ] **VM-Info-Widget**: zeigt VM-Name, CPU/RAM-Auslastung der laufenden VM
  (Daten aus BeagleStream-Metrics oder QEMU Guest Agent)
- [ ] **Beagle-Session-Controls**: direkt im Tray: Session pausieren, Resume, Disconnect
  ohne Alt+F4 oder Menü-Navigation
- [x] **Escape-Hint-Overlay**: beim Starten des Streams kurz einblenden:
  `"Super+Escape → Lokalen Desktop"` — zenity auto-close 4s (128b575)

### Phase F — Accessibility und Internationalisierung

Der beste Desktop der Welt muss für alle nutzbar sein.

- [ ] Screen Reader (Orca) funktioniert im Stream (AT-SPI über VirtIO)
- [ ] High-Contrast-Theme verfügbar (auch im Cyberpunk-Stil)
- [ ] Schriftgröße skalierbar über Beagle-Setup ohne System-Settings
- [ ] Tastaturnavigation für alle Beagle-eigenen Widgets
- [ ] i18n: Alle Beagle-spezifischen Strings in QM-Dateien (Deutsch, Englisch, initial)

---

## Was der beste Open-Source-Desktop für die Menschheit bedeutet

Nicht der Desktop mit den meisten Features. Nicht der schönste Screenshot.
Sondern der, der diese drei Versprechen gleichzeitig hält:

1. **Du brauchst keine lokale Hardware mehr** — dein Desktop läuft in der Cloud
   oder auf einem Unternehmensserver, ohne dass du das merkst.
2. **Du bist nicht eingesperrt** — alles ist Open Source, alles ist migrierbar,
   nichts gehört einem einzelnen Vendor.
3. **Es funktioniert für jeden** — Schulen mit Thin-Clients, Krankenhäuser ohne
   IT-Abteilung, Entwickler mit veralteter Hardware, Menschen in
   Ländern ohne teure Geräte.

Das ist Beagle OS.

---

## Abnahme-Gate "Desktop Excellence"

Beagle OS Desktop gilt als exzellent (Gate D-UX), wenn:

- [ ] Ein erstmaliger Nutzer (kein Linux-Vorwissen) kann nach 5 Minuten arbeiten.
- [x] Alle Fenster haben sichtbare Schließen/Minimieren/Maximieren-Buttons.
- [x] Taskbar zeigt alle offenen Fenster, ermöglicht Wechseln per Klick.
- [x] System-Tray zeigt Netzwerk, Lautstärke und Uhrzeit.
- [x] Alt+F4 schließt das Fenster in der VM, nicht auf dem Thin-Client.
- [x] Ctrl+Alt+Shift+F12 bringt zurück zum lokalen Desktop.
- [x] Keine Desktop-Icons im Weg.
- [x] KWin läuft immer; wenn nicht, startet `beagle-plasma-desktop-repair` es neu.
- [x] Schriften sind lesbar (Sub-Pixel-Hinting aktiv, richtige DPI).
- [x] Mindestens 8 Auflösungen wählbar in KDE System Settings (1280×720 bis 4K).
- [x] Beagle AI mit Meta+A erreichbar und im Taskbar gepinnt.
- [ ] Stream-Status (FPS, Latenz) ist im Tray sichtbar.
- [x] Dark Cyberpunk Color-Scheme ist konsistent von Login bis Terminal.
- [ ] Windows-Profil: Windows-Nutzer erkennen die UI sofort als vertraut.

---

## Konkurrenz-Lücke zusammengefasst

| Was fehlt überall | Beagle OS Antwort |
|---|---|
| Open-Source VDI mit Streaming | BeagleStream (Sunshine/Moonlight-Fork) |
| Eigener Thin-Client | Beagle Endpoint OS |
| Zentrale Fleet-Verwaltung | Beagle Web Console + Host-Manager |
| Cyberpunk-Identität | Beagle Cyberpunk Theme + Branding |
| WireGuard Zero-Trust | integriert in Thin-Client und Stream |
| KVM ohne Proxmox-Lock-in | providers/beagle/ (libvirt-native) |
| Stream-Status im Desktop | BeagleStream-Status-Widget (Phase E) |

---

## Kanonische Quellen

- `docs/checklists/02-streaming-endpoint.md` — BeagleStream Details
- `docs/checklists/04-quality-ci.md` — UX/i18n Gates
- `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl` — Plasma-Provisioning
- `beagle-stream-client/app/streaming/input/input.cpp` — Keyboard-Capture-Logik
- `docs/refactor/05-progress.md` — Fortschrittslog
