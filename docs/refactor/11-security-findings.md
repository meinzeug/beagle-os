# Security Findings

Stand: 2026-04-26 (ergänzt: S-021 Cluster-Preflight/Port-Härtung + Setup-Code Auto-Join)

## S-023 — GitHub Release Workflow war durch unzulaessigen `secrets`-Ausdruck deaktiviert (PATCHED)

- Status: **gepatcht** (2026-04-26)
- Risiko: **Mittel**
- Betroffene Dateien:
  - `.github/workflows/release.yml`
- Beschreibung:
  - Der Release-Workflow nutzte `if: ${{ secrets.BEAGLE_RELEASE_GPG_KEY != '' }}`.
  - GitHub Actions akzeptiert `secrets.*` an dieser Stelle nicht; der gesamte Workflow wurde deshalb schon beim Parsen als invalid verworfen.
  - Folge: Pushes nach `main` bzw. Release-Laeufe konnten keinen gueltigen Workflow-Run erzeugen, Artefakte/Checksummen/Signaturen wurden gar nicht mehr gebaut.
- Fix:
  - Die Secret-Pruefung wurde in den Shell-Schritt verlegt.
  - Der Schritt importiert den GPG-Key jetzt nur noch, wenn `BEAGLE_RELEASE_GPG_KEY` in `env` gesetzt ist; sonst wird sauber ohne Signaturpfad weitergelaufen.
- Rest-Risiko:
  - Die eigentliche Release-Erzeugung auf GitHub muss nach Push erneut live bestaetigt werden.

---

## S-022 — Artifact-Watchdog las initial die falsche Settings-Datei (PATCHED)

- Status: **gepatcht** (2026-04-26)
- Risiko: **Niedrig bis Mittel**
- Betroffene Dateien:
  - `scripts/artifact-watchdog.sh`
  - `beagle-host/services/server_settings.py`
- Beschreibung:
  - Die WebUI speichert Server-/Artifact-Einstellungen im Manager-Datenpfad (`/var/lib/beagle/beagle-manager/server-settings.json`).
  - Der neue Artifact-Watchdog las initial `/etc/beagle/server-settings.json` und konnte dadurch `enabled`/`auto_repair`/`max_age_hours` ignorieren.
  - Folge: UI-Konfiguration und Host-Reaktion konnten auseinanderlaufen.
- Fix:
  - Watchdog liest jetzt standardmaessig denselben Manager-Datenpfad wie die Control-Plane (`${BEAGLE_MANAGER_DATA_DIR:-/var/lib/beagle/beagle-manager}/server-settings.json`).
  - Live auf `srv1` und `srv2` verifiziert: `PUT /settings/artifacts/watchdog` + `POST /settings/artifacts/watchdog/check` fuehren jetzt zu konsistentem `watchdog.config` und `watchdog.status`.
- Rest-Risiko:
  - Solange der Artifact-Refresh selbst noch fehlschlaegt bzw. Artefakte fehlen, meldet der Watchdog korrekt `drift`; das ist kein Sicherheitsproblem, sondern Betriebszustand.

---

## S-021 — Cluster-Preflight und RPC-Port waren zu offen (PATCHED, REST-RISIKO 8443)

- Status: **kritische Punkte gepatcht/live gehärtet** (2026-04-26)
- Risiko vorher: **Hoch**
- Risiko nach Fix: **Mittel** wegen weiter öffentlich erreichbarem Legacy-Port `8443`
- Betroffene Server: `srv1.beagle-os.com`, `srv2.beagle-os.com`
- Betroffene Dateien:
  - `beagle-host/services/request_handler_mixin.py`
  - `beagle-host/services/auth_session_http_surface.py`
  - `beagle-host/services/cluster_membership.py`
  - `scripts/harden-cluster-api-iptables.sh` (live erneut fuer `9089` genutzt)
  - `/etc/iptables/rules.v4` auf `srv1` und `srv2`
- Gefundene Ist-Situation:
  - Von extern erreichbar waren `22`, `80`, `443`, `8443`, `9089`.
  - `9088` war bereits peer-gefiltert, `9089` aber noch nicht.
  - `/beagle-api/api/v1/health` lieferte ohne Login detaillierte Betriebsinformationen.
  - `/beagle-api/api/v1/auth/onboarding/status` lieferte ohne Login interne Details wie `completed_by` und `user_count`.
  - Der Cluster-Preflight rief auf Zielservern unauthentifiziert `/health` ab.
- Fix:
  - `9089` auf beiden Hosts mit persistenter iptables-Chain `BEAGLE_CLUSTER_RPC_9089` auf localhost + Peer-IP begrenzt.
  - `/api/v1/health` erfordert jetzt Authentifizierung; nur `/healthz` bleibt als minimaler Liveness-Pfad public.
  - Onboarding-Status gibt public nur noch `pending` und `completed` aus.
  - Cluster-Preflight macht keine unauthentifizierte `/health`-Abfrage mehr; `api_health` wird bis zum echten Remote-Setup-Token als `skipped` markiert.
  - Zielserver-Setup-Code umgesetzt: `POST /api/v1/cluster/setup-code` erzeugt nach Login einen kurzlebigen Einmal-Code, speichert nur den SHA-256-Hash und gibt keine Secrets ins Audit.
  - Leader-Auto-Join umgesetzt: `POST /api/v1/cluster/auto-join` verbindet neue Server per Hostname + Setup-Code; der Zielserver akzeptiert `POST /api/v1/cluster/join-with-setup-code` nur bei gültigem Code.
  - Join-Tokens pruefen jetzt serverseitig ihr Ablaufdatum und werden nach Ablauf verworfen.
  - Cluster-Member-Leave folgt jetzt einem Leader-bestaetigten 2-Phasen-Flow; ein normales Mitglied kann die Leader-Memberliste nicht mehr lokal still ueberschreiben.
- Verifikation:
  - Externer TCP-Test nach Fix: öffentlich erreichbar nur noch `22`, `80`, `443`, `8443`; `9088/9089` nicht mehr extern offen.
  - Public API nach Fix: `/health` -> `401`, `/cluster/status` -> `401`, `/auth/onboarding/status` -> nur `{pending, completed}`.
  - `9089` ohne Client-Zertifikat gab vorher keine Daten heraus (`TLS alert certificate required`), ist jetzt zusaetzlich netzseitig begrenzt.
- Rest-Risiken:
  - `8443` ist weiterhin öffentlich erreichbar und spiegelt Legacy-Download/API-Funktionen. Auth schützt Management-Routen, aber der Port vergrößert die Angriffsfläche.
  - `22` ist öffentlich erreichbar; SSH-Key-Policy/Fail2ban/Allowlist muss separat bewertet werden.
  - `srv2` nutzt derzeit ein self-signed TLS-Zertifikat auf `443/8443`.
- Naechster Schritt:
  - `8443` entweder auf reine Downloads ohne `/beagle-api` reduzieren oder per Firewall schließen, sobald alle Installer-/Download-Pfade auf `443` umgestellt sind.
  - Remote-KVM/libvirt-Preflight nur ueber den setup-code-geschuetzten Zielserverpfad ausfuehren, nicht ueber offene Detail-Endpunkte.

---

Stand: 2026-04-25 (ergänzt: S-020 iptables-Härtung aktiv)

## S-020 — Cluster-Mode: API bindet auf 0.0.0.0 (PATCHED, HARDENED)

- Status: **gepatcht/gehärtet** (2026-04-25)
- Risiko: **Niedrig** (auth + rate-limit + IP-Allowlist auf 9088)
- Betroffene Server: `srv1.beagle-os.com` (46.4.96.80), `srv2.beagle-os.com` (176.9.127.50)
- Betroffene Dateien:
  - `scripts/harden-cluster-api-iptables.sh`
  - `/etc/beagle/beagle-manager.env` (nicht versioniert — lokale Operatorkonfiguration)
  - `/etc/iptables/rules.v4` auf `srv1` und `srv2`
- Beschreibung:
  - Für Cluster-Betrieb muss `BEAGLE_MANAGER_LISTEN_HOST=0.0.0.0` gesetzt sein, damit der andere Node
    die API (Port 9088) für Join-Token-Validierung und Health-Probes erreichen kann.
  - Dadurch war Port 9088 grundsätzlich breit erreichbar.
- Mitigationen aktiv:
  - API-Authentifizierung: alle Management-Endpoints erfordern `Authorization: Bearer` oder Session-Cookie
  - Ausnahmen nur: `/api/v1/cluster/join` (join-token-validiert intern), `/healthz`, öffentliche Endpoints
  - Rate Limiting: 240 Requests/60s pro IP, Lockout nach 5 fehlgeschlagenen Logins (300s)
  - Neue IP-Allowlist-Chain `BEAGLE_CLUSTER_API_9088`:
    - `srv1`: erlaubt `127.0.0.1/32` und `176.9.127.50`, sonst DROP auf tcp/9088
    - `srv2`: erlaubt `127.0.0.1/32` und `46.4.96.80`, sonst DROP auf tcp/9088
  - Neue IP-Allowlist-Chain `BEAGLE_CLUSTER_RPC_9089`:
    - `srv1`: erlaubt `127.0.0.1/32` und `176.9.127.50`, sonst DROP auf tcp/9089
    - `srv2`: erlaubt `127.0.0.1/32` und `46.4.96.80`, sonst DROP auf tcp/9089
  - Persistenz aktiv via `netfilter-persistent`/`iptables-persistent` (Regeln reboot-fest)
- Verbleibende Restrisiken:
  - Public-IP-Transport bleibt ohne VPN grundsätzlich exponiert (trotz Auth + IP-Filter).
  - Empfohlen bleibt ein WireGuard-Mesh und Binding auf das VPN-Interface.
- Nächster Schritt:
  - Optional: automatisches Anwenden der Script-Logik direkt im Cluster-Init/Join-Workflow verdrahten.

---

Stand: 2026-04-29 (ergänzt: Network POST fehlende Authentifizierung gepatcht)

## S-019 — Network POST Endpoints: Fehlende _is_authenticated()-Prüfung (PATCHED)

- Status: **gepatcht** (commit `adbb20f`)
- Risiko: **Mittel** (war — unauthentifizierte Anfragen an Network POST-Endpoints)
- Betroffene Dateien: `beagle-host/bin/beagle-control-plane.py` (do_POST, network-Sektion)
- Beschreibung:
  - Die originalen `do_POST`-Handler für `/api/v1/network/ipam/zones`, `/api/v1/network/ipam/zones/*/allocate`, `/api/v1/network/ipam/zones/*/release`, `/api/v1/network/firewall/profiles`, `/api/v1/network/firewall/profiles/*/apply` hatten kein explizites `_is_authenticated()`-Check.
  - `_authorize_or_respond()` wurde aufgerufen, aber wenn `_auth_principal()` `None` zurückgab (unauthentifiziert + keine Permission konfiguriert), wurde `True` zurückgegeben ohne Authentifizierungsprüfung.
- Fix: Bei Verdrahtung der NetworkHttpSurfaceService in `do_POST` wurde `if not self._is_authenticated():` explizit hinzugefügt.

---

## S-018 — BeagleStream (Sunshine-Fork): Unverschlüsselter LAN-Stream ohne WireGuard

- Status: **architektonisch bekannt**, Mitigation in Plan 01 (GoEnterprise) dokumentiert
- Risiko: **Hoch** (Produktionsumgebungen ohne Verschlüsselung auf dem Streaming-Kanal)
- Betroffene Dateien: `beagle-host/services/sunshine_integration.py`, zukünftig `beagle-stream-server/`
- Beschreibung:
  - Vanilla Sunshine/Moonlight überträgt Video/Audio über UDP ohne Transportverschlüsselung.
  - Im LAN ist ein Angreifer mit physischem Netzwerkzugang in der Lage, Streaming-Traffic mitzulesen oder zu manipulieren (MITM auf UDP-Ebene).
  - Betrifft alle heutigen Beagle-Deployments.
- Mitigation (in Plan 01 GoEnterprise):
  - WireGuard-Mesh: alle Streaming-Verbindungen laufen durch verschlüsselten Tunnel.
  - WireGuard-Latenz-Overhead: **+0.003ms** (gemessen auf srv1, 24.04.2026) — latenz-neutral.
  - `network_mode=vpn_required` in Stream-Policy: Server lehnt Direktverbindungen ohne WireGuard ab.
  - Hardware-Beschleunigung bestätigt: `aes`, `avx2`, `vaes`, `vpclmulqdq` vorhanden auf srv1.
- Nächster konkreter Schritt: `beagle-host/services/wireguard_mesh_service.py` implementieren (Plan 01, Schritt 3).

## S-017 - beagle_curl_tls_args: --pinnedpubkey ohne -k bypasst CA-Verifizierung nicht

- Status: **gefixt** in Repo (2026-04-24)
- Risiko: Mittel (verhinderte TLS-Pinning-Nutzung; kein Sicherheits-Downgrade, aber Pairing-Block)
- Betroffene Datei: `thin-client-assistant/runtime/runtime_value_helpers.sh`
- Beschreibung:
  - `beagle_curl_tls_args` gab bei konfiguriertem Pinned-Pubkey nur `--pinnedpubkey SHA` aus.
  - Bei self-signed Sunshine-Certs (keine CA-Kette) scheiterte curl zuerst an `SSL certificate problem: self-signed certificate` (Error 60), bevor der Pubkey-Check greifen konnte.
  - Effekt: Moonlight-Pairing-API-Calls schlugen fehl; `credentials.env` wurde nicht korrekt evaluiert.
- Fix: `-k` wird nun immer zusammen mit `--pinnedpubkey` ausgegeben (CA-Check bypassen, Pubkey-Pinning bleibt aktiv als Sicherheitsgarantie).
- Verbleibende Note: Mit `-k --pinnedpubkey` schützt nur der Pubkey-Hash; falls Sunshine-Key rotiert wird, muss `PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY` in `credentials.env` ebenfalls aktualisiert werden.

## S-016 - Cluster-Join-Ziel waere als Installer-Secret in breit konsumierten Env-Dateien geleakt

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel
- Betroffene Dateien:
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer-gui`
  - `scripts/install-beagle-host.sh`
  - `scripts/install-beagle-host-postinstall.sh`
  - `scripts/install-beagle-host-services.sh`
- Beschreibung:
  - Mit dem neuen Installer-Join-Dialog aus Plan 07 Schritt 5 muessen Join-Token oder Leader-Ziele durch den Installpfad transportiert werden.
  - Wuerden diese Werte direkt in `host.env`, Proxy-Env oder andere breit gesourcte Runtime-Dateien geschrieben, waeren sie fuer mehr Prozesse/Operator-Pfade sichtbar als noetig.
- Mitigation:
  - Join-Daten werden jetzt in `/etc/beagle/cluster-join.env` mit Modus `0600` persistiert.
  - Allgemeine Runtime-Env-Dateien enthalten nur `BEAGLE_CLUSTER_JOIN_REQUESTED` und den Pfad zur Secret-Datei, nicht das eigentliche Join-Ziel.
  - Der Plain-Mode- und GUI-Installerpfad wurde lokal und auf `srv1.beagle-os.com` mit erfolgreicher State-Erzeugung verifiziert.

## S-015 - Restriktive VDI-Pools waren fuer beliebige `pool:read`-Principals sichtbar

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
  - `beagle-host/services/entitlement_service.py`
  - `scripts/test-vdi-pools-smoke.py`
- Beschreibung:
  - Die Pool-GET-Routen lieferten bisher alle VDI-Pools an jeden authentifizierten Principal mit `pool:read` aus.
  - Dadurch waren Pool-IDs, Modi und Slot-Status restriktiver Pools sichtbar, obwohl dieselben User spaeter bei `POST /allocate` korrekt ein `403 not entitled to this pool` erhielten.
  - Das war ein Informationsleck zwischen Sichtbarkeit und Mutations-Guard.
- Mitigation:
  - `GET /api/v1/pools` filtert restriktive Pools jetzt serverseitig anhand der Entitlements.
  - `GET /api/v1/pools/{pool}`, `/vms` und `/entitlements` maskieren nicht sichtbare Pools als `404 pool not found`.
  - Operator-/Admin-Bearbeiter mit `pool:write` bzw. `*` behalten den Vollzugriff fuer Betrieb und Diagnose.
  - `EntitlementService` fuehrt die explizite Sichtbarkeits-Semantik (`has_explicit_entitlements`, `can_view_pool`) zentral.
  - `scripts/test-vdi-pools-smoke.py` prueft den Fall jetzt reproduzierbar mit echten Bearer-Sessions (Admin vs. berechtigter User vs. unberechtigter User) lokal und auf `srv1.beagle-os.com`.
- Naechster Schritt:
  - Wenn Auth-Principals kuenftig echte Gruppenclaims aus OIDC/SAML/SCIM tragen, denselben Sichtbarkeits-/Allocate-Pfad auch fuer Gruppen-Entitlements live verifizieren.

## S-014 - Audit-Events schrieben Secrets/PII ungeschwaerzt in `old_value` / `new_value`

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel bis Hoch
- Betroffene Dateien:
  - `core/audit_event.py`
  - `beagle-host/services/audit_pii_filter.py`
  - `beagle-host/services/audit_log.py`
  - `beagle-host/services/audit_report.py`
- Beschreibung:
  - Mit dem neuen Audit-Schema konnten sensible Inhalte wie Passwoerter, API-Tokens oder private Schluessel in `old_value` bzw. `new_value` landen.
  - Ohne Redaction waeren diese Daten sowohl lokal im Audit-Log als auch im CSV/JSON-Export sichtbar geblieben.
- Mitigation:
  - Neues Modul `beagle-host/services/audit_pii_filter.py` schwaerzt rekursiv Felder, deren Name `password`, `secret`, `token` oder `key` enthaelt.
  - `core/audit_event.py` wendet die Redaction zentral beim Erzeugen und Normalisieren von Audit-Records auf `old_value` und `new_value` an.
  - Unit-Test deckt Passwoerter, verschachtelte Tokens und private Keys explizit ab.
  - Live auf `srv1.beagle-os.com` per Python-Snippet gegen die deployte Runtime verifiziert (`[REDACTED]`).
- Naechster Schritt:
  - Optional konfigurierbare Pfadlisten/Pseudonymisierung fuer E-Mail, IP und Username ergaenzen, falls regulierte Deployments das verlangen.

## Zweck

- Diese Datei sammelt alle waehrend der laufenden Refactor-Arbeit gefundenen Sicherheitsprobleme, Secret-Leaks, unsicheren Defaults und offenen Hardening-Punkte.
- Jeder neue Fund muss hier mit Status, Auswirkung und naechstem Schritt eingetragen werden.
- Wenn ein Fund im selben Run sicher und reproduzierbar behebbar ist, wird er direkt gepatcht und hier als mitigiert dokumentiert.

## S-001 - Lokale Operator-Dateien waren im Git-Tracking

- Status: mitigiert im Workspace, Shared-Repo-Commit/Pull-Request noch erforderlich
- Risiko: Hoch
- Betroffene Dateien:
  - `AGENTS.md`
  - `AGENTS.md`
- Beschreibung:
  - Beide lokalen Operator-Dateien waren im Git-Tracking und konnten dadurch versehentlich auf GitHub landen.
  - Dadurch besteht ein strukturelles Risiko, dass interne Arbeitsanweisungen, lokale Betriebsdetails oder spaeter eingetragene Zugangshinweise offengelegt werden.
- Mitigation:
  - `.gitignore` wurde um `AGENTS.md` und `AGENTS.md` erweitert.
  - `AGENTS.md` und `AGENTS.md` wurden aus dem Git-Index entfernt und lokal beibehalten.
  - Diese Dateien muessen aus dem Git-Tracking entfernt bleiben.
  - `AGENTS.md` wurde explizit um die Regel erweitert, dass beide Dateien lokal-only sind.
- Naechster Schritt:
  - Sicherstellen, dass die Tracking-Entfernung committed und nach GitHub gepusht wird.

## S-002 - Klartext-Secrets duerfen nicht in versionierte Repo-Dateien

- Status: aktiv als Guardrail
- Risiko: Hoch
- Beschreibung:
  - Im Rahmen von Live-Betrieb, Deployments und Multi-Agent-Arbeit tauchen regelmaessig Zugriffswege, Hostnamen und Credentials auf.
  - Wenn diese als Klartext in versionierten Repo-Dateien landen, entsteht sofort ein Secret-Leak-Risiko fuer GitHub, Releases und Forks.
- Mitigation:
  - Sicherheitsregel in `AGENTS.md` verankert: keine Klartext-Passwoerter oder Zugangsdaten in commitbare Dateien.
  - Lokale Operator-Hinweise duerfen nur in nicht versionierten Dateien stehen.
  - SSH-Zugriff auf `srv1.meinzeug.cloud` erfolgt lokal ueber den Alias `ssh meinzeug` mit lokalem Key statt ueber Repo-dokumentierte Passwoerter.
- Naechster Schritt:
  - Repo gezielt nach weiteren potenziellen Klartext-Secrets, Tokens oder sensiblen Operator-Hinweisen durchsuchen und bereinigen.

## S-003 - Installimage source bundle enthaelt lokale Operator-Dateien

- Status: mitigiert, neu gebaut, verifiziert und als `6.6.9` veroeffentlicht
- Risiko: Hoch
- Betroffene Dateien:
  - `scripts/build-server-installimage.sh`
  - eingebettetes Archiv `/usr/local/share/beagle/beagle-os-source.tar.gz` innerhalb des installimage-Tarballs
- Beschreibung:
  - Der erste Build des neuen Hetzner-installimage-Artefakts hat die lokalen Dateien `AGENTS.md` und `AGENTS.md` in das eingebettete Beagle-Source-Archiv aufgenommen.
  - Dadurch waeren lokale Operator-Hinweise ueber das oeffentlich verteilte installimage-Artefakt weitergegeben worden.
- Mitigation:
  - Builder wurde direkt gepatcht, sodass nur explizit erlaubte Repo-Pfade gebuendelt werden und `AGENTS.md` / `AGENTS.md` nicht mehr Teil des Source-Bundles sind.
  - Das korrigierte `Debian-1201-bookworm-amd64-beagle-server.tar.gz` wurde fuer `6.6.9` neu gebaut, gegen den eingebetteten Source-Tarball verifiziert und auf `beagle-os.com` veroeffentlicht.
  - Die installierte Hetzner-Zielmaschine wurde auf dieses Artefakt aktualisiert.
- Naechster Schritt:
  - GitHub Release Assets nachziehen, sobald ein authentifizierter Release-Upload-Pfad verfuegbar ist.

## S-004 - Public source/server-installer bundles enthielten lokale Operator-Dateien

- Status: mitigiert im Workspace und in `6.6.9` Release-Artefakten, GitHub-Push noch erforderlich
- Risiko: Hoch
- Betroffene Dateien:
  - `scripts/package.sh`
  - `scripts/build-server-installer.sh`
  - `beagle-os-v*.tar.gz`
  - server-installer embedded source archive
- Beschreibung:
  - Neben dem installimage-Pfad waren auch das public source tarball Packaging und der server-installer embedded source bundle fuer lokale Operator-Dateien anfaellig.
  - Dadurch haetten `AGENTS.md` oder `AGENTS.md` ueber allgemeine Release-Artefakte oder Server-Installer-ISO-Inhalte veroeffentlicht werden koennen.
- Mitigation:
  - `scripts/package.sh` und `scripts/build-server-installer.sh` wurden auf explizite erlaubte Repo-Pfade ohne `AGENTS.md` / `AGENTS.md` umgestellt.
  - `beagle-os-v6.6.9.tar.gz` und das `6.6.9` installimage embedded source bundle wurden lokal auf Abwesenheit dieser Dateien geprueft.
- Naechster Schritt:
  - Repo-Aenderungen nach GitHub pushen, damit die Scrubbing-Regeln nicht nur lokal und in den gebauten Artefakten existieren.

## S-005 - Security/TLS WebUI scheiterte auf frischen Hosts an unvollstaendiger Let's-Encrypt Runtime und Service-Sandbox

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel bis Hoch
- Betroffene Dateien:
  - `beagle-host/services/server_settings.py`
  - `beagle-host/systemd/beagle-control-plane.service`
  - `scripts/install-beagle-host-services.sh`
  - `scripts/install-beagle-proxy.sh`
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
- Beschreibung:
  - Die Security-Einstellungen konnten auf einem frisch installierten Standalone-Host kein Let's-Encrypt-Zertifikat ausstellen.
  - Root Cause 1: `certbot` und `python3-certbot-nginx` wurden in den kanonischen Host-/Installer-Pfaden nicht zuverlaessig mitinstalliert.
  - Root Cause 2: selbst nach Paketinstallation scheiterte der API-Pfad innerhalb des gehaerteten `beagle-control-plane.service`-Sandboxes bei `certbot --nginx`, weil Let's-Encrypt- und nginx-Logpfade nicht im gleichen Ausfuehrungskontext nutzbar waren.
- Mitigation:
  - Installpfade wurden auf automatische Installation von `certbot` und `python3-certbot-nginx` erweitert.
  - `server_settings.py` prueft nun explizit auf fehlendes `certbot` bzw. fehlenden nginx-Plugin-Support und liefert klare Fehlerbilder.
  - `server_settings.py` schaltet nginx nach erfolgreicher Zertifikatserstellung jetzt aktiv auf die Let's-Encrypt-Pfade um (`fullchain.pem`/`privkey.pem`), prueft die Konfiguration mit `nginx -t` und laedt nginx neu.
  - Damit wird verhindert, dass ein gueltiges LE-Zertifikat zwar ausgestellt ist, aber weiterhin ein Self-Signed-Zertifikat ausgeliefert wird.
  - TLS-Issuance laeuft bevorzugt ueber einen transienten `systemd-run` Prozess, damit die Funktion mit bestehender Service-Haertung kompatibel bleibt.
  - `ReadWritePaths=` des Control-Plane-Services wurde fuer relevante Let's-Encrypt/nginx-Pfade erweitert.
  - Live auf `srv1.beagle-os.com` verifiziert: externer TLS-Handshake liefert Issuer `Let's Encrypt (E8)`, nginx referenziert LE-Pfade, Status meldet `provider=letsencrypt`, Zertifikat vorhanden, nginx TLS aktiv.
- Naechster Schritt:
  - Den Fix ueber neu gebaute Installer-Artefakte ausrollen und einen Regressionstest fuer den Security/TLS-Pfad ergaenzen.

## S-006 - Control-Plane API ohne harte Gateway-Guards (Rate-Limit/Brute-Force/Error-Schema)

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Hoch
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
  - `scripts/install-beagle-host-services.sh`
- Beschreibung:
  - Die API hatte zuvor kein durchgaengiges Request-Rate-Limit auf allen `/api/*`-Routen.
  - Login-Fehlversuche wurden nicht mit serverseitigem Exponential-Backoff + Lockout begrenzt.
  - Error-Responses waren teilweise ohne einheitliches `code`-Feld.
  - Unbehandelte Exceptions hatten keine zentrale Sanitization-Grenze.
- Mitigation:
  - Python-Middleware-Rate-Limit fuer alle API-Endpunkte implementiert (`BEAGLE_API_RATE_LIMIT_WINDOW_SECONDS`, `BEAGLE_API_RATE_LIMIT_MAX_REQUESTS`).
  - Login-Brute-Force-Schutz mit Exponential-Backoff und Lockout implementiert (`BEAGLE_AUTH_LOGIN_LOCKOUT_THRESHOLD`, `BEAGLE_AUTH_LOGIN_LOCKOUT_SECONDS`, `BEAGLE_AUTH_LOGIN_BACKOFF_MAX_SECONDS`).
  - Access-Token-Default auf 15 Minuten gehaertet (`BEAGLE_AUTH_ACCESS_TTL_SECONDS=900`).
  - Einheitliches Error-Schema durch automatisches `code`-Feld auf Fehler-Payloads ergaenzt.
  - Zentrale Exception-Grenze (`handle_one_request`) liefert sanitisiertes 500-JSON (`internal_error`).
  - Strukturierte JSON-Response-Logs enthalten jetzt `user`, `action`, `resource_type`, `resource_id`.
- Validierung:
  - `srv1`: `/api/v1/auth/me` liefert `401` mit `code=unauthorized`.
  - `srv1`: wiederholte falsche Logins liefern `429` mit `code=rate_limited` und `retry_after_seconds`.
  - `srv1`: bei temporaerem Limit `BEAGLE_API_RATE_LIMIT_MAX_REQUESTS=5` schaltet API reproduzierbar auf `429 rate_limited` nach mehreren Requests.
  - Env-Werte auf `srv1` geprueft und auf Produktionswert (`240`) zurueckgesetzt.
- Naechster Schritt:
  - Refresh-Token auf HTTP-only/SameSite=Strict Cookie-Flow umstellen (aktuell noch offen in GoFuture 20, Schritt 2).

## S-007 - Fehlende serverseitige Payload-Whitelist/Identifier-Validation in Auth-POST-Routen

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel bis Hoch
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
  - `beagle-host/services/auth_session.py`
  - `tests/unit/test_auth_session.py`
- Beschreibung:
  - Mehrere Auth-POST-Routen akzeptierten bislang zusaetzliche oder ungueltige Felder ohne strikte Whitelist-Pruefung.
  - Identifier-Checks waren nicht durchgaengig serverseitig erzwungen (z.B. User-/Role-Namen mit ungueltigen Zeichen).
- Mitigation:
  - Control-Plane hat jetzt Whitelist-Schema-Pruefung fuer zentrale Auth-POST-Routen (`login`, `refresh`, `logout`, `onboarding/complete`, `auth/users`, `auth/roles`).
  - Serverseitige Identifier-Sanitizer in Handler + Auth-Session-Service ergaenzt.
  - `AuthSessionService` erzwingt `USERNAME_PATTERN`/`ROLE_NAME_PATTERN` in `create_user`, `update_user`, `save_role`, `complete_onboarding`, `login`.
  - Unit-Tests um negative Faelle erweitert (`invalid username`, `invalid role name`).
- Validierung:
  - Lokal: `python -m unittest tests.unit.test_auth_session` -> OK.
  - `srv1`: `/api/v1/auth/onboarding/complete` mit `username="bad user"` liefert `400` + `code=bad_request`.
  - `srv1`: `/api/v1/auth/login` mit zusaetzlichem Feld `extra` liefert `400` + `invalid payload: unexpected keys`.

## S-010 - Persistente noVNC-Tokens (kein TTL, nicht single-use)

- Status: behoben in Repo und auf `srv1.beagle-os.com`
- Risiko: Hoch
- Betroffene Dateien:
  - `beagle-host/services/vm_console_access.py`
  - `beagle-host/bin/beagle_novnc_token.py` (neu)
  - `beagle-host/systemd/beagle-novnc-proxy.service`
- Beschreibung: noVNC-Tokens waren persistent pro VM (nie rotiert), wiederverwendbar und ohne TTL. Ein einmal erlangtes Token konnte unbegrenzt lange genutzt werden.
- Mitigation:
  - Pro Console-Öffnung wird jetzt ein frischer 32-Byte-Token generiert (TTL=30s).
  - Tokens werden beim ersten erfolgreichen `lookup()` als verwendet markiert (single-use).
  - Benutzerdefinierter websockify-Plugin `BeagleTokenFile` liest aus JSON-Store statt plaintext-Tokenfile.
  - 8/8 Unit-Tests validiert; live auf `srv1.beagle-os.com` deployed und verifiziert via `journalctl`.

## S-011 - Refresh-Token in localStorage / JSON-Body (kein HttpOnly Cookie)

- Status: behoben in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel-Hoch (XSS-exponiert)
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
- Beschreibung: Refresh-Token war bisher im JSON-Response-Body enthalten, was Clients veranlassen konnte, ihn in localStorage zu speichern (XSS-zugänglich).
- Mitigation:
  - Login und Refresh setzen jetzt `Set-Cookie: beagle_refresh_token=...; HttpOnly; SameSite=Strict; Path=/api/v1/auth; Secure`.
  - `/auth/refresh` liest Token aus Cookie wenn nicht im Body.
  - Logout leert den Cookie via `Max-Age=0`.
  - Fehlgeschlagener Refresh löscht Cookie ebenfalls.

## S-009 - Uneinheitliche systemd-Hardening/CSP-Baseline in Host-Units

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel
- Betroffene Dateien:
  - `beagle-host/systemd/beagle-novnc-proxy.service`
  - `beagle-host/systemd/beagle-artifacts-refresh.service`
  - `beagle-host/systemd/beagle-public-streams.service`
  - `beagle-host/systemd/beagle-ui-reapply.service`
  - `scripts/install-beagle-proxy.sh`
- Beschreibung:
  - Mehrere Beagle-Units hatten keine explizite `CapabilityBoundingSet`-/`RestrictAddressFamilies`-Absicherung.
  - noVNC lief als root obwohl kein privilegierter Port oder root-only capability erforderlich war.
  - CSP im nginx-Proxypfad war ohne explizite `wss:`-Freigabe im `connect-src`.
- Mitigation:
  - Unit-Hardening auf die betroffenen Beagle-Units ausgerollt (`CapabilityBoundingSet=`, `RestrictAddressFamilies=...`).
  - `beagle-novnc-proxy.service` auf non-root `beagle-manager` umgestellt und weiter gesandboxed.
  - CSP im nginx-Proxypfad auf `connect-src 'self' wss:` angepasst, weiterhin ohne `unsafe-inline`/`unsafe-eval`.
- Validierung:
  - `srv1`: `systemctl show beagle-novnc-proxy.service` zeigt `User=beagle-manager`, `CapabilityBoundingSet=` und eingeschraenkte AddressFamilies.
  - `srv1`: `curl -kI https://127.0.0.1/` zeigt den erwarteten CSP-Header mit `wss:`.

## S-008 - Fehlende automatisierte Dependency-Audit-Integration

- Status: mitigiert (Automation vorhanden), Findings offen
- Risiko: Mittel
- Betroffene Dateien:
  - `scripts/security-audit.sh`
  - `.github/workflows/security-audit.yml`
  - `.gitignore`
- Beschreibung:
  - Es fehlte ein reproduzierbarer, regelmaessig laufender CVE-Check fuer Python- und Node-Abhaengigkeiten.
- Mitigation:
  - Neues Skript `scripts/security-audit.sh` hinzugefuegt (`pip-audit` + `npm audit`, Report-Ausgabe nach `dist/security-audit/`).
  - Neuer GitHub-Workflow `.github/workflows/security-audit.yml` mit monatlichem Schedule + manuellem Trigger + Report-Artefakt-Upload.
  - `.gitignore` um `.env` / `.env.*` erweitert.
- Validierung:
  - Lokal ausgefuehrt (`BEAGLE_SECURITY_AUDIT_STRICT=0 scripts/security-audit.sh`).
  - Ergebnis: bekannte Vulnerabilities gemeldet (`pip` im venv; npm audit findings im `beagle-kiosk`-Scope) und als Reports gespeichert.
- Naechster Schritt:
  - `pip` im Runtime-/CI-Umfeld auf gefixte Version anheben,
  - npm findings im `beagle-kiosk` aufloesen oder begruendete Ignore-Liste mit Ablaufdatum einfuehren.

## S-012 - Unsicherer Installer-Debug-SSH-Default (aktiv + Standardpasswort)

- Status: mitigiert in Repo
- Risiko: Hoch
- Betroffene Dateien:
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
- Beschreibung:
  - Der Server-Installer aktivierte Debug-SSH im Live-System per Default (`BEAGLE_SERVER_INSTALLER_DEBUG_SSH_ENABLE=1`) und setzte ein statisches Root-Passwort (`beagle-debug`).
  - Auf exponierten Install-Netzen war damit ein triviales Remote-Login-Risiko vorhanden.
- Mitigation:
  - Debug-SSH ist jetzt standardmäßig deaktiviert (`BEAGLE_SERVER_INSTALLER_DEBUG_SSH_ENABLE=0`).
  - Es gibt kein statisches Standardpasswort mehr (`BEAGLE_SERVER_INSTALLER_DEBUG_SSH_PASSWORD` ist per Default leer).
  - Debug-SSH bleibt nur als explizit gesetzte Operator-Option verfügbar.
- Naechster Schritt:
  - Nach ISO-Rebuild verifizieren, dass Debug-SSH im Live-Boot ohne explizite Aktivierung nicht gestartet wird.

## S-013 - Fehlende verpflichtende Secret-Hygiene-Gates im Repo

- Status: mitigiert in Repo
- Risiko: Hoch
- Betroffene Dateien:
  - `scripts/security-secrets-check.sh` (neu)
  - `.github/workflows/security-secrets-check.yml` (neu)
  - `.security-secrets-allowlist` (neu)
- Beschreibung:
  - Es fehlte ein verpflichtender Repo-Gate, der harte Secret-Leaks (getrackte `.env`, Operator-Dateien, typische Hardcoded-Secret-Muster) frühzeitig blockiert.
- Mitigation:
  - Neues Skript `scripts/security-secrets-check.sh` erzwingt Secret-Hygiene-Regeln und erzeugt Report in `dist/security-audit/secrets-check.txt`.
  - CI-Workflow läuft monatlich + manuell + bei Änderungen an sicherheitsrelevanten Pfaden.
  - Allowlist-Datei für explizite, reviewbare Ausnahmen ergänzt.

## S-014 - OWASP-Baseline-Checks waren nicht reproduzierbar automatisiert

- Status: mitigiert in Repo
- Risiko: Mittel
- Betroffene Dateien:
  - `scripts/security-owasp-smoke.sh` (neu)
- Beschreibung:
  - OWASP Top-10 Abdeckung war primär textuell dokumentiert, aber nicht als reproduzierbarer API-Smoke in den operativen Skripten verfügbar.
- Mitigation:
  - `scripts/security-owasp-smoke.sh` implementiert reproduzierbare Baseline-Checks für zentrale OWASP-relevante Klassen:
    - Broken Access Control (unauth mutating routes -> 401)
    - Identification/Authentication Failures (auth endpoints unauth)
    - Injection/Input Validation (malformed payload -> 400)
    - Security Misconfiguration (unknown route handling)
  - Script ist für lokale und srv1-Läufe vorgesehen.

## S-015 - OIDC-Callback ohne kryptografische ID-Token-Signaturprüfung

- Status: offen (teilweise mitigiert, Follow-up erforderlich)
- Risiko: Mittel bis Hoch
- Betroffene Dateien:
  - `beagle-host/services/oidc_service.py`
  - `beagle-host/bin/beagle-control-plane.py`
- Beschreibung:
  - Der neue OIDC-Flow verarbeitet Authorization-Code + PKCE und extrahiert Claims aus `id_token`/`userinfo`, prüft derzeit aber die Signatur des `id_token` nicht gegen JWKS.
  - Ohne Signaturprüfung ist die Claim-Quelle nicht kryptografisch abgesichert.
- Mitigation (bereits umgesetzt):
  - PKCE (`S256`) + `state`/`nonce` werden serverseitig erzeugt und verwaltet.
  - Endpunkte sind auf explizite OIDC-Aktivierung (`BEAGLE_OIDC_ENABLED`) und konfigurierte IdP-URLs begrenzt.
- Nächster Schritt:
  - JWKS-Fetch + Key-Rotation + RSA/ECDSA-Signaturprüfung für `id_token` implementieren,
  - Claims erst nach erfolgreicher Signatur-, Issuer-, Audience- und Expiry-Validierung akzeptieren.

## S-016 - SCIM-Bearer-Token aktuell als statischer Klartext-Env-Wert

- Status: offen (mitigiert durch separate Token-Grenze, Rotation noch ausstehend)
- Risiko: Mittel
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
  - `beagle-host/services/scim_service.py`
- Beschreibung:
  - SCIM-Zugriff ist korrekt von Session/API-Token getrennt und erfordert `BEAGLE_SCIM_BEARER_TOKEN`,
    aber der Token liegt derzeit als statischer Klartext-Environment-Wert vor.
  - Ohne Rotation/Secret-Backend steigt das Risiko bei Host-Config-Leak oder Operator-Fehlbedienung.
- Mitigation (bereits umgesetzt):
  - eigener SCIM-Auth-Guard (`Authorization: Bearer <scim-token>`) auf allen `/scim/v2/*` Routen,
  - fehlender/falscher Token liefert `401 unauthorized`.
- Nächster Schritt:
  - SCIM-Token-Rotation und optional Hash-at-rest/Secret-Store-Integration ergänzen,
  - SCIM-Mutationsaufrufe strukturiert auditieren.

## S-017 - manager-api-token und weitere Secrets nicht mehr als Klartext-Env (GELOEST)

- Status: geloest (GoAdvanced Plan 03, 2026-04)
- Risiko: Hoch → Geschlossen
- Beschreibung:
  - `BEAGLE_MANAGER_API_TOKEN`, `BEAGLE_AUTH_SECRET` und weitere Laufzeit-Secrets wurden beim
    ersten Start als Klartext-Env-Vars gesetzt oder fehlten vollstaendig.
  - Ohne Rotation/Versioning war ein kompromittierter Token dauerhaft gueltig.
- Mitigation (umgesetzt):
  - `SecretStoreService` (Plan 03 Schritt 2): JSON-Backend unter `/var/lib/beagle/secrets/` (mode 0o600),
    Versions-Tracking, Grace-Period (24h), sofortige Revocation.
  - Auto-Bootstrap (Plan 03 Schritt 3): beim ersten Start wird `secrets.token_hex(32)` generiert
    und nur ins Journal geloggt (Name + Version, KEIN Wert), Env-Var bleibt als Override-Option.
  - Audit-Events (Plan 03 Schritt 4): `secret_accessed` / `secret_rotated` / `secret_revoked` im AuditLog
    — Klartext-Werte landen NICHT im Audit-Log (Test: `test_secret_bootstrap.py::TestBootstrapAuditLogSafety`).
  - Rotation-CLI: `beaglectl secret rotate|list|revoke` (Plan 03 Schritt 5).
  - SecretStore-Kopplung: `_bootstrap_secret()` in `service_registry.py` liest aus SecretStore statt Env.
- Naechster Schritt:
  - Phase 2: optionaler Vault/AWS-Secrets-Manager-Adapter (deferred, Plan 03 Schritt 2 Phase 2).
  - S-016 (SCIM-Token) als naechstes SecretStore-integrieren.

## S-018 - Operator-Debug-Traces koennen Runtime-Secrets in Logs ausgeben

- Status: offen (prozessual erkannt, technischer Guard noch ausstehend)
- Risiko: Mittel bis Hoch
- Betroffene Bereiche:
  - Operator-Ausfuehrung von Shell-Skripten mit `bash -x`
  - Skripte, die `/etc/beagle/*.env` oder andere Secret-/Runtime-Env-Dateien sourcen
- Beschreibung:
  - Shell-xtrace kann expandierte Environment-Werte und Funktionsaufrufe in Terminal-/CI-/Agent-Logs schreiben.
  - Wenn solche Skripte Runtime-Env-Dateien sourcen, koennen Tokens oder andere sensitive Werte in nicht dafuer vorgesehene Logs gelangen.
  - In diesem Run wurden keine Secret-Werte in Repo-Dateien dokumentiert; der Fund betrifft die Arbeitsweise und kuenftige Reproduzierbarkeit.
- Naechster Schritt:
  - Operator-Runbooks und kritische Skripte so haerten, dass Secret-sourcende Abschnitte `set +x` erzwingen.
  - Optional einen Shellcheck-/grep-Smoke ergaenzen, der `bash -x`/`set -x` in Kombination mit `/etc/beagle/*.env` markiert.
  - WebUI-/Job-Logs duerfen Secret-Felder nur redacted anzeigen.
