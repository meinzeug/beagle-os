# Release Policy

- Releases nur ueber definierte Workflows (`.github/workflows/release.yml`).
- Stable und Prerelease klar trennen; stable Mirror nicht von Previews ueberschreiben lassen.
- Jede Release-Aenderung braucht Regressionen fuer Versionierungslogik.
- Runtime-Hotfixes muessen vor Release im Repo reproduzierbar enthalten sein.
- Signatur-/Artefakt-Integritaet und Download-Metadaten pruefen.
