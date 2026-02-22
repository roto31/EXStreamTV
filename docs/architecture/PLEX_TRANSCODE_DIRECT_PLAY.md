# Plex Transcode vs Direct Play for EXStreamTV Tuner Streams

## Purpose

This document describes how Plex decides between direct play and transcoding for live tuner streams, and EXStreamTV’s chosen strategy so the platform behaves like an accurate TV broadcast system when used with Plex DVR.

## Plex behaviour for live tuner streams

- Plex treats live tuner streams like other media: it fetches the stream URL (from the M3U or tuner setup) and then decides **per client** whether to direct play or transcode.
- **Direct play**: No server-side re-encoding. The stream is sent to the client as-is. Requirements:
  - **Container**: Compatible with the client (e.g. MPEG-TS, fMP4/HLS).
  - **Video codec**: H.264/AVC, H.265/HEVC, or MPEG-2 (client-dependent).
  - **Audio codec**: AAC, AC-3, MP3, etc. (client-dependent).
  - **Bitrate and resolution**: Within the client’s capabilities.
- **Transcode**: If the stream does not meet the client’s direct-play profile, Plex transcodes on the server (CPU/GPU) and sends a compatible stream to the client. This is resource-intensive for live streams.

So: the **client device and its supported codecs/profiles** drive the decision. The server (Plex) either forwards the stream (direct play) or re-encodes (transcode).

## What EXStreamTV serves today

- **HLS**: `/iptv/channel/{channel_number}.m3u8` – HLS playlist and segments (format depends on FFmpeg/streaming pipeline).
- **MPEG-TS**: `/iptv/channel/{channel_number}.ts` – continuous MPEG-TS (e.g. H.264 + AAC or passthrough from source).

The actual codecs/containers depend on the channel’s source (Plex library, YouTube, Archive.org, etc.) and any transcoding already applied in the streaming pipeline (e.g. in `exstreamtv/streaming/` or FFmpeg profiles). There is currently **no EXStreamTV-level “transcode for Plex”** step; we expose one URL per channel and Plex (and the client) decide.

## EXStreamTV strategy (design)

### Chosen approach: **Expose stream URL + metadata; Plex decides (Phase 1)**

- **Behaviour**: EXStreamTV provides a single stream URL per channel (HLS or TS) and the EPG (XMLTV). Plex and the client use their normal logic to direct play or transcode. No additional transcoding service is run inside EXStreamTV solely for Plex.
- **Rationale**: Matches a classic “tuner” model: one stream per channel, guide matches playout (§6). Keeps EXStreamTV simple and avoids duplicate transcoding (our pipeline may already output compatible codecs).
- **Trade-offs**:
  - **Pro**: No extra CPU/GPU for a separate “Plex transcode” path; one source of truth for the stream.
  - **Con**: If the channel’s native stream is not client-friendly (e.g. HEVC-only or high bitrate), Plex will transcode on the Plex server; we do not offer a “direct-play friendly” alternate URL from EXStreamTV today.

### Optional future: **Direct-play–friendly URL (Phase 2)**

- **Idea**: For channels where the native stream is often transcoded by Plex, optionally run a dedicated transcoder (e.g. FFmpeg) that outputs a “direct-play friendly” stream (e.g. H.264 + AAC, constrained bitrate) and expose that as a second URL or as the primary URL for Plex.
- **Design choices if implemented**:
  - **Where**: Same server vs separate worker (resource and isolation).
  - **When**: Per-channel always-on vs on first Plex client connect (latency vs CPU).
  - **How advertised**: M3U/XMLTV could point Plex to the transcode URL, or we document a separate “Plex-optimized” endpoint.
- **Implementation**: Would live in `exstreamtv/streaming/` (or a small transcoder service), wired to channel manager and to M3U/EPG so the guide still matches the stream (§6). Not in scope for Phase 1.

## Implementation status

| Item | Status |
|------|--------|
| Document Plex transcode/direct-play behaviour for live tuner | Done (this doc). |
| EXStreamTV strategy: expose URL + metadata, Plex decides | Adopted (Phase 1). |
| Optional transcode for “direct-play friendly” URL | Deferred (Phase 2). |
| Wire transcoding into Plex DVR/tuner (if Phase 2) | Not started. |

## References

- Plex: [Direct Play, Direct Stream, and Transcoding](https://support.plex.tv/articles/200250387-streaming-media-direct-play-and-direct-stream/)
- Plex: [Supported media formats](https://support.plex.tv/articles/203824396-what-media-formats-are-supported/)
- EXStreamTV: EPG/playout alignment contract – `docs/architecture/EPG_PLAYOUT_ALIGNMENT.md`
- EXStreamTV: Plex setup – `docs/guides/PLEX_SETUP.md`
