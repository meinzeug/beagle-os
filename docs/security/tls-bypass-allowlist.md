# TLS Bypass Allowlist

Jeder Eintrag dokumentiert eine explizit erlaubte Ausnahme von der "kein --insecure / curl -k"-Regel.
Neue Eintraege benoetigen Code-Review-Genehmigung.

| # | Datei | Zeile | Begruendung | Ablauf / Cleanup-Plan |
|---|-------|-------|-------------|----------------------|
| 1 | `server-installer/live-build/.../beagle-live-server-bootstrap` | ~122 | Live-Installer-Bootstrap: Beagle-Proxy ist zu diesem Zeitpunkt gerade erst gestartet und hat noch kein gueltiges Zertifikat. Nur interne Loopback-Verbindung (127.0.0.1). | Cleanup: wenn Let's-Encrypt/ACME im Bootstrap-Flow integriert ist, diesen Call auf CA-Pinning umstellen. |
| 2 | `scripts/test-server-installer-live-smoke.sh` | ~117 | Smoke-Test gegen frischen Installer ohne vorhandenes Zertifikat. Nur bei gesetztem `BEAGLE_TLS_SKIP=1`. | Cleanup: mit Plan 09 (CI-Pipeline) automatischen Zertifikat-Generierungsschritt im Test-Harness einbauen. |
| 3 | `scripts/ensure-vm-stream-ready.sh` | ~282 | Sunshine-API verwendet Self-Signed-Cert; `--pinnedpubkey` liefert die cryptographische Garant. Das `--insecure` schaltet nur Hostname-Check aus, nicht die Pubkey-Verifizierung. | Cleanup: wenn Sunshine-Cert von Beagle-CA signiert wird, auf `--cacert "$HOST_TLS_CERT_FILE"` umstellen. |
| 4 | `scripts/check-beagle-health.sh` | ~113, ~114, ~151 | Health-Probes gegen lokale/self-signed Control-Plane- und Session-Endpoints. | Cleanup: auf signierte interne Zertifikate umstellen, sobald die lokale CA in allen Hosts ausgerollt ist. |
| 5 | `scripts/test-moonlight-appname-smoke.sh` | ~36 | Lokaler Sunshine-Smoke-Test gegen Selbstsignierung auf einem isolierten Testhost. | Cleanup: Test-Harness mit lokaler CA oder gepinntem Zertifikat erweitern. |
| 6 | `scripts/test-sunshine-selfheal-smoke.sh` | ~101 | Lokaler Selbstheilungs-Smoke gegen Sunshine mit selbstsigniertem Zertifikat. | Cleanup: auf internen CA-Trust umstellen, wenn der Host-Zertifikatsweg produktiv ist. |
| 7 | `scripts/test-stream-server-vm-register-smoke.py` | ~124, ~126, ~128 | Stream-API-Smoke gegen lokale/self-signed Endpoints im VM-Lab. | Cleanup: Testumgebung mit vertrauenswürdigem internen Zertifikat ausstatten. |
| 8 | `scripts/test-stream-persistence-reboot-smoke.sh` | ~133 | Post-Reboot-Stream-Probe gegen lokalen Sunshine-Endpoint mit self-signed TLS. | Cleanup: auf interne CA oder gepinntes Zertifikat umstellen. |
| 9 | `scripts/ops/reset-srv1-admin-password.sh` | ~72 | Lokales Admin-Reset-Skript gegen die lokale Control-Plane auf `https://localhost`. | Cleanup: nur fuer Wartung auf dem Zielhost; mittelfristig durch signierte lokale CA absichern. |
| 10 | `scripts/test-streaming-quality-smoke.py` | ~234 | Guest-exec Loopback-Smoke gegen Sunshine auf `127.0.0.1` mit self-signed TLS. | Cleanup: sobald Sunshine intern signiert ist, `--insecure` entfernen. |

## Hinweis zur CI-Pruefung

Die Datei `.github/workflows/security-tls-check.yml` prueft auf `curl.*--insecure` und `curl.*-k\b` ausserhalb von Allowlist-Eintraegen. Allowlist-Eintraege werden mit dem Kommentar `# tls-bypass-allowlist: ...` markiert und vom CI ausgenommen.
