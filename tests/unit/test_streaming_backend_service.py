import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from streaming_backend import StreamingBackendService


def test_windows_defaults_to_apollo() -> None:
    service = StreamingBackendService()

    decision = service.select_backend(guest_os="windows")

    assert decision.backend == "apollo"
    assert decision.virtual_display_supported is True
    assert decision.reason == "windows_default"


def test_linux_defaults_to_beagle_stream_server() -> None:
    service = StreamingBackendService()

    decision = service.select_backend(guest_os="linux")

    assert decision.backend == "beagle-stream-server"
    assert decision.virtual_display_supported is True
    assert decision.reason == "linux_default"


def test_linux_rejects_apollo_preference_by_default() -> None:
    service = StreamingBackendService(allow_apollo_on_linux=False)

    decision = service.select_backend(guest_os="linux", preferred_backend="apollo")

    assert decision.backend == "beagle-stream-server"
    assert decision.reason == "apollo_linux_not_supported"


def test_linux_can_allow_apollo_for_eval() -> None:
    service = StreamingBackendService(allow_apollo_on_linux=True)

    decision = service.select_backend(guest_os="linux", preferred_backend="apollo")

    assert decision.backend == "apollo"
    assert decision.reason == "preferred_backend"
    assert decision.virtual_display_supported is False


def test_unknown_os_uses_fallback() -> None:
    service = StreamingBackendService(fallback_backend="beagle-stream-server")

    decision = service.select_backend(guest_os="freebsd")

    assert decision.backend == "beagle-stream-server"
    assert decision.reason == "unknown_guest_os"
