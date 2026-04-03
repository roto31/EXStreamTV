"""
Factory Method for FFmpeg argv lists.

AGENTS.md: use exstreamtv/ffmpeg/constants.py — never duplicate streaming flags.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from exstreamtv.ffmpeg.constants import (
    AUDIO_CHANNELS,
    AUDIO_SAMPLE_RATE,
    BSF_H264_ANNEXB,
    FFLAGS_STREAMING,
    LOUDNORM_FILTER,
    MPEGTS_FLAGS,
    PCR_PERIOD_MS,
    PIX_FMT,
)
from exstreamtv.patterns.commands.config_types import TranscodeConfig


@dataclass
class StreamSource:
    url: str


class StreamMode(str, Enum):
    PASSTHROUGH = "passthrough"
    H264_VIDEOTOOLBOX = "h264_videotoolbox"
    H264_SOFTWARE = "h264_software"
    HLS_PASSTHROUGH = "hls_passthrough"
    HLS_TRANSCODE = "hls_transcode"


class FFmpegCommandBuilder(ABC):
    @abstractmethod
    def build(self, source: StreamSource, config: TranscodeConfig) -> list[str]:
        """Return full FFmpeg argv (executable first)."""

    def _base_input_args(self, source: StreamSource) -> list[str]:
        return [
            "-fflags",
            FFLAGS_STREAMING,
            "-re",
            "-i",
            source.url,
            "-reconnect",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "5",
        ]


class PassthroughBuilder(FFmpegCommandBuilder):
    def build(self, source: StreamSource, config: TranscodeConfig) -> list[str]:
        return [
            config.ffmpeg_binary,
            *self._base_input_args(source),
            "-c:v",
            "copy",
            "-bsf:v",
            BSF_H264_ANNEXB,
            "-c:a",
            "copy",
            "-f",
            "mpegts",
            "-muxrate",
            "10M",
            "-mpegts_flags",
            MPEGTS_FLAGS,
            "-pcr_period",
            PCR_PERIOD_MS,
            "pipe:1",
        ]


class H264VideoToolboxBuilder(FFmpegCommandBuilder):
    def build(self, source: StreamSource, config: TranscodeConfig) -> list[str]:
        vb = config.video_bitrate or "4000k"
        ab = config.audio_bitrate or "192k"
        return [
            config.ffmpeg_binary,
            *self._base_input_args(source),
            "-c:v",
            "h264_videotoolbox",
            "-b:v",
            vb,
            "-c:a",
            "aac",
            "-b:a",
            ab,
            "-ar",
            AUDIO_SAMPLE_RATE,
            "-ac",
            AUDIO_CHANNELS,
            "-pix_fmt",
            PIX_FMT,
            "-af",
            LOUDNORM_FILTER,
            "-f",
            "mpegts",
            "-muxrate",
            "10M",
            "-mpegts_flags",
            MPEGTS_FLAGS,
            "pipe:1",
        ]


class H264SoftwareBuilder(FFmpegCommandBuilder):
    def build(self, source: StreamSource, config: TranscodeConfig) -> list[str]:
        vb = config.video_bitrate or "4000k"
        ab = config.audio_bitrate or "192k"
        preset = config.x264_preset or "veryfast"
        return [
            config.ffmpeg_binary,
            *self._base_input_args(source),
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-b:v",
            vb,
            "-c:a",
            "aac",
            "-b:a",
            ab,
            "-ar",
            AUDIO_SAMPLE_RATE,
            "-ac",
            AUDIO_CHANNELS,
            "-pix_fmt",
            PIX_FMT,
            "-af",
            LOUDNORM_FILTER,
            "-f",
            "mpegts",
            "-mpegts_flags",
            MPEGTS_FLAGS,
            "pipe:1",
        ]


class HLSPassthroughBuilder(FFmpegCommandBuilder):
    def build(self, source: StreamSource, config: TranscodeConfig) -> list[str]:
        seg = config.hls_segment_path or "/tmp/hls/%v/segment%d.ts"
        pls = config.hls_playlist_path or "/tmp/hls/playlist.m3u8"
        ht = str(config.hls_segment_duration or 2)
        hs = str(config.hls_list_size or 5)
        return [
            config.ffmpeg_binary,
            *self._base_input_args(source),
            "-c",
            "copy",
            "-f",
            "hls",
            "-hls_time",
            ht,
            "-hls_list_size",
            hs,
            "-hls_flags",
            "delete_segments+append_list",
            "-hls_segment_filename",
            seg,
            pls,
        ]


class HLSTranscodeBuilder(FFmpegCommandBuilder):
    def build(self, source: StreamSource, config: TranscodeConfig) -> list[str]:
        seg = config.hls_segment_path or "/tmp/hls/%v/segment%d.ts"
        pls = config.hls_playlist_path or "/tmp/hls/playlist.m3u8"
        ht = str(config.hls_segment_duration or 2)
        hs = str(config.hls_list_size or 5)
        vcodec = "h264_videotoolbox" if config.use_videotoolbox else "libx264"
        vb = config.video_bitrate or "4000k"
        ab = config.audio_bitrate or "192k"
        return [
            config.ffmpeg_binary,
            *self._base_input_args(source),
            "-c:v",
            vcodec,
            "-b:v",
            vb,
            "-c:a",
            "aac",
            "-b:a",
            ab,
            "-f",
            "hls",
            "-hls_time",
            ht,
            "-hls_list_size",
            hs,
            "-hls_flags",
            "delete_segments+append_list",
            "-hls_segment_filename",
            seg,
            pls,
        ]


_BUILDER_MAP: dict[StreamMode, type[FFmpegCommandBuilder]] = {
    StreamMode.PASSTHROUGH: PassthroughBuilder,
    StreamMode.H264_VIDEOTOOLBOX: H264VideoToolboxBuilder,
    StreamMode.H264_SOFTWARE: H264SoftwareBuilder,
    StreamMode.HLS_PASSTHROUGH: HLSPassthroughBuilder,
    StreamMode.HLS_TRANSCODE: HLSTranscodeBuilder,
}


def get_ffmpeg_builder(mode: StreamMode) -> FFmpegCommandBuilder:
    cls = _BUILDER_MAP.get(mode)
    if cls is None:
        raise ValueError(f"No builder for stream mode: {mode!r}")
    return cls()
