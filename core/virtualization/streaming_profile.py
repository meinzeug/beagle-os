from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class StreamingEncoder(str, Enum):
    AUTO = "auto"
    NVENC = "nvenc"
    VAAPI = "vaapi"
    QUICKSYNC = "quicksync"
    SOFTWARE = "software"


class StreamingColorCodec(str, Enum):
    H264 = "h264"
    H265 = "h265"
    AV1 = "av1"


@dataclass(frozen=True)
class StreamingProfile:
    encoder: StreamingEncoder = StreamingEncoder.AUTO
    bitrate_kbps: int = 20000
    resolution: str = "1920x1080"
    fps: int = 60
    color: StreamingColorCodec = StreamingColorCodec.H265
    hdr: bool = False


def _normalize_resolution(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("@", "x")
    if "x" not in raw:
        raise ValueError("resolution must be WIDTHxHEIGHT")
    width_text, height_text = raw.split("x", 1)
    width = int(width_text)
    height = int(height_text)
    if width < 640 or width > 7680:
        raise ValueError("resolution width out of range")
    if height < 360 or height > 4320:
        raise ValueError("resolution height out of range")
    return f"{width}x{height}"


def streaming_profile_from_payload(payload: dict[str, Any] | None) -> StreamingProfile:
    body = dict(payload or {})
    try:
        encoder = StreamingEncoder(str(body.get("encoder", StreamingEncoder.AUTO.value) or StreamingEncoder.AUTO.value).lower())
    except ValueError as exc:
        raise ValueError(f"invalid streaming encoder: {body.get('encoder')}") from exc
    try:
        color = StreamingColorCodec(str(body.get("color", StreamingColorCodec.H265.value) or StreamingColorCodec.H265.value).lower())
    except ValueError as exc:
        raise ValueError(f"invalid streaming color codec: {body.get('color')}") from exc

    bitrate_kbps = int(body.get("bitrate_kbps", 20000) or 20000)
    if bitrate_kbps < 2000 or bitrate_kbps > 150000:
        raise ValueError("bitrate_kbps out of range")

    fps = int(body.get("fps", 60) or 60)
    if fps < 24 or fps > 240:
        raise ValueError("fps out of range")

    return StreamingProfile(
        encoder=encoder,
        bitrate_kbps=bitrate_kbps,
        resolution=_normalize_resolution(body.get("resolution", "1920x1080")),
        fps=fps,
        color=color,
        hdr=bool(body.get("hdr", False)),
    )


def streaming_profile_to_dict(profile: StreamingProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "encoder": profile.encoder.value,
        "bitrate_kbps": int(profile.bitrate_kbps),
        "resolution": str(profile.resolution),
        "fps": int(profile.fps),
        "color": profile.color.value,
        "hdr": bool(profile.hdr),
    }