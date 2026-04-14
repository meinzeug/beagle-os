# Beagle OS Refactor - Next Steps

Stand: 2026-04-14

Hinweis: Rebuild und Reattach der gehaerteten Server-Installer-ISO auf `beagleserver` sind abgeschlossen; Fokus liegt jetzt auf Security-E2E-Verifikation auf frischem Install.

## Naechste 10 konkreten Schritte
1. Browser-E2E auf Live-Host fahren: nach absichtlichem Token-Invalidieren muss die UI sauber auf Login zurueckfallen (kein 401-Polling-Loop).
2. Refresh-Token-Flow E2E validieren: abgelaufener Access-Token muss ueber `/auth/refresh` transparent erneuert werden (JSON + Blob-Downloads).
3. Security-E2E: Trusted-Origin-Guard pruefen (fremde API-Origin darf keine Bearer-Requests aus der UI erhalten).
4. Security-E2E: `allowHashToken` Default-Off validieren (Token aus URL-Hash wird ohne explizites Opt-In ignoriert).
5. Security-E2E: `allowAbsoluteApiTargets` Default-Off validieren (absolute API-Targets muessen im Default geblockt sein).
6. Security-E2E: Bearer-only Header-Pfad pruefen (Legacy-Header nur bei explizitem Opt-In senden).
7. Installer-Security-E2E: frischen ISO-Install booten und mit `ss -tulpen` + externem Portscan verifizieren, dass nur 22/443/8443 (plus optional 8006 im Proxmox-Modus) erreichbar sind.
8. Installer-Security-E2E: SSH-Hardening verifizieren (`PasswordAuthentication no` default, fail2ban aktiv, nftables aktiv, sysctl-hardening geladen).
9. Timeout-Verhalten im Browser pruefen: API- und Download-Timeouts muessen als klare Nutzerfehler erscheinen statt stiller Hangs.
10. Logout-E2E validieren: `/auth/logout` revocation und anschliessender Session-Clear in UI inkl. Poll-Stop.

## Reihenfolgeprinzip
- Erst Security Backbone (AuthN/AuthZ/Audit), dann Feature-Ausbau.
- Jede neue Funktion sofort role-gated und auditierbar.
- Manuelle Build-/Runtime-Smokes sind aktuell gruen; als naechster Schritt die Checks reproduzierbar automatisieren.
