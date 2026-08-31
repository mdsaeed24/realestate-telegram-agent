"""ffprobe gate for video.

A video that is not H.264 + AAC with a single audio stream can upload
successfully and still fail to preview or play inline for the recipient. That
failure is silent, so it is checked before sending, not inferred from a 200.
"""
import asyncio
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    video_codec: str | None
    audio_codec: str | None
    audio_stream_count: int
    faststart: bool | None
    problems: list[str]


def evaluate(streams: list[dict], format_info: dict | None = None) -> ProbeResult:
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    problems: list[str] = []

    vcodec = video[0].get("codec_name") if video else None
    acodec = audio[0].get("codec_name") if audio else None

    if not video:
        problems.append("no video stream")
    elif vcodec != "h264":
        problems.append(f"video codec is {vcodec}, must be h264")

    if not audio:
        problems.append("no audio stream")
    elif acodec != "aac":
        problems.append(f"audio codec is {acodec}, must be aac")

    if len(audio) > 1:
        problems.append(f"{len(audio)} audio streams, must be exactly 1")

    faststart = None
    if format_info is not None:
        # A moov atom at the end forces a full download before playback starts.
        faststart = "faststart" in (format_info.get("tags", {}) or {}).get("comment", "").lower() \
            or format_info.get("start_time") is not None
    return ProbeResult(
        ok=not problems,
        video_codec=vcodec,
        audio_codec=acodec,
        audio_stream_count=len(audio),
        faststart=faststart,
        problems=problems,
    )


async def probe(path: str) -> ProbeResult:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        return ProbeResult(False, None, None, 0, None,
                           [f"ffprobe failed: {err.decode().strip()}"])
    data = json.loads(out)
    return evaluate(data.get("streams", []), data.get("format"))
