# Enterprise Gap List

Stand: 2026-05-02

Diese Liste ist aus `fork.md`, `docs/checklists/*`, `docs/STATUS.md`,
`docs/MASTER-PLAN.md`, `docs/refactor/06-next-steps.md`,
`docs/refactor/08-todo-global.md` und `docs/refactor/11-security-findings.md`
konsolidiert.

## P0 - Blocker vor Firmen-Pilot

- [ ] Frische Server-Installation aus aktuellem Release-Artefakt auf leerem Host beweisen.
  - Akzeptanz: Erst-Boot erreicht WebUI ohne manuelle Hotfixes.
  - Akzeptanz: `scripts/check-beagle-host.sh` ist direkt nach Clean-Install gruen.
  - Quelle: `docs/checklists/05-release-operations.md`, R1.

- [ ] WebUI-VM-Provisioning fuer neue VMs reproduzierbar abschliessen.
  - Akzeptanz: Ubuntu-Autoinstall, Firstboot, Abschluss-Callback, automatischer Reboot, Desktop-Login und KDE/Beagle-Cyberpunk-Profil funktionieren.
  - Akzeptanz: VM meldet `installed`/`ready` statt dauerhaft `installing`.
  - Quelle: `docs/refactor/06-next-steps.md`, VM100-Pfad.

- [ ] BeagleStream-End-to-End mit echter VM und echtem Thinclient abschliessen.
  - Akzeptanz: Thinclient bootet, enrollt, aktiviert WireGuard, ruft `/api/v1/streams/allocate` auf und zeigt den Desktop.
  - Akzeptanz: keine manuelle PIN-Eingabe, kein Legacy-Direct-Stream-State fuer VM-Sticks.
  - Quelle: `fork.md`, `docs/checklists/02-streaming-endpoint.md`, `docs/refactor/08-todo-global.md`.

- [ ] WireGuard-Stream-Latenz mit Messwerten belegen.
  - Akzeptanz: Thinclient + VM-Node Ping <= raw + 0.01 ms.
  - Akzeptanz: Stream durch Tunnel <= direct + 0.1 ms.
  - Quelle: `docs/checklists/02-streaming-endpoint.md`.

- [ ] Backup einer echten VM-Disk auf frischem oder zweitem Host restoren.
  - Akzeptanz: Restore bootet, Datenhash stimmt, Runbook ist aktualisiert.
  - Quelle: `docs/checklists/01-platform.md`, `docs/checklists/05-release-operations.md`.

## P1 - Blocker vor bezahltem Pilot

- [ ] Cluster-Smoke auf zwei echten Nodes fahren.
  - Akzeptanz: Join, Drain, Failover, Fencing/HA-Manager und Session-Handover laufen auf Hardware.
  - Quelle: `docs/checklists/05-release-operations.md`, R2.

- [ ] Storage-Hardware-Gates validieren.
  - Akzeptanz: ZFS und Ceph oder der bewusst gewaehlte produktive Storage-Pfad sind auf Hardware getestet.
  - Akzeptanz: Quotas und Placement verhalten sich unter Last erwartbar.
  - Quelle: `docs/checklists/01-platform.md`.

- [ ] Runbooks live validieren.
  - Akzeptanz: Installation, Update, Rollback, Backup/Restore, Incident und Pilot wurden mindestens einmal gegen echte Hosts durchgespielt.
  - Quelle: `docs/runbooks/*`, `docs/checklists/05-release-operations.md`.

- [ ] Update und Rollback aus Release-Artefakten beweisen.
  - Akzeptanz: Update von Vorversion auf Zielversion laeuft automatisch.
  - Akzeptanz: Rollback/Restore bei fehlerhaftem Update ist dokumentiert und getestet.
  - Quelle: `docs/checklists/05-release-operations.md`.

## P2 - Blocker vor Enterprise-Angebot

- [ ] Externer Security-Review/Pentest ohne kritische Findings.
  - Akzeptanz: Scope, Testfenster, Bericht und Nachfix-Nachweis liegen vor.
  - Quelle: `docs/checklists/03-security.md`, `docs/checklists/05-release-operations.md`.

- [ ] Offene Security-Findings schliessen oder bewusst akzeptieren.
  - OIDC: JWKS-Fetch, Key-Rotation, Signatur-, Issuer-, Audience- und Expiry-Pruefung.
  - SCIM: Token-Rotation und SecretStore-Integration.
  - Operator-Debug: Guard gegen Secret-Leaks bei `bash -x` und Skript-Debugging.
  - Quelle: `docs/refactor/11-security-findings.md`.

- [ ] GPU-R3 abschliessen.
  - Akzeptanz: NVENC-/Streaming-Session mit Latenz- und Qualitaetsmesswerten.
  - Akzeptanz: VFIO-Konfiguration ueberlebt Host-Reboot.
  - Akzeptanz: vGPU/MDEV nur mit echter Hardware/Lizenz als bestanden markieren.
  - Quelle: `docs/checklists/01-platform.md`, `docs/checklists/05-release-operations.md`.

- [ ] UX/i18n/Mobile-Gates schliessen.
  - Akzeptanz: alle zentralen WebUI-Strings laufen ueber `t()`.
  - Akzeptanz: Lighthouse Mobile > 90 und Accessibility > 90.
  - Akzeptanz: Breakpoints 360/600/900/1200 und Touch-Targets >= 44px.
  - Quelle: `docs/checklists/04-quality-ci.md`.

## P3 - Enterprise-Ausbau

- [ ] WebRTC-Modus fuer Browser-Streaming.
- [ ] BeagleStream Native Protocol.
- [ ] Vault/AWS-Secrets-Manager-Adapter.
- [ ] Predictive Scheduling auf Mehr-Node-Pool validieren.
- [ ] Endpoint-Update-Architektur in Hardware-Test-Matrix validieren.
- [ ] Optional: vGPU/MDEV-Produktpfad mit Lizenzmodell und Hardware-Kompatibilitaetsliste.

