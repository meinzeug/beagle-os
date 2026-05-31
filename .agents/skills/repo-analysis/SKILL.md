---
name: repo-analysis
description: Analysiert den aktuellen Zustand des Beagle-OS-Repositories und aktualisiert die operative Basis fuer autonome Weiterentwicklung.
---

# Repo Analysis

Nutze diesen Skill, wenn der aktuelle Zustand neu bewertet werden muss.

## Ablauf

1. Lies `.agents/repo-analysis.md`, `.agents/status.md`, `.agents/roadmap.md`.
2. Pruefe Kernpfade: `beagle-host/`, `providers/beagle/`, `core/`, `scripts/`, `tests/`, `website/`.
3. Pruefe Workflows unter `.github/workflows/`.
4. Erfasse Build/Test/Lint-Befehle und moegliche Brueche.
5. Aktualisiere `.agents/repo-analysis.md` mit Risiken, Luecken und Prioritaeten.
