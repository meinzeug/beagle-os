from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_beagle_provider_uses_virtio_video_not_legacy_vga() -> None:
    provider = (ROOT / "beagle-host" / "providers" / "beagle_host_provider.py").read_text(encoding="utf-8")

    assert "<video><model type='virtio'" in provider
    assert "<video><model type='vga'" not in provider