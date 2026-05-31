---
name: refactoring
description: Verbessert Struktur, Lesbarkeit und Wartbarkeit ohne unbegruendete Verhaltensaenderung.
---

# Refactoring

## Ablauf

1. Scope begrenzen und Ausgangsverhalten dokumentieren.
2. In kleinen Schritten umbauen.
3. Tests waehrenddessen gruen halten.
4. Keine stillen API-Breaks einfuehren.
5. Architekturgrenzen (`providers/beagle`, keine Proxmox-Kopplung) einhalten.
