# Next Steps

## Stand (2026-04-25) — Multi-Node Cluster: srv1 + srv2 verbunden

**Zuletzt erledigt**:
- GoFuture Gate: alle 20 Pläne (docs/gofuture/) abgeschlossen (d588939)
- `service_registry.py` extrahiert: `beagle-control-plane.py` 4964 → 1627 LOC (e2e4c38)
- `request_handler_mixin.py` extrahiert: `beagle-control-plane.py` 1627 → 899 LOC (03bd203)
- **Multi-Node Cluster**: srv1 (46.4.96.80) + srv2 (176.9.127.50) in Cluster verbunden
  - `BEAGLE_MANAGER_LISTEN_HOST=0.0.0.0` auf beiden Servern gesetzt
  - members.json gefixte URLs (war: 127.0.0.1, jetzt: echte IPs)
  - stales "node-b" entfernt
  - srv2 via Join-Token beigetreten: `3/3 nodes online, 0 unreachable`

---

### Verbleibende Punkte (nach Priorität)

1. **Cluster: Hardware-Ressourcen (mem/maxmem/maxcpu)** — srv1 und srv2 zeigen `mem:0, maxmem:0, maxcpu:0`.
   Der Provider liest diese Werte anscheinend nur für den lokalen libvirt-Node (`beagle-0`).
   Beagle-Cluster-Nodes brauchen eine eigene Ressourcen-Abfrage.

2. **Plan 09 Schritt 6**: Branch-Protection-Regeln in GitHub repository settings aktivieren.
   _Manueller Schritt im GitHub UI._

3. **Hardware-abhängige Tests**: Live-Migration (Plan 07), NFS-Backend (Plan 08),
   Thin-Client-Boot / A-B / TPM / Kiosk (Plan 19).

4. **Cluster-Sicherheit (optional Härtung)**: iptables-Regel für Port 9088 nur srv1↔srv2
   (Details in `docs/refactor/11-security-findings.md` S-020).

5. **GoEnterprise: VM Stateless Reset** — `providers/beagle/libvirt_provider.py`: `reset_vm_to_snapshot()`

6. **GoEnterprise: RBAC kiosk_operator** — Rolle + Berechtigungsprüfung in IAM

---

### Verbleibende Punkte (nach Prioritaet)

1. **Plan 09 Schritt 6**: Branch-Protection-Regeln in GitHub repository settings aktivieren.
   Manueller Schritt im GitHub UI.

2. **Hardware-abhaengige Tests**: Bei erstem echten Multi-Node-Setup validieren:
   - Live-Migration (Plan 07)
   - NFS-Backend (Plan 08)
   - Thin-Client-Boot / A-B / TPM / Kiosk (Plan 19)

3. **GoEnterprise: VM Stateless Reset** -- providers/beagle/libvirt_provider.py: reset_vm_to_snapshot()
   (geplant in docs/goenterprise/03-gaming-kiosk-pools.md)

4. **GoEnterprise: RBAC kiosk_operator** -- Rolle + Berechtigungspruefung in IAM
   (geplant in docs/goenterprise/03-gaming-kiosk-pools.md)

5. **Proxmox-Cleanup vollenden** (Plan 05): providers/proxmox/ und proxmox-ui/ loeschen, sobald alle
   verbleibenden Referenzen in beagle-host/services/ auf providers/beagle/ migriert sind.
