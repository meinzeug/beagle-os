# 03 — Gaming-Kiosk-Pool-Management

Stand: 2026-04-24  
Priorität: 8.0.1

---

## Motivation — Ein Feature das kein Konkurrent hat

**Kein einziger VDI-Anbieter (Citrix, VMware, Azure, AWS) bietet Gaming-Kiosk-Pools an.**

Beagle OS ist die einzige Virtualisierungsplattform die:
1. Gaming-Grade Streaming (Moonlight/Sunshine) nativ integriert hat
2. Einen Kiosk-Modus für Endgeräte bietet
3. Beides auf derselben Hardware/Plattform kombinieren kann

### Zielkunden

| Kunde | Use-Case | Marktgröße |
|---|---|---|
| **Esports-Arenas** | 50-500 Gaming-PCs als VMs auf zentraler GPU-Hardware | ~$2Mrd global |
| **Schulen/Universitäten** | Gaming-Unterricht, Game-Design-Kurse, IT-Labore | ~$15Mrd EdTech |
| **Internet-Cafes 2.0** | Alle Games in der Cloud, kein lokales Installieren | ~$1Mrd |
| **Militär/Behörden** | Sichere Gaming-Räume für Entspannung, E-Sport-Teams | Enterprise-Vertrag |
| **Game-Publishing-QA** | Game-QA-Teams testen auf virtualisierten GPU-VMs | ~$500Mio |
| **Game-Streaming-Dienste** | Unternehmen wie Shadow PC nutzen KVM-basierte Infra | ~$5Mrd Cloud-Gaming |

### Was heute vorhanden ist

- `beagle-kiosk/` — Electron-basierter Game-Launcher für lokales Gaming
- GPU-Passthrough-Service (`gpu_passthrough_service.py`)
- Pool-Manager mit VDI-Pools

### Was fehlt

- Kein "Gaming Pool" Typ in Pool-Manager (nur "desktop" heute)
- Keine automatische Game-Installation in VMs (Steam/Epic/GOG)
- Kein "Session-Time-Limit" für Kiosk-Betreiber (Abrechnung nach Zeit)
- Kein "Gaming-Performance-Reporting" (FPS, Latenz, GPU-Auslastung)
- Kein "Kiosk-Controller" (Betreiber sieht alle aktiven Gaming-Sessions live)
- Keine Integration mit Steam-Family-Sharing / Enterprise-Lizenzen

---

## Schritte

### Schritt 1 — Pool-Typ "gaming" einführen

- [x] `core/virtualization/desktop_pool.py`: `pool_type` Feld erweitern: `desktop` | `gaming` | `kiosk`
  - `gaming`-Pools: GPU-Slot-Pflicht, höhere Standard-Bitrate (50-100Mbps), 60/120/144fps Standard
  - `kiosk`-Pools: Session-Time-Limit, keine Persistenz (VM reset nach Session), keine Datei-Uploads
- [x] `beagle-host/services/pool_manager.py`: Pool-Typ-spezifische Allocation-Logik
  - Gaming-Pool: blockiert wenn keine GPU verfügbar (kein Soft-Fallback auf CPU)
- [x] Web Console: Pool-Typ-Auswahl beim Erstellen
- [x] Tests: `tests/unit/test_gaming_pool.py`

### Schritt 2 — Session-Time-Limit + Kiosk-Abrechnung

- [x] `core/virtualization/desktop_pool.py`: `session_time_limit_minutes` (0 = unbegrenzt)
- [x] `beagle-host/services/pool_manager.py`:
  - Beim Allocate: `session_expires_at = now + time_limit`
  - Background-Task: Session automatisch terminieren wenn abgelaufen
  - `session_cost_per_minute` Feld (für Abrechnung)
- [x] `beagle-host/bin/beagle-control-plane.py`: `GET /api/v1/sessions/{id}/time-remaining`
- [x] Web Console: Timer-Anzeige in Session-Übersicht (Kiosk-Betreiber sieht wie lang jede Session noch läuft)
- [x] Tests: `tests/unit/test_session_time_limit.py`

### Schritt 3 — Kiosk-Controller-Dashboard

- [x] `website/ui/kiosk_controller.js`: Echtzeit-Dashboard für Kiosk-Betreiber:
  - Grid aller Kiosk-Stationen (VM-Status, aktiver User, laufendes Spiel, verbleibende Zeit)
  - Aktionen: Session verlängern, vorzeitig beenden, VM-Reset anstoßen
  - Live-Metriken: GPU-Auslastung, FPS, Latenz der aktiven Streams
- [x] Getrennte RBAC-Rolle: `kiosk_operator` (darf nur Kiosk-Sessions verwalten, keine Admin-Rechte)
- [x] Tests: RBAC-Test für `kiosk_operator`

### Schritt 4 — Gaming-Performance-Reporting

- [x] `beagle-host/services/gaming_metrics_service.py`:
  - Aggregiert Stream-Health-Daten (RTT, FPS, dropped frames) + GPU-Metriken pro Session
  - Stündliche/tägliche Reports: Durchschnittliche FPS, Peak-Stunden, populärste Spiele (via Window-Title aus Sunshine)
  - Alert wenn FPS < 30 oder RTT > 50ms
- [x] Web Console: Gaming-Metrics-Dashboard mit Graphen
- [x] Tests: `tests/unit/test_gaming_metrics.py`

### Schritt 5 — VM-Reset-nach-Session (Stateless Gaming)

- [x] `beagle-host/providers/beagle_host_provider.py`: `reset_vm_to_snapshot(vmid, snapshot_name)`
  - Nach jeder Session: VM zurück auf sauberes Snapshot setzen
  - Kein User-Daten-Rückstand zwischen Sessions (Datenschutz + Hygiene)
- [x] Pool-Manager: `on_session_release` Callback → Reset-VM wenn `pool_type=kiosk`
- [x] Tests: `tests/unit/test_vm_stateless_reset.py`

---

## Testpflicht nach Abschluss

- [x] Gaming-Pool: Allocation ohne verfügbare GPU schlägt fehl (kein CPU-Fallback).
- [x] Session-Time-Limit: Session mit 30min Limit endet automatisch nach 30min.
- [x] Kiosk-Controller: Operator sieht alle Sessions live, kann beenden.
- [x] VM-Reset: Nach Session-Ende wird VM auf Snapshot zurückgesetzt (keine User-Daten übrig).
- [x] RBAC: `kiosk_operator` kann nur eigene Kiosk-Sessions sehen, kein Admin-Zugriff.

## Update (2026-04-27)

- Pool-Wizard in `/#panel=policies` erweitert:
  - neues Feld `Pool-Typ` (`desktop`, `gaming`, `kiosk`, `gpu_passthrough`, `gpu_timeslice`, `gpu_vgpu`)
  - `GPU-Klasse`, `Session-Limit (Minuten)` und `Kosten / Minute`
  - Inline-Validierung: Gaming-Pools brauchen `gpu_class`, Kiosk-Pools brauchen `session_time_limit_minutes > 0`
- API/Backend erweitert:
  - `PoolsHttpSurfaceService` akzeptiert jetzt `pool_type`, `session_time_limit_minutes` und `session_cost_per_minute` bei `POST /api/v1/pools`
  - `PoolManagerService` validiert Gaming/Kiosk-Pools serverseitig
  - `pool_info_to_dict()` liefert `pool_type`, `session_time_limit_minutes` und `session_cost_per_minute` jetzt sauber an die WebUI aus
- Kiosk-Operator-RBAC vervollstaendigt:
  - neue Permission `kiosk:operate`
  - Default-Rolle `kiosk_operator` traegt jetzt `vm:read`, `vm:power`, `kiosk:operate`
  - neue dedizierte Endpunkte:
    - `GET /api/v1/pools/kiosk/sessions`
    - `POST /api/v1/pools/kiosk/sessions/{vmid}/end`
- WebUI:
  - vorhandenes `website/ui/kiosk_controller.js` ist jetzt in `renderPolicies()` eingebunden und rendert im Policies-Panel eine echte Kiosk-Controller-Karte
- Validierung:
  - lokal: `python3 -m pytest tests/unit/test_session_time_limit.py tests/unit/test_auth_session.py tests/unit/test_authz_policy.py tests/unit/test_pools_http_surface.py tests/unit/test_policies_ui_regressions.py` => `34 passed`
  - `node --check website/ui/policies.js website/ui/kiosk_controller.js` => OK
  - live: `GET /api/v1/pools/kiosk/sessions` auf `srv1` und `srv2` liefert `200 {"ok":true,...}`
  - Browser-Smoke auf `srv2`: `/#panel=policies` zeigt `Pool-Typ`, `Session-Limit`, `GPU-Klasse` und `Kiosk-Controller` im DOM

## Update (2026-04-27, Stateless Kiosk Reset)

- `PoolManagerService.release_desktop(...)` fuehrt fuer `pool_type=kiosk` + `floating_non_persistent` jetzt sofort `recycle_desktop(...)` aus statt die VM nur in `recycling` oder `expired` stehen zu lassen.
- `PoolManagerService.expire_overdue_sessions()` nutzt jetzt denselben Release-/Recycle-Pfad; ueberfaellige Kiosk-Sessions werden dadurch direkt gestoppt, zurueckgesetzt und wieder `free`.
- dedizierte Regression hinzugefuegt: `tests/unit/test_vm_stateless_reset.py`
- `website/ui/kiosk_controller.js` kennzeichnet die Operator-Aktion jetzt sichtbar als `Beenden + Reset`
- Lokal validiert:
  - `python3 -m pytest tests/unit/test_vm_stateless_reset.py tests/unit/test_session_time_limit.py tests/unit/test_pool_manager.py tests/unit/test_policies_ui_regressions.py` => `31 passed`
- Runtime-Smoke auf `srv1` und `srv2` (direkt auf den deployten Python-Modulen mit temp State):
  - Kiosk-Release ergibt `lease_state=free`
  - VM-Endzustand `free`
  - `stop_vm` und `reset_vm_to_template` werden beide ausgelost
- Nebenfund/Live-Drift:
  - auf beiden Hosts lag noch eine alte `/opt/beagle/core/virtualization/desktop_pool.py`; das wurde im selben Run mit ausgerollt und die Control Plane auf `srv1`/`srv2` neu gestartet.

## Update (2026-04-27, Gaming-Metrics-Dashboard)

- Neuer GET-Endpunkt `GET /api/v1/gaming/metrics` aggregiert aktive Gaming-Sessions und die letzten Report-Dateien fuer das Policies-Panel.
- `POST /api/v1/sessions/stream-health` spiegelt Gaming-Telemetrie jetzt in `GamingMetricsService`, statt sie nur als Rohzustand im Pool-Manager zu halten.
- WebUI in `/#panel=policies` zeigt jetzt:
  - KPI-Kacheln fuer aktive Sessions, Alerts, Avg FPS, Avg RTT und Peak GPU-Temperatur
  - drei SVG-Trends fuer FPS, RTT und GPU-Temperatur
  - aktive Gaming-Sessions mit Live-Metriken
  - letzte abgeschlossene Session-Reports in Tabellenform
- Regressionen:
  - `tests/unit/test_gaming_metrics.py`
  - `tests/unit/test_pools_http_surface.py`
  - `tests/unit/test_policies_ui_regressions.py`

## Update (2026-04-27, Testpflicht abgeschlossen)

- Testpflicht fuer Schritt 1/3 ist jetzt reproduzierbar geschlossen:
  - `tests/unit/test_pool_manager.py`: Gaming-Allocation ohne freie GPU bleibt in `pending-gpu` und scheitert hart statt auf CPU zu fallen.
  - `tests/unit/test_pools_http_surface.py`: Kiosk-Sessions werden fuer nicht berechtigte Pools serverseitig ausgefiltert.
  - `tests/unit/test_authz_policy.py`: `kiosk_operator` erhaelt kein `auth:read` und damit keinen Admin-Zugriff.
  - `tests/unit/test_auth_session.py` + `tests/unit/test_auth_session_http_surface.py`: eingebaute Rollen werden beim Laden bestehender `roles.json` nachgezogen und `/auth/me` liefert die effektiven Permissions an die WebUI.
- Frontend-RBAC-Drift im eingeschraenkten Operator-Flow behoben:
  - `website/ui/dashboard.js` laedt fuer Rollen ohne `cluster:read`, `pool:read` oder `auth:read` diese Endpunkte nicht mehr blind vor.
  - Folge: `kiosk_operator` sieht im Browser keine falsche Warnung `5 API-Aufrufe momentan nicht verfuegbar.` mehr und produziert keine 403-Console-Errors.
- Live validiert:
  - `srv1` und `srv2`: direkter Pool-Manager-Smoke bestaetigt, dass Gaming-Pools ohne passende GPU nicht alloziert werden.
  - `srv2`: Browser-Smoke mit echtem `kiosk_operator`-Login zeigt genau die berechtigte Session (`kiosk-visible`, VM `9301`, User `guest-visible`) inkl. `Beenden + Reset`.
  - `srv2`: derselbe `kiosk_operator` sieht via API nur die berechtigte Kiosk-Session; `GET /api/v1/auth/users` liefert fuer ihn `403 forbidden`.
  - `srv2`: nach dem Dashboard-Gating-Deploy keine Console-Messages mehr im Policies-Flow.

## Update (2026-04-27, Kiosk-Operator Live-Extension + Live-Metriken)

- Kiosk-Controller erweitert:
  - neuer Operator-Action-Button `+15m`
  - pro Session jetzt sichtbar: `FPS`, `RTT`, `GPU`
- Backend:
  - `PoolManagerService` fuehrt `session_expires_at` kompatibel ein; bestehende Sessions ohne Feld fallen weiter auf `assigned_at + session_time_limit_minutes` zurueck.
  - neuer Pfad `POST /api/v1/pools/kiosk/sessions/{vmid}/extend`
  - `update_stream_health()` speichert jetzt auch `gpu_util_pct` und `gpu_temp_c` im Pool-State
- Gaming-Dashboard verbessert:
  - KPI-Karten und Trends nutzen jetzt aktive Sessions als Datenquelle, wenn noch keine historischen Reports vorliegen.
  - Dadurch zeigt `/#panel=policies` bei einer laufenden Gaming-Session sofort sinnvolle `AVG FPS`, `AVG RTT` und `PEAK GPU TEMP` statt nur `0`.
- Regressionen erweitert:
  - `tests/unit/test_pool_manager.py`
  - `tests/unit/test_pools_http_surface.py`
  - `tests/unit/test_authz_policy.py`
  - `tests/unit/test_policies_ui_regressions.py`
  - `tests/unit/test_gaming_metrics.py`
- Live validiert auf `srv2`:
  - `kiosk_operator` sieht im Browser eine berechtigte Kiosk-Session mit `117 FPS`, `9 ms RTT`, `71 C GPU`
  - `+15m` verlaengert eine abgelaufene Session live wieder auf `14m 59s`
  - Gaming-Metrics-Dashboard zeigt fuer eine aktive Session live `121.0 FPS`, `7.00 ms RTT`, `73.0 C` inkl. Trend-Sparklines
  - DevTools-Konsole bleibt im gesamten Policies-Flow fehlerfrei

## Update (2026-04-27, Variable Verlaengerung + Spieltitel/GPU-Auslastung)

- Kiosk-Controller weiter ausgebaut:
  - feste Operator-Aktionen `+15m`, `+30m`, `+60m`
  - neue Spalte `Spiel` aus `stream_health.window_title`
  - GPU-Spalte kombiniert jetzt Auslastung und Temperatur (`88 % / 71 C`)
- Backend:
  - `PoolManagerService.update_stream_health(...)` persistiert jetzt auch `window_title`
  - `extend_kiosk_session(...)` arbeitet bereits mit allgemeinen Minutenwerten; die WebUI nutzt jetzt mehrere feste Operator-Stufen darauf
- Regressionen erweitert:
  - `tests/unit/test_pool_manager.py`
  - `tests/unit/test_pools_http_surface.py`
  - `tests/unit/test_policies_ui_regressions.py`
- Live validiert auf `srv2`:
  - Browser-Smoke zeigt `Steam - Hades`, `88 % / 71 C`, `+15m`, `+30m`, `+60m`
  - `+30m` verlaengert eine abgelaufene Session live auf `29m 59s`
  - temporaerer Smoke-User und Test-State anschliessend wieder entfernt

## Update (2026-04-27, Pool-konfigurierbare Verlaengerungen + Session-Alerts)

- Kiosk-Pools koennen Verlaengerungsstufen jetzt serverseitig konfigurieren:
  - neues Pool-Feld `session_extension_options_minutes`
  - `PoolManagerService.extend_kiosk_session(...)` akzeptiert nur noch konfigurierte Minutenwerte
  - Standard fuer Kiosk-Pools bleibt kompatibel bei `15, 30, 60`
- WebUI:
  - Pool-Wizard hat jetzt das Feld `Verlaengerungsstufen (Minuten)`
  - Pool-Karten zeigen die konfigurierten Stufen sichtbar an
  - Kiosk-Controller rendert die Extend-Buttons nicht mehr hart, sondern pro Session aus dem Pool-State
- Kiosk-Controller zeigt zusaetzlich Session-Alert-Chips aus Live-Telemetrie:
  - `Encoder 95 %` ab hoher `encoder_load`
  - `Drops 12` bei erkannten Dropped Frames
- Regressionen erweitert:
  - `tests/unit/test_pool_manager.py`
  - `tests/unit/test_pools_http_surface.py`
  - `tests/unit/test_policies_ui_regressions.py`
- Live validiert:
  - `srv1` und `srv2`: `GET /api/v1/pools/kiosk/sessions` bleibt gesund (`200`, leer wenn keine Sessions laufen)
- `srv2`: Browser-Smoke mit temporaerem Kiosk-State zeigt `30, 60 Min` im Pool-Card-Meta, Buttons `+30m` / `+60m` im Grid und die Alert-Chips `Encoder 95 %` + `Drops 12`
  - temporaerer `srv2`-Testzustand danach wieder sauber entfernt

## Update (2026-04-27, Reproduzierbarer Zwei-Host-Smoke auf `srv1`/`srv2`)

- Neues Repo-Script `scripts/smoke-gaming-kiosk-flow.sh` fuehrt den kombinierten Gaming-/Kiosk-Smoke jetzt reproduzierbar auf Live-Hosts aus:
  - seedet temporaere Gaming- und Kiosk-Pools
  - speist `stream_health` fuer Gaming/Kiosk ein
  - validiert
    - `GET /api/v1/gaming/metrics`
    - `GET /api/v1/pools/kiosk/sessions`
    - `POST /api/v1/pools/kiosk/sessions/{vmid}/extend`
  - entfernt den Testzustand danach wieder automatisch
- Realer Host-Fund auf `srv1` geschlossen:
  - `POST /api/v1/pools/kiosk/sessions/{vmid}/extend` lieferte live `500`
  - Ursache war kein API-Bug in der Kiosk-Logik, sondern Dateirechte-Drift:
    `desktop-pools.json.lock` lag nach Root-Skriptausfuehrung als `root:root` vor und blockierte `JsonStateStore.save()`
- Repo-Fix:
  - `website`/API unveraendert funktional
  - `beagle-host/services/request_handler_mixin.py` loggt ungefangene Request-Exceptions jetzt mit vollem Traceback strukturiert
  - `scripts/smoke-gaming-kiosk-flow.sh` setzt `desktop-pools.json` nach dem Smoke wieder auf `beagle-manager:beagle-manager` zurueck und entfernt die Lock-Datei sauber
- Live validiert:
  - `srv1`: Smoke komplett gruen, kein `500` mehr
  - `srv2`: Smoke weiterhin komplett gruen
  - auf beiden Hosts bleiben danach keine `smoke-flow`-/`debug-flow`-Pools oder VMs zurueck

---

## Unique Selling Point vs. Konkurrenz

- **Citrix/Omnissa**: Kein Gaming-Modus, RDP-Latenz für Gaming ungeeignet → Beagle: Moonlight, <5ms, Gaming-native
- **GeForce NOW / Shadow PC**: Cloud-only, teuer, DSGVO-Probleme → Beagle: On-Prem, selbst gehostet
- **Proxmox**: Kein Broker, kein Kiosk-UI, kein Time-Limit → Beagle: vollständiger Stack
