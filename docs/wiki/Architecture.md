# Architecture

See [Platform Guide](PLATFORM_GUIDE.md#1-platform-overview) for full overview, components, and diagrams.

High-level: Clients (Plex, IPTV, Web) connect via REST, M3U/EPG, or HDHomeRun. SessionManager → ChannelManager → ProcessPoolManager → FFmpeg → StreamThrottler → Live MPEG-TS. EPG: get_timeline → SMT verify → export.

## FFmpeg Flag Architecture (2026-03 remediation)

All FFmpeg command builders import flags from `exstreamtv/ffmpeg/constants.py`. No flag string is hardcoded in individual builder files (`ffmpeg_builder.py`, `pipeline.py`). This is the single source of truth for:

- `FFLAGS_STREAMING` — `+genpts+discardcorrupt+igndts`
- `BSF_H264_ANNEXB` — `h264_mp4toannexb` (required on all H.264 → MPEG-TS COPY paths)
- `LOUDNORM_FILTER` — `loudnorm=I=-16:TP=-1.5:LRA=11` (EBU R128)
- `PIX_FMT`, `MPEGTS_FLAGS`, `PCR_PERIOD_MS`, `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`

See [Architecture Diagram 16](../architecture/DIAGRAMS.md#16-ffmpeg-command-builder-safety-layer-2026-03-remediation--ll-002-to-ll-016).

**Last Revised:** 2026-03-20
