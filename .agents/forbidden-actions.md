# Forbidden Actions

Der Agent darf nicht:

- Secrets, Tokens, Passwoerter, private Keys oder sensible `.env`-Werte committen.
- Lizenzdateien ohne explizite Freigabe aendern.
- Produktionsserver mutieren, wenn die Aenderung nicht reproduzierbar im Repo landet.
- Destruktive Kommandos ohne Schutz ausfuehren (`rm -rf` auf produktiven Pfaden, harte Resets etc.).
- Unbegruendete Grossrefactorings/Architekturwechsel in einem Schritt durchfuehren.
- Kaputte Tests ignorieren oder stillschweigend deaktivieren.
- Neue Proxmox-Kopplung einfuehren (`qm`, `pvesh`, `/api2/json`, `PVEAuthCookie`).
- Direkt auf `main` committen (Ausnahme: expliziter, dokumentierter Notfall fuer Agenten-Konfiguration).
