# 01 - Security Gates fuer Enterprise-GA

Stand: 2026-04-27  
Ziel: Beagle OS so haerten, dass Firmen es nicht nur testen, sondern kontrolliert produktiv einsetzen koennen.

---

## Gate S1 - Auth und Session-Sicherheit

- [ ] Login-Flow per Browser und API reproduzierbar testen: Erfolg, falsches Passwort, Rate-Limit, Logout, Session-Ablauf.
- [ ] Refresh-Token nicht dauerhaft XSS-exponiert in unsicheren Browser-Speichern halten oder Risiko explizit mitigieren.
- [ ] Session-Cookies/Token mit `Secure`, `HttpOnly` wo moeglich, SameSite und kurzer TTL betreiben.
- [ ] Passwort-/Bootstrap-Reset mit Audit-Event und Einmal-Token absichern.
- [ ] Brute-Force-Schutz mit reproduzierbarem Test nachweisen.

Abnahme:

- [ ] Chrome-DevTools-Login-Smoke auf Zielhost ohne `500`, ohne Console-Fehler der Auth-Pfade.
- [ ] API-Smoke fuer `/auth/login`, `/auth/me`, `/auth/logout`, Refresh und Expiry.
- [ ] Security-Findings S-006, S-011, S-020 auf Status `PATCHED` oder dokumentiertes Restrisiko.

---

## Gate S2 - Secrets und Token-Hygiene

- [ ] Keine Klartext-Secrets in Repo, Release-Artefakten, Installimage-Bundles oder downloadbaren Skripten.
- [ ] Manager-/Installer-/Endpoint-Tokens haben Scope, TTL, Rotation und Audit.
- [ ] SCIM/OIDC/SAML-Secrets in SecretStore oder geschuetzter Runtime-Konfiguration halten.
- [ ] Operator-Dateien wie `AGENTS.md` bleiben lokal und werden nicht released.
- [ ] Secret-Scan in CI und vor Release ausfuehren.

Abnahme:

- [ ] `scripts/security-audit.sh` gruen oder dokumentierte Ausnahmen.
- [ ] Release-Tarballs und Installimage-Bundles auf bekannte Secret-Muster gescannt.
- [x] Downloadbare Installer enthalten nur scoped write-only Installer-Log-Tokens. Lokal per `tests/unit/test_installer_script.py` und `tests/unit/test_installer_log_service.py` validiert.

---

## Gate S3 - TLS, Zertifikate und Transport

- [x] Oeffentliche WebUI/API nur ueber `443`. Lokal per `tests/unit/test_public_download_url_regressions.py` validiert; Default-URLs lassen `443` weg.
- [x] Keine `8443`-Referenzen in Download-Artefakten, Status-JSON, WebUI-Config oder VM-spezifischen Skripten. Repo-seitig normalisiert; verbleibende Host-Artefakte werden ueber `scripts/check-beagle-host.sh` geprueft.
- [x] `srv1` Host-Firewall ist als Beagle-nftables-Guard aktiv: oeffentlich `22/80/443`, Cluster-Ports `9088/9089` peer-/bridge-lokal, VM-Forwarding nur Egress oder explizites DNAT. Validiert per `scripts/check-beagle-host.sh` und externer Portprobe am 2026-04-27.
- [ ] TLS-Zertifikatsausstellung und Erneuerung auf frischem Host testen.
- [ ] Interne Cluster-Kommunikation mit mTLS oder klar dokumentierter Allowlist betreiben.
- [ ] `curl -k` nur in explizit erlaubten Testpfaden, nicht in Produktivpfaden.

Abnahme:

- [x] `scripts/check-beagle-host.sh` erkennt keine `8443`-Reste auf `srv1`.
- [x] Browser-Zertifikatskette auf `srv1` ohne manuelle Ausnahme gueltig; Chrome DevTools lud die WebUI bis zum Login-Dialog ohne Console-Fehler.
- [ ] `security-tls-check` in GitHub Actions gruen.

---

## Gate S4 - RBAC und Mandantenfaehigkeit

- [ ] Jede mutierende API-Route benoetigt Authentisierung und passende Permission.
- [ ] Rollen `admin`, `operator`, `kiosk_operator`, read-only und tenant-scoped Nutzer browserseitig testen.
- [ ] Pool-, Session-, VM- und Audit-Sichtbarkeit tenant-/role-scoped validieren.
- [ ] Built-in-Rollen duerfen nicht versehentlich geloescht oder unsicher erweitert werden.
- [ ] Audit-Events duerfen keine Secrets oder PII unredacted speichern.

Abnahme:

- [ ] RBAC-Regressions fuer VM-Power, Kiosk-Sessions, Pools, IAM und Audit gruen.
- [ ] Browser-Smoke mit Nicht-Admin-Rolle zeigt keine Admin-Aktionen.
- [ ] Audit-Export enthaelt Redaction fuer Secrets.

---

## Gate S5 - noVNC, Console und Remote-Zugriff

- [ ] Console-Tokens sind kurzlebig, scoped und auditierbar.
- [ ] noVNC-Zugriff wird an VM-, Rolle- und Session-Kontext gebunden.
- [ ] Keine persistenten globalen Console-Tokens ohne TTL.
- [ ] SSH-/Tunnel-User sind eingeschraenkt und haben keine interaktive Shell ausserhalb des vorgesehenen Pfads.
- [ ] Console-Start/Fehler werden in WebUI sauber angezeigt.

Abnahme:

- [ ] Token nach Ablauf nicht mehr verwendbar.
- [ ] Nicht berechtigter Nutzer bekommt `403`.
- [ ] Console-Launch im Browser ohne DevTools-Fehler.

---

## Gate S6 - Streaming und Zero Trust

- [ ] Enterprise-Piloten nutzen WireGuard-Mesh oder gleichwertig verschluesselten Transport.
- [ ] Thin-Client Enrollment erzeugt eigene Schluessel; Private Keys verlassen das Geraet nicht.
- [ ] Broker erzwingt Policy, Pool-Zugehoerigkeit und Session-Status vor Stream-Start.
- [ ] Sunshine/Moonlight-Pairing ist nachvollziehbar und nicht manuell unsicher.
- [ ] Stream-Health und Session-Ende werden auditierbar erfasst.

Abnahme:

- [ ] Enrollment -> Mesh -> Broker -> Stream End-to-End-Smoke.
- [ ] Stream ohne gueltiges Endpoint-/Session-Token wird abgelehnt.
- [ ] Stream-Persistenz ueber Reboot ohne manuelle Firewall-/Route-Hotfixes validiert.

---

## Gate S7 - Update, Supply Chain und Artefakte

- [ ] GitHub Release zeigt aktuelle Zielversion als `latest`.
- [ ] Artefakte haben `SHA256SUMS`, SBOM und optional Signaturen.
- [ ] Repo-Auto-Update kann aktualisieren und danach Artefakte konsistent regenerieren.
- [ ] Artifact-Writer sind gelockt, damit ISO/Payload/Status nicht parallel inkonsistent geschrieben werden.
- [ ] Rollback auf letzte bekannte gute Version ist getestet.

Abnahme:

- [ ] `scripts/validate-project.sh` gruen.
- [ ] GitHub Actions: tests, lint, security checks, release gruen.
- [ ] `beagle-downloads-status.json` passt zu echten Dateigroessen und Checksummen.

---

## Gate S8 - Externe Security-Pruefung

- [ ] Threat Model fuer WebUI, Control Plane, Thin Client, Installer, Cluster und Streaming erstellen.
- [ ] Externen Pentest oder mindestens unabhaengigen Code-/Infra-Review durchfuehren.
- [ ] Kritische Findings vor R4 schliessen.
- [ ] Mittlere Findings mit Fixdatum oder akzeptiertem Restrisiko dokumentieren.
- [ ] Abschlussbericht in nicht-oeffentlicher Betreiber-Doku ablegen.

Abnahme:

- [ ] Keine offenen kritischen Findings.
- [ ] Alle akzeptierten Restrisiken haben Owner, Ablaufdatum und Mitigation.
