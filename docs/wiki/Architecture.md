# Architecture

See [Platform Guide](PLATFORM_GUIDE.md#1-platform-overview) for full overview, components, and diagrams.

High-level: Clients (Plex, IPTV, Web) connect via REST, M3U/EPG, or HDHomeRun. SessionManager → ChannelManager → ProcessPoolManager → FFmpeg → StreamThrottler → Live MPEG-TS. EPG: get_timeline → SMT verify → export.

## FFmpeg Flag Architecture (2026-03 remediation)

All FFmpeg command builders import flags from `exstreamtv/ffmpeg/constants.py`. No flag string is hardcoded in individual builder files (`ffmpeg_builder.py`, `pipeline.py`). This is the single source of truth for:

- `FFLAGS_STREAMING` — `+genpts+discardcorrupt+igndts`
- `BSF_H264_ANNEXB` — `h264_mp4toannexb` (required on all H.264 → MPEG-TS COPY paths)
- `LOUDNORM_FILTER` — `loudnorm=I=-16:TP=-1.5:LRA=11` (EBU R128)
- `PIX_FMT`, `MPEGTS_FLAGS`, `PCR_PERIOD_MS`, `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`

See [Architecture Diagram 16](../architecture/DIAGRAMS.md#16-ffmpeg-command-builder-safety-layer-2026-03-remediation--ll-002-to-ll-016) and [Diagram 18 — six-layer AI/coding safety](../architecture/DIAGRAMS.md#18-six-layer-ai--coding-safety-enforcement-2026-03--post-merge-main).

**Default branch:** `main` carries the merged remediation from `2026-02-21-ufnw`; keep architecture docs and code on the same branch for audits.

**Last Revised:** 2026-03-21
