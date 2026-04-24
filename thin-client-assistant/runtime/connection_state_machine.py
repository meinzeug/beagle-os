#!/usr/bin/env python3
"""
Beagle Endpoint OS — Connection State Machine.

Manages the lifecycle of the endpoint's cluster connection with clean
state transitions:

  ONLINE  ──────(loss)──────►  OFFLINE
    ▲                               │
    └────────(recovery)─────────────┘
    (via RECONNECTING on configurable interval)

States:
  ONLINE       — cluster is reachable; normal streaming operation
  OFFLINE      — cluster unreachable; showing Offline-UI; polling for recovery
  RECONNECTING — actively attempting reconnect after offline period

Callbacks are invoked on each state transition so the UI layer can react
(e.g. show/hide the "Cluster nicht erreichbar" overlay).

Usage:
  from connection_state_machine import ConnectionStateMachine, State

  def check_cluster():
      # e.g. HTTP GET to cluster health endpoint
      return True / False

  def on_transition(old_state, new_state, ctx):
      if new_state == State.OFFLINE:
          show_offline_overlay(ctx["countdown"])
      elif new_state == State.ONLINE:
          hide_offline_overlay()

  sm = ConnectionStateMachine(
      check_fn=check_cluster,
      on_transition=on_transition,
      reconnect_interval=30,
  )
  sm.run()  # blocking loop
"""
from __future__ import annotations

import enum
import time
from typing import Any, Callable


class State(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    RECONNECTING = "reconnecting"


class ConnectionStateMachine:
    """Finite state machine managing cluster connectivity for Beagle endpoints.

    Parameters
    ----------
    check_fn:
        Callable() -> bool — returns True when cluster is reachable.
    on_transition:
        Optional callback(old_state: State, new_state: State, ctx: dict).
        ctx may contain: 'offline_since', 'countdown', 'cached_config'.
    reconnect_interval:
        Seconds between reconnect attempts while OFFLINE (default: 30).
    cache:
        Optional OfflineCache instance for cached config retrieval while offline.
    """

    def __init__(
        self,
        *,
        check_fn: Callable[[], bool],
        on_transition: Callable[[State, State, dict[str, Any]], None] | None = None,
        reconnect_interval: int = 30,
        cache: Any | None = None,
        _sleep: Callable[[float], None] = time.sleep,
        _now: Callable[[], float] = time.time,
    ) -> None:
        self._check_fn = check_fn
        self._on_transition = on_transition
        self._reconnect_interval = max(1, int(reconnect_interval))
        self._cache = cache
        self._sleep = _sleep
        self._now = _now

        self._state: State = State.ONLINE
        self._offline_since: float | None = None
        self._last_check: float = 0.0
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> State:
        return self._state

    def tick(self) -> State:
        """Run one connectivity check and advance state. Returns new state.

        Designed for use in tests and custom event loops. Use `run()` for
        blocking operation with automatic sleep between ticks.
        """
        reachable = self._safe_check()
        old_state = self._state
        new_state = self._compute_next(reachable)
        if new_state != old_state:
            self._state = new_state
            self._emit_transition(old_state, new_state)
        self._last_check = self._now()
        return self._state

    def run(self, max_ticks: int = 0) -> None:
        """Blocking run loop.

        max_ticks: if > 0, stop after that many ticks (for testing).
        """
        self._running = True
        tick_count = 0
        while self._running:
            self.tick()
            tick_count += 1
            if max_ticks and tick_count >= max_ticks:
                break
            self._sleep(self._reconnect_interval)

    def stop(self) -> None:
        """Signal the run loop to stop after the current tick."""
        self._running = False

    def ui_message(self) -> str:
        """Return a user-facing status message for the current state."""
        if self._state == State.ONLINE:
            return "Cluster verbunden."
        if self._state == State.RECONNECTING:
            return "Verbindungsversuch läuft…"
        # OFFLINE
        if self._offline_since is not None:
            elapsed = int(self._now() - self._offline_since)
            m, s = divmod(elapsed, 60)
            duration = f"{m}m {s}s" if m else f"{s}s"
            countdown = max(0, self._reconnect_interval - (elapsed % self._reconnect_interval))
            return (
                f"Cluster nicht erreichbar (seit {duration}). "
                f"Nächster Versuch in {countdown}s."
            )
        return "Cluster nicht erreichbar."

    def cached_config(self) -> dict[str, Any] | None:
        """Return the last cached cluster config or None."""
        if self._cache is not None:
            try:
                return self._cache.load()
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_check(self) -> bool:
        try:
            return bool(self._check_fn())
        except Exception:
            return False

    def _compute_next(self, reachable: bool) -> State:
        if reachable:
            if self._state in (State.OFFLINE, State.RECONNECTING):
                self._offline_since = None
            return State.ONLINE

        # Not reachable
        if self._state == State.ONLINE:
            self._offline_since = self._now()
            return State.OFFLINE

        if self._state == State.OFFLINE:
            return State.RECONNECTING

        if self._state == State.RECONNECTING:
            # Still offline after reconnect attempt — stay OFFLINE for UI display
            return State.OFFLINE

        return self._state  # fallback: no change

    def _emit_transition(self, old_state: State, new_state: State) -> None:
        if self._on_transition is None:
            return
        ctx: dict[str, Any] = {}
        if self._offline_since is not None:
            ctx["offline_since"] = self._offline_since
            ctx["countdown"] = self._reconnect_interval
        cfg = self.cached_config()
        if cfg is not None:
            ctx["cached_config"] = cfg
        try:
            self._on_transition(old_state, new_state, ctx)
        except Exception:
            pass
