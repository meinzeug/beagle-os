# Beagle OS Refactor - Decisions

Stand: 2026-04-13

## D-001: Beagle-native ist Primarpfad
- Entscheidung: Zielarchitektur ist eigenstaendig lauffaehig ohne Proxmox.
- Grund: Produktstrategie verlangt Plattformautonomie.

## D-002: Thinclient-Streaming ist Kernfaehigkeit
- Entscheidung: Streaming-Orchestrierung pro VM wird als Tier-1 Domain behandelt.
- Grund: Das ist das unterscheidende Produktmerkmal von Beagle OS.

## D-003: Session-basierte Auth als Standard
- Entscheidung: username/password + session lifecycle ersetzt Token-First UI.
- Grund: Multi-User Betrieb, Auditierbarkeit und RBAC brauchen identity-native Zugriffe.

## D-004: RBAC serverseitig erzwungen
- Entscheidung: Autorisierung wird im Backend zentral und deklarativ geprueft.
- Grund: UI-only checks sind unsicher und nicht ausreichend.

## D-005: Legacy API-Token nur fuer Automation
- Entscheidung: API tokens bleiben optional fuer machine-to-machine Zwecke.
- Grund: Rueckwaertskompatibilitaet fuer Skripte, ohne UI-Primarzugang darauf aufzubauen.

## D-006: Inkrementelle Wellen statt Big Bang
- Entscheidung: Umsetzung in vier Wellen mit klaren Abnahmen.
- Grund: Minimiert Runtime-Risiken und ermoeglicht fortlaufende Lieferbarkeit.

## D-007: Bootstrap-Admin fuer Erstzugang
- Entscheidung: Beim Start wird ein Bootstrap-Admin angelegt, wenn noch kein User existiert und Credentials gesetzt sind.
- Grund: Ermöglicht kontrollierten Erstzugang ohne separaten Setup-Wizard.

## D-008: Session-Token als primaerer API-Auth-Mechanismus
- Entscheidung: Bearer Session-Token werden als Standard fuer UI-Authentifizierung verwendet.
- Grund: Passt zu username/password Login und erlaubt klare Session-Lifecycles.

## D-009: Legacy API-Token bleibt waehrend Migration gueltig
- Entscheidung: X-Beagle-Api-Token und Bearer-Token mit Legacy-Wert bleiben im Backend als Fallback aktiv.
- Grund: Bestehende Automationspfade und Tools duerfen waehrend Umbau nicht brechen.

## D-010: RBAC-Matrix v1 wird im Handler erzwungen
- Entscheidung: Mutierende API-Routen werden serverseitig ueber eine explizite Permission-Matrix geprueft (deny-by-default).
- Grund: Sofortige Risikoreduktion fuer Write-Aktionen, bevor User/Role-CRUD vollstaendig verfuegbar ist.

## D-011: Audit-Basis als append-only Event-Log
- Entscheidung: Auth- und Mutationsereignisse werden in ein append-only JSONL Audit-Log geschrieben.
- Grund: Nachvollziehbarkeit und Security-Forensik werden frueh aktiviert, ohne erst auf vollstaendige Audit-UI warten zu muessen.

## D-012: Auth-User/Role-CRUD als Backend-API
- Entscheidung: Benutzer- und Rollenverwaltung wird als eigene API-Surface unter /api/v1/auth/users und /api/v1/auth/roles bereitgestellt.
- Grund: RBAC muss operativ verwaltbar sein und darf nicht nur aus Bootstrap-Konfiguration bestehen.

## D-013: Permission-Mapping in dediziertem AuthZ-Service
- Entscheidung: Routen-zu-Permission-Abbildung liegt in beagle-host/services/authz_policy.py statt im Handler.
- Grund: Trennung von HTTP-Transport und Autorisierungslogik verbessert Wartbarkeit und Testbarkeit.

## D-014: Session-Lifecycle mit Idle- und Absolute-Timeout serverseitig erzwingen
- Entscheidung: Session-Validierung prueft idle timeout und absolute timeout im Backend, nicht nur Token-Ablauf.
- Grund: Reduziert Risiko langlebiger oder inaktiver Sessions in Multi-User-Betrieb.

## D-015: User-weiter Session-Revoke als Admin-Operation
- Entscheidung: POST /api/v1/auth/users/<username>/revoke-sessions ermoeglicht gezielte Session-Invalidierung.
- Grund: Incident-Response und Account-Schutz brauchen sofortige serverseitige Sperrung aktiver Sessions.

## D-016: First-Install-Onboarding ist verpflichtend vor Dashboard-Zugriff
- Entscheidung: Bei pending Onboarding zeigt die Website einen Setup-Dialog und blockiert den normalen Dashboard-Flow.
- Grund: Frisch installierte Hosts brauchen einen gefuehrten Erst-Setup statt direkter UI-Nutzung ohne Initialkonfiguration.

## D-017: Onboarding-Status als eigener Auth-Endpunkt
- Entscheidung: /api/v1/auth/onboarding/status und /api/v1/auth/onboarding/complete bilden den expliziten Server-Setup-Lifecycle.
- Grund: UI und Backend brauchen einen klaren, persistierten Zustand fuer "first boot" vs "configured".

## D-018: Beagle ist Default-Provider im Host-Installpfad

## D-019: SSH-Passwort-Auth Default ist `yes` im Standalone-Installer
- Entscheidung: `BEAGLE_SERVER_SSH_PASSWORD_AUTH` Default im Server-Installer auf `yes` gesetzt.
- Grund: Ein frisch installiertes System muss per SSH erreichbar sein; Passwort-Deaktivierung bleibt opt-in fuer Hardening, nicht opt-out fuer Grundfunktionalitaet.
- Datei: `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer` Zeile 31.

## D-020: USB-Tunnel-User heisst `beagle-tunnel`, nicht `beagle`
- Entscheidung: Default-Benutzername fuer den SSH-USB-Tunnel-Account ist `beagle-tunnel`, nicht `beagle`.
- Grund: Wurde `beagle` verwendet, ueberschrieb das SSH-Match-Block (`AuthenticationMethods publickey`) auch den Basis-Admin-User und blockierte Passwort-Login vollstaendig.
- Dateien: `scripts/install-beagle-host-services.sh`, `scripts/check-beagle-host.sh`, `beagle-host/bin/beagle-control-plane.py`.

## D-021: Script-Provider-Wrapper muss Provider-Timeouts transparent durchreichen
- Entscheidung: `scripts/lib/beagle_provider.py` akzeptiert fuer `run_json`/`run_text`/`run_checked` optional `timeout` und behandelt `TimeoutExpired` als kontrollierten Fehlerpfad.
- Grund: Provider-Implementierungen nutzen `timeout=` bereits; ohne Durchreichen entstehen Laufzeitfehler (`TypeError`) und der VM-Prep bricht ab.
- Datei: `scripts/lib/beagle_provider.py`.

## D-022: Debian-Hosts duerfen nicht an Ubuntu-only Language-Packs scheitern
- Entscheidung: `configure-sunshine-guest.sh` installiert `language-pack-*` nur, wenn die Pakete auf dem Zielhost im APT-Index existieren.
- Grund: Das gleiche VM-Prep-Skript wird auf Debian- und Ubuntu-basierten Hosts genutzt; Ubuntu-only Pakete duerfen den Gesamtflow nicht stoppen.
- Datei: `scripts/configure-sunshine-guest.sh`.

## D-023: Libvirt-Kernel-Boot fuer Ubuntu-Install nutzt per-domain `seclabel type=none`
- Entscheidung: Fuer beagle-provider Domains mit `qemu:commandline` (`-kernel/-initrd`) wird im Domain-XML `seclabel type="none"` gesetzt.
- Grund: libvirt/AppArmor blockiert in dieser Konstellation den Kernel-Dateizugriff ansonsten reproduzierbar mit `Permission denied`, selbst bei lesbaren Dateien.
- Scope: Nur beagle-provider Install-Domain-Flow; keine hostweite Abschaltung des libvirt Security Drivers im Installer.
- Betroffene Datei: `beagle-host/providers/beagle_host_provider.py`.

## D-024: Moonlight USB-Presets duerfen nicht ohne Sunshine Auto-Pair Credentials ausgeliefert werden
- Entscheidung: Der VM-Installer-Skriptgenerator bricht Moonlight-Preset-Generierung ab, wenn `sunshine_username`, `sunshine_password` oder `sunshine_pin` fehlen.
- Grund: Unvollstaendige Presets fuehren nach Thinclient-Reboot zu manueller PIN-Eingabe und brechen den Zielpfad "auto-connect".
- Umsetzung: `beagle-host/services/installer_script.py` priorisiert explizite VM-Metadaten (`sunshine-user/password/pin`) und nutzt danach VM-Secret-Fallback; bei fehlenden Pflichtfeldern wird ein Fehler geworfen.

## D-025: Standalone-Host-Service-Install darf nicht auf distro-spezifischem QEMU-Paketnamen haengen
- Entscheidung: `scripts/install-beagle-host-services.sh` waehlt QEMU-Paketnamen dynamisch nach verfuegbarem APT-Candidate (`qemu-kvm` -> `qemu-system-x86` -> `qemu-system`) statt hartem Debian/Ubuntu-Annahmenmix.
- Grund: Frische Server-ISO-Installationen auf Debian 12 brachen reproduzierbar beim Host-Service-Install mit "qemu-kvm has no installation candidate".
- Wirkung: Standalone-Host-Setup bleibt zwischen Debian-/Ubuntu-Familien robust reproduzierbar.

## D-026: Standalone-Provisioning braucht `xorriso` als Pflicht-Tool
- Entscheidung: `xorriso` ist verpflichtender Teil der Standalone-Host-Abhaengigkeiten und Runtime-Readiness-Pruefung.
- Grund: Ohne `xorriso` scheitert die Seed-ISO-Erzeugung im Ubuntu-Autoinstall-Flow trotz ansonsten erfolgreichem Host-Setup.
- Umsetzung: Paketliste + Readiness-Check in `scripts/install-beagle-host-services.sh` erweitert (`virsh`, `qemu-img`, `xorriso`).

## D-027: API-Reverse-Proxy fuer Provisioning auf Long-Running Calls auslegen
- Entscheidung: `proxy_read_timeout` und `proxy_send_timeout` fuer Beagle-API-Locations werden auf 900 Sekunden gesetzt.
- Grund: Laengere Provisioning-Operationen (z. B. ISO-Download/VM-Setup) liefen reproduzierbar in 504 Timeouts bei 30s Default.
- Datei: `scripts/install-beagle-proxy.sh`.

## D-028: Frischer Host muss generische Thinclient-Artefakte immer mitziehen
- Entscheidung: Host-Install zieht zusaetzlich die generischen Shell-/PowerShell-Installer-Artefakte (`pve-thin-client-live-usb*`, `pve-thin-client-usb-installer*`) als Pflichtbestandteil des Release-Downloads.
- Grund: Ohne diese Artefakte liefern VM-spezifische Wrapper-Endpunkte (`/vms/<vmid>/installer.sh`) auf frischen Hosts 503 oder unvollstaendige Payloads.
- Datei: `scripts/install-beagle-host.sh`.

## D-029: Host-Service-Installer darf in Installer-Chroot kein Live-libvirt erzwingen
- Entscheidung: `scripts/install-beagle-host-services.sh` unterscheidet zwischen live-managebarer libvirt-Systemumgebung und chroot/offline Installationskontext; runtime-nahe libvirt waits/provisioning (`wait_for_libvirt_system`, `virsh net/pool`) werden nur in live Kontexten ausgefuehrt.
- Grund: Frische Server-ISO Installationen brachen im chroot-Host-Stack-Schritt reproduzierbar mit `libvirt qemu:///system is not ready` ab, obwohl der Schritt nur Zielsystem-Datei/Service-Provisioning benoetigte.
- Wirkung: Installer kann den Host-Stack im chroot zu Ende provisionieren; Live-libvirt Initialisierung bleibt fuer den gebooteten Hostpfad erhalten.
- Datei: `scripts/install-beagle-host-services.sh`.

## D-030: Server-Installer erzwingt Onboarding-First statt Bootstrap-Admin-Autocomplete
- Entscheidung: Der Server-Installer setzt im chroot Host-Installpfad `BEAGLE_AUTH_BOOTSTRAP_DISABLE=1`, und der Onboarding-Status behandelt bootstrap-only Nutzer in diesem Modus nicht als abgeschlossenes Setup.
- Grund: Frische Host-Installationen zeigten keinen Onboarding-Dialog mehr, weil ein automatisch angelegter Bootstrap-User den Setup-Status auf `completed` setzte.
- Wirkung: Web UI zeigt nach frischer Installation wieder verlässlich den verpflichtenden Onboarding-Flow; bestehende bootstrap-only Zustände werden auf `pending` zurückgeführt, sobald Bootstrap-Auth deaktiviert ist.
- Dateien: `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`, `beagle-host/services/auth_session.py`, `beagle-host/bin/beagle-control-plane.py`.

## D-031: Security-Funde muessen pro Run dokumentiert und nach Moeglichkeit sofort gepatcht werden
- Entscheidung: Jeder Agent-Run muss im bearbeiteten Scope aktiv nach Security-Funden suchen; neue Funde werden in `docs/refactor/11-security-findings.md` dokumentiert und direkt mitgepatcht, wenn der Fix reproduzierbar und risikoarm ist.
- Grund: Security darf im laufenden Refactor nicht als spaetere Phase behandelt werden, sonst akkumulieren versteckte Risiken zwischen mehreren Agentenruns.

## D-032: `AGENTS.md` und `CLAUDE.md` sind lokale Operator-Dateien und duerfen nicht versioniert werden
- Entscheidung: `AGENTS.md` und `CLAUDE.md` bleiben lokal-only, stehen in `.gitignore` und muessen aus dem Git-Tracking entfernt werden.
- Grund: Diese Dateien koennen interne Arbeitsanweisungen oder lokale Betriebsdetails enthalten und duerfen nicht versehentlich auf GitHub landen.

## D-033: Operator-Zugriff fuer `srv1.meinzeug.cloud` laeuft lokal ueber SSH-Key alias `meinzeug`
- Entscheidung: Lokaler Remote-Zugriff auf `srv1.meinzeug.cloud` wird ueber `ssh meinzeug` mit dediziertem Key `/home/dennis/.ssh/meinzeug_ed25519` abgewickelt.
- Grund: Vereinheitlicht Operator-Zugriff im Workspace und reduziert Passwort-Nutzung im Tagesbetrieb.

## D-034: `AGENTS.md` bleibt kompakte Policy, nicht der Volltext-Refactorplan
- Entscheidung: Die lokale `AGENTS.md` wird kurz gehalten und enthaelt nur dauerhafte Arbeitsregeln, Sicherheitsvorgaben, Uebergabepflichten und lokale Operator-Hinweise.
- Grund: Die alte Mischform aus Policy, Roadmap und Dateiplatzierungsdetails war drift-anfaellig und fuer neue Agents schwerer scanbar.
- Detailplanung, Architekturfeinschnitt und Migrationsstand gehoeren stattdessen nach `docs/refactor/*`.

## D-035: Release- und Installer-Source-Bundles duerfen keine lokalen Operator-Dateien enthalten
- Entscheidung: `AGENTS.md` und `CLAUDE.md` werden nicht in `beagle-os-v*.tar.gz`, server-installer embedded source bundles oder Hetzner installimage embedded source bundles aufgenommen.
- Grund: Diese Dateien sind lokale Operator-Artefakte und koennen interne Hinweise oder Zugangsdaten enthalten; sie duerfen nicht ueber GitHub, ISO oder tar.gz verteilt werden.
- Dateien: `scripts/package.sh`, `scripts/build-server-installer.sh`, `scripts/build-server-installimage.sh`.

## D-036: Runtime-Paketinstallation muss APT-Index explizit aktualisieren und darf Fehler nicht verschlucken
- Entscheidung: Standalone/Beagle-Provider Host-Service-Installationen fuehren vor Runtime-Paketinstallationen `apt-get update` aus und lassen fehlgeschlagene Pflichtinstallationen sichtbar fehlschlagen.
- Grund: Minimal-Rootfs aus Hetzner `installimage` hat keine zuverlaessigen APT-Listen; ein still geschluckter Installationsfehler fuehrte zu fehlendem `virsh` und gebrochenem Firstboot.
- Datei: `scripts/install-beagle-host-services.sh`.
