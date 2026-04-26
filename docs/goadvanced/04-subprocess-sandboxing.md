# Plan 04 — Subprocess-Sandboxing: `run_cmd_safe`, Validation, Timeouts

**Dringlichkeit**: MEDIUM
**Welle**: B (Mittelfrist)
**Audit-Bezug**: B-005

## Problem

Subprocess-Aufrufe (`subprocess.run`, `subprocess.check_output`) sind ueber das gesamte Repo verteilt. Probleme:

- Inkonsistente Fehlerbehandlung (`check=True` vs `check=False`)
- Keine zentralen Timeouts
- Manche Aufrufe verwenden `shell=True` mit User-Input
- Keine Argument-Validierung (z.B. VM-IDs als String an `virsh` ohne Whitelist-Check)
- Keine Limit auf Output-Groesse → potenzielle DoS

Betroffene Dateien (Beispiele):

- `beagle-host/services/server_settings.py:346-383`
- `beagle-host/services/vm_secret_bootstrap.py:75`
- `providers/beagle/libvirt_provider.py` (zahlreiche `virsh`-Aufrufe)
- `providers/beagle/network/*.py`

## Ziel

1. Zentraler `run_cmd_safe`-Helper mit standardisierten Defaults.
2. Argument-Validierung fuer haeufige VM-/Network-Operationen.
3. Output-Size-Limits + Timeouts ueberall.
4. Keine `shell=True` mehr ausser in expliziter Allowlist.

## Schritte

- [x] **Schritt 1** — `core/exec/safe_subprocess.py`
  - [x] `run_cmd(cmd: list[str], *, timeout=30, check=True, max_output=10*1024*1024, capture=True) -> CompletedProcess`
  - [x] Validierung: `cmd` muss `list`, nicht `str` sein → ValueError sonst
  - [x] `shell=False` immer; `shell=True` separater Wrapper `run_shell_unsafe()` mit lautem Warning-Log
  - [x] Timeout ist Pflicht (kein `None` als Default)
  - [x] Output ueber `max_output` abgeschnitten + Warning-Log
  - [x] Tests: `tests/unit/test_safe_subprocess.py`
    - [x] Liste vs String → ValueError
    - [x] Timeout greift
    - [x] Output > max_output → trunkiert + log
    - [x] Non-zero exit + check=True → CalledProcessError

- [x] **Schritt 2** — Argument-Validatoren
  - [x] `core/validation/identifiers.py`:
  - [x] Tests: alle Validatoren mit Edge-Cases (Leerstring, Sonderzeichen, Unicode, sehr lang) — 25 Tests in `test_identifiers.py`
    - `validate_network_name(s: str) -> str` (regex `^[a-zA-Z0-9_-]{1,63}$`)
    - `validate_pool_id(s: str) -> str`
    - `validate_node_id(s: str) -> str`

- [x] **Schritt 3** — `LibvirtRunner` als Adapter
  - [x] `providers/beagle/libvirt_runner.py` neu
  - [x] API:
    - `virsh(*args, timeout=30) -> str`  — validiert Argumente, ruft `run_cmd` auf
    - `domain_state(vmid)`, `domain_xml(vmid)`, `start(vmid)`, `shutdown(vmid)`
  - [x] Macht VM-ID-Validation und virsh-Pfad-Resolution einmal zentral
  - [x] Tests: `tests/unit/test_libvirt_runner.py` (mit Mock von `run_cmd`)

- [x] **Schritt 4** — Migration der Provider
  - [x] `providers/beagle/libvirt_provider.py` → nutzt `LibvirtRunner` statt direkter `subprocess.run`
  - [x] `providers/beagle/network/*.py` → nutzt `run_cmd` aus Plan 04 + `validate_network_name`

- [x] **Schritt 5** — CI-Guard
  - [x] `.github/workflows/security-subprocess-check.yml`: pruefen, dass `subprocess.run` mit `shell=True` nicht in `beagle-host/services/`, `providers/`, `core/` vorkommt (Allowlist via Marker-Kommentar `# noqa: shell-allowed: <reason>`)

- [x] **Schritt 6** — Verifikation
  - [x] `srv1.beagle-os.com`: alle Beagle-Services starten + reagieren wie vorher
  - [ ] Smoke: VM-Start ueber API, Netzwerk-Operationen ueber CLI funktionieren
  - [x] Pen-Test-artiger Test: `vmid="../../etc/passwd"` → wird abgewiesen, kein virsh-Call — `test_identifiers.py::test_path_traversal_raises`

## Abnahmekriterien

- [x] `run_cmd_safe` ist in `core/exec/safe_subprocess.py` und wird in mind. 10 Modulen verwendet.
- [x] `LibvirtRunner` ersetzt direkte `virsh`-Subprocess-Calls in `providers/beagle/`.
- [x] CI-Guard `security-subprocess-check` ist gruen.
- [x] Mind. 4 Argument-Validatoren produktiv.

## Risiko

- Migration kann subtile Verhaltensaenderungen einfuehren (z.B. striktere Timeouts) → pro Modul testen.
- Argument-Whitelisting kann legitime Edge-Cases blockieren → Validierungs-Regex-Updates iterativ.
