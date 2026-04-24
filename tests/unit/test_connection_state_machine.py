"""Unit tests for Plan 19 L168: Offline-Mode state machine.

Validates:
  - ONLINE → OFFLINE transition when cluster unreachable
  - OFFLINE → RECONNECTING on next poll
  - RECONNECTING → ONLINE on cluster recovery
  - RECONNECTING → OFFLINE when still unreachable
  - on_transition callback fires with correct args
  - ui_message() returns correct messages per state
  - cached_config() returned via OfflineCache when OFFLINE
  - ONLINE → ONLINE stays ONLINE (no spurious transitions)
  - check_fn exceptions handled gracefully (treated as unreachable)
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_RUNTIME = Path(__file__).resolve().parents[2] / "thin-client-assistant" / "runtime"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from connection_state_machine import ConnectionStateMachine, State  # type: ignore[import]


def _make_sm(
    reachable_seq: list[bool],
    on_transition=None,
    cache=None,
    reconnect_interval: int = 5,
):
    """Build a state machine that plays through a sequence of check results."""
    idx = [0]

    def _check() -> bool:
        val = reachable_seq[idx[0] % len(reachable_seq)]
        idx[0] += 1
        return val

    clock = [0.0]

    def _now() -> float:
        return clock[0]

    def _sleep(s: float) -> None:
        clock[0] += s

    return ConnectionStateMachine(
        check_fn=_check,
        on_transition=on_transition,
        reconnect_interval=reconnect_interval,
        cache=cache,
        _sleep=_sleep,
        _now=_now,
    )


class TestConnectionStateMachineBasic(unittest.TestCase):

    def test_initial_state_is_online(self):
        sm = _make_sm([True])
        self.assertEqual(sm.state, State.ONLINE)

    def test_online_stays_online_when_reachable(self):
        sm = _make_sm([True, True, True])
        sm.tick(); sm.tick(); sm.tick()
        self.assertEqual(sm.state, State.ONLINE)

    def test_online_to_offline_on_unreachable(self):
        sm = _make_sm([False])
        sm.tick()
        self.assertEqual(sm.state, State.OFFLINE)

    def test_offline_to_reconnecting_on_next_poll(self):
        sm = _make_sm([False, False])
        sm.tick()  # ONLINE → OFFLINE
        sm.tick()  # OFFLINE → RECONNECTING
        self.assertEqual(sm.state, State.RECONNECTING)

    def test_reconnecting_to_online_on_recovery(self):
        sm = _make_sm([False, False, True])
        sm.tick()  # ONLINE → OFFLINE
        sm.tick()  # OFFLINE → RECONNECTING
        sm.tick()  # RECONNECTING → ONLINE
        self.assertEqual(sm.state, State.ONLINE)

    def test_reconnecting_to_offline_when_still_unreachable(self):
        sm = _make_sm([False, False, False])
        sm.tick()  # ONLINE → OFFLINE
        sm.tick()  # OFFLINE → RECONNECTING
        sm.tick()  # RECONNECTING → OFFLINE (still down)
        self.assertEqual(sm.state, State.OFFLINE)

    def test_full_cycle_online_offline_online(self):
        """Complete cycle: online → offline → reconnecting → online."""
        sm = _make_sm([True, False, False, True, True])
        states = [sm.tick() for _ in range(5)]
        self.assertEqual(states[0], State.ONLINE)      # was online, still online
        self.assertEqual(states[1], State.OFFLINE)     # cluster lost
        self.assertEqual(states[2], State.RECONNECTING)
        self.assertEqual(states[3], State.ONLINE)      # recovered
        self.assertEqual(states[4], State.ONLINE)

    def test_check_fn_exception_treated_as_unreachable(self):
        def _failing():
            raise ConnectionError("timeout")

        sm = ConnectionStateMachine(check_fn=_failing, _sleep=lambda _: None, _now=float)
        sm.tick()
        self.assertEqual(sm.state, State.OFFLINE)


class TestConnectionStateMachineCallbacks(unittest.TestCase):

    def test_on_transition_called_on_state_change(self):
        transitions: list[tuple[State, State]] = []

        def _cb(old, new, ctx):
            transitions.append((old, new))

        sm = _make_sm([False, False, True], on_transition=_cb)
        sm.tick(); sm.tick(); sm.tick()

        self.assertIn((State.ONLINE, State.OFFLINE), transitions)
        self.assertIn((State.OFFLINE, State.RECONNECTING), transitions)
        self.assertIn((State.RECONNECTING, State.ONLINE), transitions)

    def test_on_transition_not_called_without_state_change(self):
        called = [0]

        def _cb(old, new, ctx):
            called[0] += 1

        sm = _make_sm([True, True, True], on_transition=_cb)
        sm.tick(); sm.tick(); sm.tick()
        self.assertEqual(called[0], 0)

    def test_on_transition_ctx_contains_offline_since(self):
        ctx_received: list[dict] = []

        def _cb(old, new, ctx):
            ctx_received.append(dict(ctx))

        sm = _make_sm([False], on_transition=_cb)
        sm.tick()

        self.assertTrue(len(ctx_received) > 0)
        self.assertIn("offline_since", ctx_received[0])

    def test_on_transition_ctx_contains_cached_config(self):
        mock_cache = MagicMock()
        mock_cache.load.return_value = {"pools": ["pool-1"]}

        ctx_received: list[dict] = []

        def _cb(old, new, ctx):
            ctx_received.append(dict(ctx))

        sm = _make_sm([False], on_transition=_cb, cache=mock_cache)
        sm.tick()

        self.assertIn("cached_config", ctx_received[0])
        self.assertEqual(ctx_received[0]["cached_config"], {"pools": ["pool-1"]})

    def test_on_transition_exception_does_not_crash_sm(self):
        def _bad_cb(old, new, ctx):
            raise RuntimeError("UI broken")

        sm = _make_sm([False], on_transition=_bad_cb)
        # Must not raise
        sm.tick()
        self.assertEqual(sm.state, State.OFFLINE)


class TestConnectionStateMachineUI(unittest.TestCase):

    def test_ui_message_online(self):
        sm = _make_sm([True])
        sm.tick()
        msg = sm.ui_message()
        self.assertIn("verbunden", msg.lower())

    def test_ui_message_offline_contains_reconnect_info(self):
        sm = _make_sm([False])
        sm.tick()
        msg = sm.ui_message()
        self.assertIn("nicht erreichbar", msg.lower())
        self.assertIn("Versuch", msg)

    def test_ui_message_reconnecting(self):
        sm = _make_sm([False, False])
        sm.tick(); sm.tick()
        msg = sm.ui_message()
        # Either "Verbindungsversuch" or "nicht erreichbar"
        self.assertTrue(
            "verbindungsversuch" in msg.lower() or "erreichbar" in msg.lower()
        )

    def test_cached_config_returned_from_cache(self):
        mock_cache = MagicMock()
        mock_cache.load.return_value = {"stream_url": "rtsp://beagle-100"}

        sm = _make_sm([False], cache=mock_cache)
        sm.tick()
        cfg = sm.cached_config()
        self.assertEqual(cfg, {"stream_url": "rtsp://beagle-100"})

    def test_cached_config_none_when_no_cache(self):
        sm = _make_sm([False])
        sm.tick()
        self.assertIsNone(sm.cached_config())


class TestConnectionStateMachineWithOfflineCache(unittest.TestCase):
    """Integration test: state machine + OfflineCache together."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def test_offline_mode_serves_cached_config(self):
        """When offline, the state machine can serve the last cached config."""
        from offline_cache import OfflineCache  # type: ignore[import]

        cache = OfflineCache(
            cache_file=Path(self._tmpdir) / "offline-cache.bin",
            ttl=3600,
            machine_id_file=None,  # uses fallback machine-id
        )

        # Simulate: endpoint was online and stored a config
        stored_config = {"pools": ["gaming-pool"], "cluster_version": "7.1.0"}
        cache.store(stored_config)

        transitions: list[tuple[State, State]] = []

        def _cb(old, new, ctx):
            transitions.append((old, new))

        sm = _make_sm([False, False, True], on_transition=_cb, cache=cache)

        sm.tick()  # ONLINE → OFFLINE
        self.assertEqual(sm.state, State.OFFLINE)
        # Cached config available while offline
        cfg = sm.cached_config()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["pools"], ["gaming-pool"])

        sm.tick()  # OFFLINE → RECONNECTING
        sm.tick()  # RECONNECTING → ONLINE

        self.assertEqual(sm.state, State.ONLINE)
        self.assertIn((State.RECONNECTING, State.ONLINE), transitions)


if __name__ == "__main__":
    unittest.main()
