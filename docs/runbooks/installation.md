# Runbook — Installation

**Status**: Skelett · **Letzte Validierung**: —

Ziel: Frischer Beagle-OS-Host (bare metal oder Hetzner Cloud/Dedicated) ist nach
Abarbeitung dieser Schritte mit allen Default-Diensten erreichbar und passiert
`scripts/check-beagle-host.sh`.

## 1. Voraussetzungen

- [ ] Hardware-Profil ueberprueft (CPU mit VT-x/AMD-V, mind. 16 GB RAM, IOMMU bei GPU-Plaenen)
- [ ] Netzwerk-Plan (statische IP oder DHCP, DNS, optional VLAN)
- [ ] Hostname + FQDN festgelegt
- [ ] TLS-Strategie: Let's Encrypt vs. eigene CA vs. self-signed
- [ ] Admin-Credentials sicher abgelegt (Vault/Passwortmanager — **nie** in Repo)

## 2. Installations-Pfade

| Pfad | Verwendung | Skript |
|---|---|---|
| Bare-Metal-ISO (USB) | Eigene Hardware, On-Prem | `scripts/build-server-installer.sh` → ISO → boot |
| Hetzner installimage | Hetzner Dedicated | `scripts/build-server-installimage.sh` → Tarball → installimage |
| Hetzner Cloud | Hetzner Cloud-Server (Ubuntu base) | siehe [`../deployment/hetzner-installimage.md`](../deployment/hetzner-installimage.md) |

## 3. Schritte (Bare-Metal-ISO)

1. ISO bauen oder Release-ISO herunterladen + SHA256SUMS pruefen.
2. USB-Stick beschreiben (`dd` oder Etcher).
3. Host booten, im TUI Sprache/Tastatur/Disk/Netzwerk waehlen.
4. Erst-Boot abwarten (`firstboot.service` schliesst Provisionierung ab).
5. Im Browser `https://<host>/` oeffnen, Onboarding-Workflow durchlaufen.
6. Admin-Account anlegen, MFA empfohlen.
7. `scripts/check-beagle-host.sh` lokal ausfuehren — alle Checks gruen.

## 4. Smoke-Tests nach Installation

- [ ] `https://<host>/healthz` antwortet `200`
- [ ] Login funktioniert, Dashboard laedt ohne Console-Fehler
- [ ] `virsh list --all` (auf dem Host) zeigt erwartete Default-VMs
- [ ] `systemctl status beagle-control-plane.service` = `active (running)`
- [ ] TLS-Zertifikat gueltig + alle 7 Security-Header gesetzt (`curl -sI https://<host>/ | grep -iE 'strict-transport|content-security-policy|x-frame|x-content-type|referrer|permissions-policy|cross-origin'`)

## 5. Rollback

Bei Fehlschlag siehe [`rollback.md`](rollback.md).

## 6. Befund-Felder

- Datum:
- Operator:
- Host:
- Installations-Pfad:
- Dauer:
- Beobachtete Probleme:
- Eingetragen in `checklists/05-release-operations.md`:
