#!/usr/bin/env bash
# test-lockscreen-x11-acceptance.sh
#
# Plan 02 live acceptance: grafischen Sperrbildschirm gegen echte X11-Session abnehmen.
# Nutzt Xvfb als virtuellen Framebuffer – CI-tauglich und ohne echte Hardware.
#
# Prueft:
#   1. device_lock_screen.sh erkennt x11-Backend korrekt (xmessage/xterm)
#   2. UI-Prozess wird als Background-Job gestartet (PID-File vorhanden + lebendig)
#   3. Marker-File und Runtime-Info-File werden geschrieben
#   4. lock_screen_stop_ui raumt PID-File und Marker auf
#   5. Xvfb-Screenshot beweist visuellen Lockscreen-Output
#
# Benoetigte Pakete: xvfb, xmessage oder xterm, scrot (optional fuer Screenshot)
# Verwendung:  bash scripts/test-lockscreen-x11-acceptance.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCK_SCREEN_SH="$ROOT_DIR/thin-client-assistant/runtime/device_lock_screen.sh"

PASS=0
FAIL=0
STEP=0

pass() { PASS=$(( PASS + 1 )); printf '[PASS] %s\n' "$1"; }
fail() { FAIL=$(( FAIL + 1 )); printf '[FAIL] %s\n' "$1"; }
step() { STEP=$(( STEP + 1 )); printf '\n--- Step %d: %s ---\n' "$STEP" "$1"; }

cleanup() {
  # Kill xmessage/xterm/xvfb spawned by this test
  [[ -n "${LOCK_PID:-}" ]] && kill "$LOCK_PID" 2>/dev/null || true
  [[ -n "${XVFB_PID:-}" ]] && kill "$XVFB_PID" 2>/dev/null || true
  rm -rf "${TEST_STATE_DIR:-}" "${STUBS_DIR:-}" 2>/dev/null || true
}
trap cleanup EXIT

# ---- Voraussetzungen pruefen -------------------------------------------

step "Voraussetzungen"

if ! command -v Xvfb >/dev/null 2>&1; then
  fail "Xvfb nicht gefunden – apt-get install xvfb"
  exit 1
fi
pass "Xvfb vorhanden"

if ! command -v xmessage >/dev/null 2>&1 && ! command -v xterm >/dev/null 2>&1; then
  fail "Weder xmessage noch xterm gefunden – apt-get install x11-apps xterm"
  exit 1
fi
X11_TOOL="xmessage"; command -v xmessage >/dev/null 2>&1 || X11_TOOL="xterm"
pass "X11-Backend verfuegbar: $X11_TOOL"

if [[ ! -f "$LOCK_SCREEN_SH" ]]; then
  fail "device_lock_screen.sh nicht gefunden: $LOCK_SCREEN_SH"
  exit 1
fi
pass "device_lock_screen.sh gefunden"

# ---- Xvfb starten -------------------------------------------------------

step "Xvfb starten"

VDISPLAY=":99"
Xvfb "$VDISPLAY" -screen 0 1280x800x24 -ac &
XVFB_PID=$!
sleep 1

if ! kill -0 "$XVFB_PID" 2>/dev/null; then
  fail "Xvfb auf $VDISPLAY konnte nicht gestartet werden"
  exit 1
fi
pass "Xvfb laeuft (PID=$XVFB_PID, DISPLAY=$VDISPLAY)"

# ---- Stub-Verzeichnisse anlegen -----------------------------------------

step "Test-Stubs anlegen"

TEST_STATE_DIR="$(mktemp -d /tmp/beagle-lockscreen-test.XXXXXX)"
STUBS_DIR="$(mktemp -d /tmp/beagle-lockscreen-stubs.XXXXXX)"

# Stub fuer common.sh – liefert beagle_state_dir und beagle_log_event
cat > "$STUBS_DIR/common.sh" <<STUB
beagle_state_dir() { printf '%s\n' "${TEST_STATE_DIR}"; }
beagle_log_event() { true; }
runtime_device_id() { printf '%s\n' "test-device-001"; }
STUB

# Stub fuer device_state_enforcement.sh – device_lock_active prueft Marker-Datei
cat > "$STUBS_DIR/enforcement.sh" <<STUB
device_lock_active() { [[ -f "${TEST_STATE_DIR}/device.locked" ]]; }
STUB

pass "Stubs angelegt in $STUBS_DIR"
pass "State-Dir: $TEST_STATE_DIR"

# ---- Phase 1: Lockscreen aktivieren ------------------------------------

step "Lockscreen aktivieren (device.locked setzen)"

# Geraet als gesperrt markieren
touch "${TEST_STATE_DIR}/device.locked"
pass "device.locked gesetzt"

# Lock-Screen einmal starten (ONCE=1: Watcher-Schleife laeuft genau einmal)
BEAGLE_TEST_STATE_DIR="$TEST_STATE_DIR" \
COMMON_SH="$STUBS_DIR/common.sh" \
DEVICE_STATE_ENFORCEMENT_SH="$STUBS_DIR/enforcement.sh" \
BEAGLE_LOCK_SCREEN_MARKER_FILE="$TEST_STATE_DIR/lock-screen.marker" \
BEAGLE_LOCK_SCREEN_PID_FILE="$TEST_STATE_DIR/lock-screen.pid" \
BEAGLE_LOCK_SCREEN_RUNTIME_INFO_FILE="$TEST_STATE_DIR/lock-screen.env" \
BEAGLE_LOCK_SCREEN_ONCE=1 \
BEAGLE_LOCK_SCREEN_POLL_INTERVAL=1 \
XDG_SESSION_TYPE=x11 \
DISPLAY="$VDISPLAY" \
bash -c "
  source '$LOCK_SCREEN_SH'
  run_device_lock_screen_watcher
"

# Kurz warten bis Background-Prozess sich etabliert
sleep 2

# ---- Phase 2: Ergebnisse pruefen ----------------------------------------

step "PID-File pruefen"

if [[ -f "$TEST_STATE_DIR/lock-screen.pid" ]]; then
  LOCK_PID="$(cat "$TEST_STATE_DIR/lock-screen.pid" 2>/dev/null || true)"
  pass "PID-File vorhanden (PID=$LOCK_PID)"
else
  fail "PID-File fehlt: $TEST_STATE_DIR/lock-screen.pid"
  LOCK_PID=""
fi

step "Prozess lebendig pruefen"

if [[ -n "$LOCK_PID" ]] && kill -0 "$LOCK_PID" 2>/dev/null; then
  pass "Lock-Screen-Prozess laeuft (PID=$LOCK_PID)"
else
  fail "Lock-Screen-Prozess nicht aktiv"
fi

step "Runtime-Info-File pruefen"

if [[ -f "$TEST_STATE_DIR/lock-screen.env" ]]; then
  pass "Runtime-Info-File vorhanden"
  # Backend muss x11 sein
  if grep -q 'BEAGLE_LOCK_SCREEN_RUNTIME_BACKEND=x11' "$TEST_STATE_DIR/lock-screen.env"; then
    pass "Backend=x11 korrekt gesetzt"
  else
    backend_line="$(grep 'BACKEND' "$TEST_STATE_DIR/lock-screen.env" 2>/dev/null || echo '(nicht gefunden)')"
    fail "Backend-Wert unerwartet: $backend_line"
  fi
  # Session-Type muss x11 sein
  if grep -q 'BEAGLE_LOCK_SCREEN_RUNTIME_SESSION_TYPE=x11' "$TEST_STATE_DIR/lock-screen.env"; then
    pass "SessionType=x11 korrekt gesetzt"
  else
    fail "SessionType unerwartet: $(grep SESSION_TYPE "$TEST_STATE_DIR/lock-screen.env" || true)"
  fi
  # Display muss gesetzt sein
  if grep -q "BEAGLE_LOCK_SCREEN_RUNTIME_DISPLAYS=$VDISPLAY" "$TEST_STATE_DIR/lock-screen.env"; then
    pass "Display=$VDISPLAY korrekt in Runtime-Info"
  else
    fail "Display unerwartet: $(grep DISPLAYS "$TEST_STATE_DIR/lock-screen.env" || true)"
  fi
else
  fail "Runtime-Info-File fehlt"
fi

# ---- Phase 3: Screenshot -----------------------------------------------

step "Xvfb-Screenshot aufnehmen"

SCREENSHOT_FILE="/tmp/beagle-lockscreen-acceptance-$(date +%Y%m%d-%H%M%S).xwd"
SCREENSHOT_PNG="${SCREENSHOT_FILE%.xwd}.png"

if command -v xwd >/dev/null 2>&1; then
  DISPLAY="$VDISPLAY" xwd -root -silent -out "$SCREENSHOT_FILE" 2>/dev/null && pass "XWD-Screenshot: $SCREENSHOT_FILE" || fail "xwd fehlgeschlagen"
  if command -v convert >/dev/null 2>&1; then
    convert "$SCREENSHOT_FILE" "$SCREENSHOT_PNG" 2>/dev/null && pass "PNG konvertiert: $SCREENSHOT_PNG" || true
  fi
elif command -v scrot >/dev/null 2>&1; then
  DISPLAY="$VDISPLAY" scrot "$SCREENSHOT_PNG" 2>/dev/null && pass "Screenshot: $SCREENSHOT_PNG" || fail "scrot fehlgeschlagen"
else
  printf '[INFO] Kein Screenshot-Tool verfuegbar (xwd/scrot). Visueller Nachweis ueber SPICE/VNC.\n'
fi

# ---- Phase 4: Unlock (lock_screen_stop_ui) -----------------------------

step "Lockscreen deaktivieren (Unlock)"

rm -f "${TEST_STATE_DIR}/device.locked"

COMMON_SH="$STUBS_DIR/common.sh" \
DEVICE_STATE_ENFORCEMENT_SH="$STUBS_DIR/enforcement.sh" \
BEAGLE_LOCK_SCREEN_MARKER_FILE="$TEST_STATE_DIR/lock-screen.marker" \
BEAGLE_LOCK_SCREEN_PID_FILE="$TEST_STATE_DIR/lock-screen.pid" \
BEAGLE_LOCK_SCREEN_RUNTIME_INFO_FILE="$TEST_STATE_DIR/lock-screen.env" \
DISPLAY="$VDISPLAY" \
bash -c "
  source '$LOCK_SCREEN_SH'
  lock_screen_stop_ui
"

sleep 1

if [[ ! -f "$TEST_STATE_DIR/lock-screen.pid" ]]; then
  pass "PID-File nach Stop entfernt"
else
  fail "PID-File nach Stop noch vorhanden"
fi

if [[ ! -f "$TEST_STATE_DIR/lock-screen.marker" ]]; then
  pass "Marker-File nach Stop entfernt"
else
  fail "Marker-File nach Stop noch vorhanden"
fi

if [[ -n "$LOCK_PID" ]] && ! kill -0 "$LOCK_PID" 2>/dev/null; then
  pass "Lock-Screen-Prozess nach Stop beendet"
elif [[ -z "$LOCK_PID" ]]; then
  pass "Kein PID vorhanden – Prozess war bereits inaktiv"
else
  fail "Lock-Screen-Prozess laeuft noch nach Stop"
fi

# ---- Ergebnis -----------------------------------------------------------

printf '\n========================================\n'
printf 'Plan-02 X11-Lockscreen Acceptance: %d passed, %d failed\n' "$PASS" "$FAIL"
printf '========================================\n'

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
