# Autonomous Roadmap

Stand: 2026-06-01

## Jetzt (P0)

1. Build/Test-Stabilitaet auf `main` sichern.
2. Security-Hygiene (Secrets, TLS, subprocess) laufend erzwingen.
3. Release-Versionierungslogik (stable/prerelease) robust machen.

## Naechste Welle (P1)

1. Clean-Install-R1-Gate reproduzierbar schliessen.
2. VM-Provisioning- und Stream-Readiness auf frischen Hosts absichern.
3. Backup/Restore mit echter VM-Disk auf zweitem Host validieren.

## Ausbau (P2)

1. Lint-Schulden abbauen und Warnungen in Fail-Gates ueberfuehren.
2. Dokumentations- und Runbook-Abdeckung fuer Incident/Operations ausbauen.
3. E2E- und Hardware-nahe Regressionen erweitern.

## Richtung (P3)

1. Multi-Tenant-/IAM-Reifegrad steigern.
2. Security-Review/Pentest-Faehigkeit vorbereiten.
3. Langfristige Debian-/ISO-Produktlinie konsolidieren.
