# TLS Bypass Allowlist

Jeder Eintrag dokumentiert eine explizit erlaubte Ausnahme von der "kein --insecure / curl -k"-Regel.
Neue Eintraege benoetigen Code-Review-Genehmigung.

| # | Datei | Zeile | Begruendung | Ablauf / Cleanup-Plan |
|---|-------|-------|-------------|----------------------|
| 1 | `server-installer/live-build/.../beagle-live-server-bootstrap` | ~122 | Live-Installer-Bootstrap: Beagle-Proxy ist zu diesem Zeitpunkt gerade erst gestartet und hat noch kein gueltiges Zertifikat. Nur interne Loopback-Verbindung (127.0.0.1). | Cleanup: wenn Let's-Encrypt/ACME im Bootstrap-Flow integriert ist, diesen Call auf CA-Pinning umstellen. |
| 2 | `scripts/test-server-installer-live-smoke.sh` | ~117 | Smoke-Test gegen frischen Installer ohne vorhandenes Zertifikat. Nur bei gesetztem `BEAGLE_TLS_SKIP=1`. | Cleanup: mit Plan 09 (CI-Pipeline) automatischen Zertifikat-Generierungsschritt im Test-Harness einbauen. |
| 3 | `scripts/ensure-vm-stream-ready.sh` | ~282 | Sunshine-API verwendet Self-Signed-Cert; `--pinnedpubkey` liefert die cryptographische Garant. Das `--insecure` schaltet nur Hostname-Check aus, nicht die Pubkey-Verifizierung. | Cleanup: wenn Sunshine-Cert von Beagle-CA signiert wird, auf `--cacert "$HOST_TLS_CERT_FILE"` umstellen. |

## Hinweis zur CI-Pruefung

Die Datei `.github/workflows/security-tls-check.yml` prueft auf `curl.*--insecure` und `curl.*-k\b` ausserhalb von Allowlist-Eintraegen. Allowlist-Eintraege werden mit dem Kommentar `# tls-bypass-allowlist: ...` markiert und vom CI ausgenommen.
