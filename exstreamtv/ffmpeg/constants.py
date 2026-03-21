"""
Shared FFmpeg flag constants for EXStreamTV.

Single source of truth for all FFmpeg command builders.
Import from here — NEVER hardcode these values in pipeline.py or ffmpeg_builder.py.

Derived from audit findings: LL-004, LL-005, LL-006, LL-011, LL-013, LL-016, LL-017, LL-018.
"""

# Input flags — applied to ALL sources (Plex, YouTube, Archive.org, local)
#
# +genpts         : Regenerate missing PTS from DTS. Required for remuxed content.
# +discardcorrupt : Skip corrupt packets instead of erroring. Prevents single-packet
#                   corruption from killing the stream.
# +igndts         : Ignore DTS when DTS > PTS. Required for B-frame content, YouTube,
#                   Archive.org, and Plex transcodes. Without this, FFmpeg emits DTS
#                   discontinuity warnings and drops packets at every GOP boundary.
#
# REMOVED +fastseek  — seek optimisation with zero benefit for pipe output; masked +igndts.
# REMOVED +low_delay — forces single-ref P-frames, drops B-frames on pre-recorded
#                      content, causes progressive A/V desync. (LL-004)
FFLAGS_STREAMING = "+genpts+discardcorrupt+igndts"

# H.264 bitstream filter
# Plex/MP4 sends H.264 as length-prefixed AVCC NAL units.
# MPEG-TS requires Annex B start codes (0x00 0x00 0x00 0x01).
# Without this on the COPY path, first GOP is corrupted or black on ALL decoders.
# NON-OPTIONAL when VideoFormat.COPY is used. (LL-006)
BSF_H264_ANNEXB = "h264_mp4toannexb"

# MPEG-TS mux flags
# resend_headers: Resend PAT/PMT on every keyframe so Plex detects mid-stream changes.
MPEGTS_FLAGS = "resend_headers"

# PCR period in ms. 40ms = one PCR per frame at 25fps. Keeps Plex clock sync tight.
PCR_PERIOD_MS = "40"

# Pixel format — only format guaranteed compatible with all Plex/Jellyfin/Emby/HDHomeRun
# clients. Always force on output. (LL-012)
# NOTE: When hardware decode is active, prepend "hwdownload" BEFORE "format=yuv420p".
# GPU surfaces cannot be formatted directly.
PIX_FMT = "yuv420p"

# Standard audio output settings for MPEG-TS
AUDIO_SAMPLE_RATE = "48000"
AUDIO_CHANNELS = "2"

# EBU R128 loudness normalisation — broadcast standard used by Plex/Jellyfin/streaming.
# ALWAYS use this target. NEVER use I=-24 (ATSC A/85) — causes audible volume jumps
# between items when channels switch between the two FFmpeg builders. (LL-017)
LOUDNORM_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"
