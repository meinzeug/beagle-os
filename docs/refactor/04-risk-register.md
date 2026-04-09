# Risk Register

## Active Risks

| ID | Risk | Severity | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- | --- |
| R1 | Browser-side token handling in UI, extension, and website | High | Token leakage or broader exposure during XSS/UI compromise | Reduce frontend token persistence, centralize auth policy, prefer server-mediated flows where possible | Open |
| R2 | `beagle-control-plane.py` monolith | High | Small edits can break host API, installers, or provisioning | Extract internal services behind stable routes | Open |
| R3 | `proxmox-ui/beagle-ui.js` monolith | High | UI regressions during changes, difficult continuation between agents | Extract by concern into stable modules | Open |
| R4 | Thin client shell-script complexity | High | Moonlight regression, installer breakage, quoting issues | Refactor around config/network/pairing/launch seams with smoke checks | Open |
| R5 | Release surface spans two servers | High | Drift breaks hosted installers or public downloads | Keep artifact contracts explicit and verify both sides after release work | Open |
| R6 | Local `.build/` and `dist/` artifacts on control workstation | Medium | Stale outputs and disk pressure can distort analysis and release confidence | Avoid local heavy builds; clean accidental local outputs | Open |
| R7 | No meaningful automated behavioral tests | High | Refactors rely on manual confidence and syntax checks only | Add smoke and contract checks incrementally | Open |
| R8 | Duplicated browser logic across surfaces | Medium | Behavior drift and inconsistent security fixes | Extract shared helpers or mirrored modules with common contract | Open |
| R9 | Packaging script orchestrates too many artifact families | Medium | Failures are harder to isolate and partial reruns are fragile | Split packaging into smaller phases and verify contracts | Open |
| R10 | Kiosk main process still mixes config, catalog, store rules, and child-process supervision | Medium | Regressions in GFN launch/supervision or offline cache handling | Extract main-process services while preserving child-process model | Open |
| R11 | Provider abstraction is incomplete and uneven across repo surfaces | High | New work may accidentally reintroduce direct Proxmox coupling outside approved provider seams | Enforce `core/*` + `providers/proxmox/*` boundaries, document remaining direct couplings, block new unmanaged Proxmox bindings in reviews | Open |

## Immediate Watch Items

- Any refactor touching Moonlight launch requires explicit runtime caution.
- Any refactor touching GeForce NOW integration must preserve kiosk ownership of the child process.
- Any release or installer change must consider both `srv.thinover.net` and `srv1.meinzeug.cloud`.
- Any new VM/inventory/provider feature must be checked for direct `qm`, `pvesh`, `/api2/json`, or `PVE.*` usage outside the provider layer.
