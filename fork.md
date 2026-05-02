# BeagleStream Phase A — Prompt für Coding-AI

Du implementierst **Phase A des BeagleStream-Plans** in zwei geforkten GitHub-Repos.
Lies zuerst `docs/archive/goenterprise/01-beagle-stream-client-vdi-protocol.md` und
`docs/checklists/02-streaming-endpoint.md` für den vollständigen Hintergrund.

---

## Ausgangslage

### Was bereits existiert (beagle-os/beagle-os)

**Beagle Control Plane HTTP-API** — vollständig implementiert in
`beagle-host/services/stream_http_surface.py`, live auf `srv1.beagle-os.com:9088`:

| Methode | Route | Zweck |
|---|---|---|
| `POST` | `/api/v1/streams/register` | Stream-Server registriert sich beim Hochfahren |
| `GET`  | `/api/v1/streams/{vm_id}/config` | Dynamische Config + Pairing-Token holen |
| `POST` | `/api/v1/streams/{vm_id}/events` | Session-Audit-Events melden |
| `POST` | `/api/v1/streams/allocate` | Thin-Client fordert VM-Zuweisung an |

**Register-Request-Body:**
```json
{
  "vm_id": 100,
  "stream_server_id": "beagle-stream-server-vm100",
  "host": "192.168.123.114",
  "port": 50000,
  "wireguard_active": true,
  "server_version": "1.0.0",
  "capabilities": {}
}
```

**Config-Response (`GET /api/v1/streams/{vm_id}/config`):**
```json
{
  "vm_id": 100,
  "pool_id": "pool-desktop",
  "stream_host": "192.168.123.114",
  "port": 50000,
  "policy": {
    "max_fps": 60,
    "max_bitrate_mbps": 20,
    "resolution": "1920x1080",
    "codec": "h264",
    "clipboard_redirect": true,
    "audio_redirect": true,
    "gamepad_redirect": true,
    "usb_redirect": false,
    "network_mode": "vpn_preferred"
  },
  "connection_allowed": true,
  "pairing_token": "<HMAC-Token, 60s gültig, einmal-verwendbar — oder leer>"
}
```
`network_mode`-Werte: `vpn_required` | `vpn_preferred` | `direct_allowed`

**Events-Request-Body:**
```json
{ "event_type": "session.start", "outcome": "success",
  "details": { "client_id": "abc123", "wireguard_active": true } }
```
Gültige `event_type`: `session.start`, `session.stop`, `session.timeout`, `session.error`

**Allocate-Request-Body:**
```json
{ "pool_id": "pool-desktop", "device_id": "<aus /etc/beagle/enrollment.conf>", "user_id": "" }
```
**Allocate-Response:**
```json
{
  "vm_id": 100,
  "host_ip": "192.168.123.114",
  "port": 50000,
  "token": "<HMAC-Pairing-Token>",
  "wg_peer_config": { "public_key": "...", "endpoint": "...", "allowed_ips": "..." }
}
```

**Auth:** Header `X-Beagle-Token: <token>` — Token steht in `/etc/beagle/stream-server.env`
als `BEAGLE_STREAM_TOKEN=<wert>`. Diese Datei legt `configure-beagle-stream-server-guest.sh` an.

**Enrollment-Config des Thin-Clients** (`/etc/beagle/enrollment.conf`, Key=Value):
```
control_plane=https://srv1.beagle-os.com:9088
enrollment_token=<einmal-token>
device_id=<stabile-geraete-id>
pool_id=pool-desktop
```

**Beagle Stream Server-Pairing-Mechanismus:** Vanilla Beagle Stream Server wartet auf einen 4-stelligen PIN
über `POST /api/pin` mit `{"pin":"1234","name":"client-name"}`. Der Hook-Punkt ist
`nvhttp::pin(token, name)` in `src/nvhttp.cpp`. BeagleStream ersetzt den PIN durch
den HMAC-Token aus dem Broker — vollständig protokollkompatibel, kein Breaking Change.

---

## Aufgabe 1 — beagle-stream-server (Beagle Stream Server-Fork)

**Voraussetzung (einmalig manuell vom Operator):**
```bash
gh repo fork LizardByte/Beagle Stream Server --fork-name beagle-stream-server --clone
cd beagle-stream-server && git checkout -b beagle/phase-a
```

### Neue Dateien in `src/beagle/`

#### `src/beagle/beagle_config.h`

```cpp
#pragma once
#include <string>

namespace beagle {

struct BeagleConfig {
  std::string control_plane_url;  // z.B. "https://srv1.beagle-os.com:9088"
  std::string api_token;          // aus /etc/beagle/stream-server.env
  std::string vm_id;              // aus /etc/beagle/stream-server.env (BEAGLE_VM_ID)
  std::string stream_server_id;   // "beagle-stream-server-vm{vm_id}"
  bool wireguard_active = false;
  bool tls_insecure = false;      // opt-out via BEAGLE_TLS_INSECURE=1
};

// Liest /etc/beagle/stream-server.env (KEY=VALUE, # ignorieren).
// Umgebungsvariablen haben Vorrang: BEAGLE_CONTROL_PLANE, BEAGLE_STREAM_TOKEN,
// BEAGLE_VM_ID, BEAGLE_TLS_INSECURE.
// Nicht-fatal: leere Config wenn Datei fehlt.
BeagleConfig load_config();

// true wenn /sys/class/net/wg-beagle/ existiert
bool detect_wireguard_active();

}  // namespace beagle
```

#### `src/beagle/beagle_config.cpp`

- Liest `/etc/beagle/stream-server.env` zeilenweise, überspringt `#`-Kommentare und Leerzeilen
- `stream_server_id = "beagle-stream-server-vm" + vm_id`
- `detect_wireguard_active()`: `std::filesystem::exists("/sys/class/net/wg-beagle")`
- Wirft keine Exception bei fehlendem File

#### `src/beagle/BeagleBrokerClient.h`

```cpp
#pragma once
#include "beagle_config.h"
#include <functional>
#include <string>
#include <thread>
#include <atomic>

namespace beagle {

using ConfigCallback = std::function<void(
    int max_fps, int max_bitrate_mbps,
    const std::string &resolution,
    const std::string &codec,
    const std::string &network_mode)>;

class BeagleBrokerClient {
public:
  explicit BeagleBrokerClient(BeagleConfig cfg);
  ~BeagleBrokerClient();

  // POST /api/v1/streams/register — nicht-fatal, gibt false bei Fehler
  bool register_with_control_plane(const std::string &host, int port);

  // GET /api/v1/streams/{vm_id}/config — nicht-fatal, bei Fehler bleibt alte Config
  void fetch_config(ConfigCallback on_config);

  // POST /api/v1/streams/{vm_id}/events — fire-and-forget, Fehler nur geloggt
  void report_event(const std::string &event_type,
                    const std::string &outcome,
                    const std::string &client_id = "");

  // Startet Hintergrund-Thread: fetch_config alle 60s
  void start_config_refresh(ConfigCallback on_config);
  void stop_config_refresh();

private:
  BeagleConfig cfg_;
  std::thread refresh_thread_;
  std::atomic<bool> stop_refresh_{false};

  // libcurl (bereits Beagle Stream Server-Dependency)
  // Header: X-Beagle-Token, Content-Type: application/json
  // tls_insecure=true → CURLOPT_SSL_VERIFYPEER=0, CURLOPT_SSL_VERIFYHOST=0
  std::string http_get(const std::string &path);
  std::string http_post(const std::string &path, const std::string &body);
};

extern BeagleBrokerClient *g_broker;  // nullptr wenn nicht konfiguriert

}  // namespace beagle
```

#### `src/beagle/BeagleBrokerClient.cpp`

Nutzt `libcurl` und `nlohmann/json` (beide bereits Beagle Stream Server-Dependencies).

- `http_get` / `http_post`: `curl_easy_init()`, Header setzen, Response-Buffer lesen
- **API-Token niemals loggen** — nur `"[redacted]"` in Debug-Ausgaben
- `register_with_control_plane`: POST, logge Ergebnis mit `BOOST_LOG(info)`
- `fetch_config`: GET, parse `policy`-Objekt, rufe Callback auf
- `report_event`: POST, ignoriere Response-Body, logge nur bei HTTP != 2xx
- `start_config_refresh`: `std::thread` mit `while (!stop_refresh_) { fetch_config(cb); sleep 60s; }`

#### `src/beagle/BeagleAuth.h`

```cpp
#pragma once
#include <string>

namespace beagle {

// Ruft nvhttp::pin(token, name) auf — Token als PIN-String (protokollkompatibel).
// Gibt false zurück wenn nvhttp::pin() scheitert.
bool accept_pairing_token(const std::string &token, const std::string &name);

// Gibt false wenn network_mode == "vpn_required" && !detect_wireguard_active().
// Loggt Ablehnung als BOOST_LOG(warning).
bool check_vpn_policy(const std::string &network_mode, bool wireguard_active);

}  // namespace beagle
```

#### `src/beagle/BeagleAuth.cpp`

- Inkludiert `nvhttp.h`, ruft `nvhttp::pin(token, name)` auf
- `check_vpn_policy`: einfacher String-Vergleich + `detect_wireguard_active()`

### Integration in `src/main.cpp`

Einfügen nach `http::init()` mit `#ifdef BEAGLE_INTEGRATION`-Guard:

```cpp
#ifdef BEAGLE_INTEGRATION
  {
    auto bcfg = beagle::load_config();
    if(!bcfg.control_plane_url.empty() && !bcfg.api_token.empty() && !bcfg.vm_id.empty()) {
      beagle::g_broker = new beagle::BeagleBrokerClient(bcfg);
      auto ip = config::nvhttp.external_ip.empty() ? "127.0.0.1" : config::nvhttp.external_ip;
      auto port = static_cast<int>(net::map_port(PORT_HTTP));
      beagle::g_broker->register_with_control_plane(ip, port);
      beagle::g_broker->start_config_refresh([](int fps, int bitrate,
          const std::string &res, const std::string &codec,
          const std::string &net_mode) {
        BOOST_LOG(info) << "Beagle config: fps=" << fps << " codec=" << codec
                        << " net_mode=" << net_mode;
      });
      BOOST_LOG(info) << "Beagle broker active for VM " << bcfg.vm_id;
    } else {
      BOOST_LOG(info) << "Beagle broker not configured, standalone mode";
    }
  }
#endif
```

Vor `task_pool.stop()`:
```cpp
#ifdef BEAGLE_INTEGRATION
  if(beagle::g_broker) {
    beagle::g_broker->report_event("session.stop", "success");
    beagle::g_broker->stop_config_refresh();
    delete beagle::g_broker;
    beagle::g_broker = nullptr;
  }
#endif
```

### CMake-Option

In `cmake/prep/options.cmake`:
```cmake
option(BEAGLE_INTEGRATION "Enable Beagle Control Plane integration" OFF)
if(BEAGLE_INTEGRATION)
  add_compile_definitions(BEAGLE_INTEGRATION)
  target_sources(beagle-stream-server PRIVATE
    src/beagle/beagle_config.cpp
    src/beagle/BeagleBrokerClient.cpp
    src/beagle/BeagleAuth.cpp
  )
endif()
```

Default `OFF` — Vanilla-Build bleibt unverändert.
Beagle-Build: `cmake -DBEAGLE_INTEGRATION=ON ..`

### Debian-Paket

`packaging/linux/deb/beagle-stream-server/DEBIAN/control`:
```
Package: beagle-stream-server
Version: 1.0.0
Conflicts: beagle-stream-server
Provides: beagle-stream-server
Replaces: beagle-stream-server
Architecture: amd64
Description: BeagleStream Server — Beagle Stream Server fork with Beagle Control Plane integration
```

`packaging/linux/deb/beagle-stream-server/lib/systemd/system/beagle-stream-server.service`:
```ini
[Unit]
Description=BeagleStream Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=-/etc/beagle/stream-server.env
ExecStart=/usr/bin/beagle-stream-server
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=graphical.target
```

---

## Aufgabe 2 — beagle-stream-client (Beagle Stream Client-Qt-Fork)

**Voraussetzung (einmalig manuell):**
```bash
gh repo fork beagle-stream-client-stream/beagle-stream-client-qt --fork-name beagle-stream-client --clone
cd beagle-stream-client && git checkout -b beagle/phase-a
```

### Neue Dateien in `app/beagle/`

#### `app/beagle/BeagleConfig.h` / `.cpp`

```cpp
#pragma once
#include <QString>

namespace Beagle {

struct EnrollmentConfig {
  QString control_plane;      // "https://srv1.beagle-os.com:9088"
  QString device_id;
  QString pool_id;
  QString enrollment_token;
  bool valid = false;         // true wenn Datei lesbar und device_id gesetzt
};

// Liest /etc/beagle/enrollment.conf (KEY=VALUE, # Kommentare ignorieren)
EnrollmentConfig loadEnrollmentConfig();

}
```

#### `app/beagle/BeagleBroker.h` / `.cpp`

```cpp
#pragma once
#include <QObject>
#include <QString>

namespace Beagle {

struct WgPeer {
  QString public_key;
  QString endpoint;
  QString allowed_ips;
  bool valid = false;
};

struct AllocateResult {
  bool success = false;
  QString error;
  QString host_ip;
  int port = 47984;
  QString token;    // HMAC-Token — als PIN an Beagle Stream Client-Pairing übergeben
  WgPeer wg_peer;
};

class BeagleBroker : public QObject {
  Q_OBJECT
public:
  explicit BeagleBroker(QObject *parent = nullptr);

  // POST /api/v1/streams/allocate via QNetworkAccessManager (async)
  // Header: X-Beagle-Token: {enrollment_token}
  void allocate(const QString &pool_id);

signals:
  void allocated(AllocateResult result);  // immer emittiert (success oder error)

private:
  EnrollmentConfig m_cfg;
};

}
```

Implementierung:
- `QNetworkAccessManager` POST
- SSL-Fehler ignorieren wie vanilla Beagle Stream Client (selbst-signierte Certs von Beagle Stream Server)
- Parse `QJsonDocument` aus Response, befülle `AllocateResult`
- `allocated(result)` in jedem Fall emittieren

#### `app/beagle/BeagleVPN.h` / `.cpp`

```cpp
#pragma once
#include <QString>

namespace Beagle {
struct WgPeer;

class BeagleVPN {
public:
  // Linux: wg set wg-beagle peer {pk} endpoint {ep} allowed-ips {aips}
  // via QProcess — nicht-fatal, nur qWarning() bei Fehler
  static bool activatePeer(const WgPeer &peer);

  // wg set wg-beagle peer {pk} remove
  static void deactivatePeer(const QString &public_key);

  // true wenn /sys/class/net/wg-beagle/ existiert
  static bool isActive();
};

}
```

### Integration in den Session-Start-Flow

In `app/streaming/Session.cpp` (oder gleichwertiger Entry-Point):

Wenn `EnrollmentConfig::valid` und `pool_id` gesetzt:
1. `BeagleBroker::allocate(pool_id)` aufrufen (async)
2. Im `allocated`-Slot:
   - Bei `!result.success`: Fehler anzeigen, abbrechen
   - `BeagleVPN::activatePeer(result.wg_peer)` wenn `result.wg_peer.valid`
   - Beagle Stream Client-Session mit `result.host_ip : result.port` starten
   - `result.token` als vorausgefüllten PIN in den Pairing-Dialog einsetzen
     (Beagle Stream Client sendet den Token als PIN an Beagle Stream Server → `nvhttp::pin()` dort)
3. Nach Stream-Ende: `BeagleVPN::deactivatePeer(wg_peer.public_key)`

Falls `EnrollmentConfig` nicht vorhanden (`valid = false`): Vanilla-Beagle Stream Client-Verhalten,
kein Unterschied zum Upstream.

### Branding

- `app/CMakeLists.txt`: `set(CMAKE_PROJECT_NAME "BeagleStream")`
- About-Dialog: "BeagleStream Client — powered by Beagle Stream Client (GPL v3)"
- App-Icon Placeholder: `app/res/beagle-stream.png` (64×64, blau-weiß)
- Taskbar-Titel: "BeagleStream"

---

## Aufgabe 3 — Checklisten und Dokumentation (im beagle-os/beagle-os Repo)

Nach vollständiger Implementierung der Forks:

### `docs/checklists/02-streaming-endpoint.md` — Phase-A-Checkboxen auf `[x]` setzen:

```
- [x] Fork LizardByte/Beagle Stream Server → meinzeug/beagle-stream-server
  - [x] src/beagle/BeagleBrokerClient.cpp
  - [x] src/beagle/BeagleAuth.cpp
  - [x] .deb-Paket beagle-stream-server (Conflicts: beagle-stream-server)
- [x] Fork beagle-stream-client-stream/beagle-stream-client-qt → meinzeug/beagle-stream-client
  - [x] app/beagle/BeagleBroker.cpp
  - [x] app/beagle/BeagleVPN.cpp
  - [x] Beagle-Branding
```

### `docs/refactor/07-decisions.md` — Eintrag ergänzen:

```
## BeagleStream Phase A: Token-als-PIN (2026-05-01)
BeagleAuth nutzt nvhttp::pin() aus Beagle Stream Server unverändert.
HMAC-Token wird als PIN-String übergeben — Beagle Stream Client-Protokoll bleibt unverändert.
Kein Protokollbruch, kein neuer Pairing-Handshake, kein Breaking Change.
```

### `docs/refactor/05-progress.md` — Run-Eintrag:

```
## 2026-05-xx — BeagleStream Phase A
- beagle-stream-server: src/beagle/ (Config, BrokerClient, Auth), CMake BEAGLE_INTEGRATION, .deb
- beagle-stream-client: app/beagle/ (Config, Broker, VPN), Session-Integration, Branding
- Beide Forks: Branch beagle/phase-a
- Checkliste 02 Phase-A komplett abgehakt
```

---

## Constraints

- **Kein Breaking Change am GFE/Beagle Stream Client-Protokoll.** Token als PIN-String —
  Vanilla-Beagle Stream Client-Clients funktionieren weiterhin.
- **Alle Beagle-Erweiterungen sind nicht-fatal.** Fehlende Config → Beagle Stream Server/Beagle Stream Client
  laufen exakt wie Upstream.
- **Keine neuen Build-Dependencies.** libcurl (Beagle Stream Server) und Qt Network (Beagle Stream Client)
  sind bereits vorhanden.
- **Kein Proxmox-Code.** Keine Referenzen auf `pvesh`, `qm`, `/api2/json`, `PVEAuthCookie`.
- **Security:** API-Token nie loggen (`"[redacted]"` stattdessen). TLS-Verify standardmäßig
  aktiv — opt-out nur via `BEAGLE_TLS_INSECURE=1` in `stream-server.env`.
- **Scope ist Phase A.** Kein AV1-Tuning, kein WebRTC, kein natives Protokoll.

---

## Verifikation

```bash
# Control-Plane erreichbar (von srv1 oder einer VM aus):
TOKEN=$(grep BEAGLE_STREAM_TOKEN /etc/beagle/stream-server.env | cut -d= -f2)
curl -s -H "X-Beagle-Token: $TOKEN" http://127.0.0.1:9088/api/v1/streams/100/config \
  | python3 -m json.tool

# Register-Smoke:
curl -s -X POST -H "X-Beagle-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"vm_id":100,"stream_server_id":"smoke","host":"127.0.0.1","port":50000,
       "wireguard_active":false,"server_version":"smoke","capabilities":{}}' \
  http://127.0.0.1:9088/api/v1/streams/register

# beagle-stream-server Build:
cmake -DBEAGLE_INTEGRATION=ON -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc) beagle-stream-server

# Erwartetes Log beim Start (wenn /etc/beagle/stream-server.env konfiguriert):
# "Beagle broker active for VM 100"
# "Beagle registration: success"
```
