# 04 - Release Pipeline und Artefakt-Freigabe

Stand: 2026-04-27  
Ziel: Release-Artefakte muessen aktuell, nachvollziehbar, pruefbar und selbstheilend sein.

---

## Gate R1 - Version und GitHub Release

- [ ] `VERSION` entspricht Zielversion.
- [ ] Git-Tag zeigt auf den finalen Commit.
- [ ] GitHub `latest` Release zeigt auf den finalen Tag.
- [ ] Kein alter `6.x` Release bleibt als sichtbarer aktueller Stand stehen.
- [ ] Release Notes enthalten Security-/Breaking-/Upgrade-Hinweise.

Abnahme:

- [ ] GitHub API `releases/latest` liefert Zielversion.
- [ ] Release-Workflow ist gruen.

---

## Gate R2 - Artefakte

- [ ] Server-Installer-ISO vorhanden.
- [ ] Server-Installimage-Tarball vorhanden.
- [ ] Thin-Client-Installer-ISO vorhanden.
- [ ] USB Bootstrap/Payload vorhanden.
- [ ] Linux- und Windows-Installer-Skripte vorhanden.
- [ ] `latest`- und versionierte Dateien zeigen auf dieselbe Zielversion.
- [ ] Alte versionierte Thin-Client-Downloads werden nicht weiter im Host-Index angeboten.

Abnahme:

- [ ] `SHA256SUMS` passt zu allen veroeffentlichten Dateien.
- [ ] `beagle-downloads-status.json` passt zu Dateigroessen, Checksummen und URLs.

---

## Gate R3 - SBOM, Signaturen und Provenance

- [ ] SBOM fuer Python-/Node-/Release-Artefakte erzeugen.
- [ ] `SHA256SUMS` signieren, wenn GPG-Key verfuegbar ist.
- [ ] Cosign/Sigstore-Bundle erzeugen, wenn Workflow-Umgebung es erlaubt.
- [ ] Release-Manifest mit inkludierten und ausgelassenen Assets erzeugen.
- [ ] Release-Assets duerfen keine kollidierenden Basenames haben.

Abnahme:

- [ ] Root-`SHA256SUMS` ist das autoritative Manifest.
- [ ] SBOM-interne Checksummen kollidieren nicht mit Release-Asset-Namen.

---

## Gate R4 - Host-Downloads und Self-Heal

- [ ] `scripts/prepare-host-downloads.sh` erzeugt konsistente Downloads.
- [ ] `scripts/package.sh` und `prepare-host-downloads.sh` halten gemeinsamen Artifact-Lock.
- [ ] Repo-Auto-Update laeuft durch und startet Artifact-Refresh.
- [ ] Artifact-Refresh laeuft durch und erzeugt keinen Checksum-Drift.
- [ ] WebUI zeigt Update-/Artifact-Status korrekt.
- [ ] `8443` bleibt nach Self-Heal entfernt.

Abnahme:

- [ ] Nach Auto-Update: `scripts/check-beagle-host.sh` gruen.
- [ ] Oeffentliche Downloads `200`.
- [x] Download-Skripte enthalten Installer-Log-Hooks und keine Admin-Credentials. Lokal per `tests/unit/test_installer_script.py` und `tests/unit/test_installer_log_service.py` validiert.

---

## Gate R5 - Rollback

- [ ] Letzte bekannte gute Version wird gespeichert.
- [ ] Rollback-Script oder dokumentierter manueller Rollback-Pfad existiert.
- [ ] Rollback stellt WebUI/API/Downloads wieder her.
- [ ] Rollback laesst Datenbanken/State-Dateien nicht inkonsistent zurueck.
- [ ] Rollback wird vor R4 mindestens einmal real getestet.

Hardware:

- H1 fuer Control-Plane-Rollback.
- H3 fuer Host-/VM-/Artifact-Rollback.
