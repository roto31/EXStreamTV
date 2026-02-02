# EXStreamTV v1.0.3 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: Streaming Infrastructure

## Summary

Complete streaming infrastructure ported from StreamTV with all bug fixes preserved.

## Components at This Version

| Component | Version | Status |
|-----------|---------|--------|
| Streaming Engine | 1.0.3 | Created |

## Streaming Module Files

- `exstreamtv/streaming/channel_manager.py` - ErsatzTV-style continuous streaming
- `exstreamtv/streaming/mpegts_streamer.py` - FFmpeg MPEG-TS generation
- `exstreamtv/streaming/error_handler.py` - Error classification and recovery
- `exstreamtv/streaming/retry_manager.py` - Retry logic with backoff

## Bug Fixes Preserved

- **Bitstream filters**: `-bsf:v h264_mp4toannexb,dump_extra` for H.264 copy mode
- **Real-time flag**: `-re` for pre-recorded content
- **Error tolerance**: `-fflags +genpts+discardcorrupt+igndts`
- **VideoToolbox restrictions**: MPEG-4 codec software fallback on macOS
- **Extended timeouts**: 60s for Archive.org/Plex, 30s default
- **Reconnection**: Automatic reconnection for HTTP streams

## Features

- Smart codec detection (copy vs transcode)
- Multi-client broadcast to single stream
- Playout timeline tracking with resume
- 15 error types with recovery strategies

## Previous Version

← v1.0.2: Database Models & FFmpeg

## Next Version

→ v1.0.4: AI Agent Module
