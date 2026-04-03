"""Minimal transcode config for UpdateTranscodeCommand (extensible)."""

from dataclasses import dataclass, field


@dataclass
class TranscodeConfig:
    """FFmpeg-oriented transcode settings placeholder for command pattern."""

    ffmpeg_binary: str = "ffmpeg"
    video_bitrate: str | None = None
    audio_bitrate: str | None = None
    x264_preset: str | None = None
    hls_segment_path: str | None = None
    hls_playlist_path: str | None = None
    hls_segment_duration: int | None = None
    hls_list_size: int | None = None
    use_videotoolbox: bool = False
    extra: dict[str, str] = field(default_factory=dict)
