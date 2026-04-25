# Next Steps

## Stand (2026-05-XX) -- HandlerMixin Extraction committed (03bd203)

**Zuletzt erledigt**:
- GoFuture Gate: alle 20 Plaene (docs/gofuture/) abgeschlossen (d588939)
- service_registry.py extrahiert: beagle-control-plane.py 4964 -> 1627 LOC (e2e4c38)
- request_handler_mixin.py extrahiert: beagle-control-plane.py 1627 -> 899 LOC (03bd203)
- **Kumulativ: 6151 -> 899 LOC = -85%**
- 778 Unit-Tests bestanden (9 pre-existing GPU-Failures), 31/31 Smoke-Checks auf srv1

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
