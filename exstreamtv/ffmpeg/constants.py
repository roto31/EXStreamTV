"""
Shared FFmpeg flag constants.

Single source of truth for all command builders (pipeline.py and ffmpeg_builder.py).
Import from here — never hardcode these values in individual builders.
"""

# +genpts   : regenerate missing PTS from DTS
# +discardcorrupt : skip corrupt packets instead of erroring
# +igndts   : ignore DTS when DTS > PTS (B-frame content, YouTube, Plex transcodes)
FFLAGS_STREAMING = "+genpts+discardcorrupt+igndts"

# H.264 bitstream filter: converts MP4/AVCC length-prefixed NAL units to
# Annex B start-code format required by MPEG-TS.
BSF_H264_ANNEXB = "h264_mp4toannexb"

MPEGTS_FLAGS = "resend_headers"
PCR_PERIOD_MS = "40"

PIX_FMT = "yuv420p"

# EBU R128 broadcast standard
LOUDNORM_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"

AUDIO_SAMPLE_RATE = "48000"
AUDIO_CHANNELS = "2"
