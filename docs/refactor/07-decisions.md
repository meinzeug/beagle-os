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

