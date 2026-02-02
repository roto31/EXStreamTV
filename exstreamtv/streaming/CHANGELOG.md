# Streaming Engine Component Changelog

All notable changes to the Streaming Engine component will be documented in this file.

## [2.6.0] - 2026-01-31
### Added - Tunarr/dizqueTV Integration
- **Session Manager** (`session_manager.py`) - Tunarr-style client connection tracking
  - `StreamSession` dataclass for individual client sessions
  - `SessionManager` for centralized session lifecycle
  - Idle session cleanup with configurable timeout
  - Per-channel session limits
  - Error and restart tracking
- **Stream Throttler** (`throttler.py`) - dizqueTV-style rate limiting
  - `StreamThrottler` for bitrate-based delivery pacing
  - Multiple modes: realtime, burst, adaptive, disabled
  - Keepalive packet support during stalls
  - Client buffer overrun prevention
- **Error Screen Generator** (`error_screens.py`) - dizqueTV error screen port
  - `ErrorScreenGenerator` for fallback streams during failures
  - Visual modes: text, static, test_pattern, slate, custom_image
  - Audio modes: silent, sine_wave, white_noise, beep
  - FFmpeg command builder for MPEG-TS error streams
- **Channel Manager Integration**
  - Throttler integration for rate limiting
  - Error screen fallback during auto-restart
  - AI monitoring integration hooks
  - Graceful degradation support

### Changed
- Updated `channel_manager.py` with new component integrations
- Updated `__init__.py` with new exports

## [2.5.0] - 2026-01-17
### Changed
- No changes to streaming module in this release

## [1.0.3] - 2026-01-14
### Added
- Complete streaming infrastructure ported from StreamTV
- `channel_manager.py` - ErsatzTV-style continuous streaming
- `mpegts_streamer.py` - FFmpeg MPEG-TS generation
- `error_handler.py` - Error classification and recovery
- `retry_manager.py` - Retry logic with backoff

### Bug Fixes Preserved
- **Bitstream filters**: `-bsf:v h264_mp4toannexb,dump_extra` for H.264 copy mode
- **Real-time flag**: `-re` for pre-recorded content (prevents buffer underruns)
- **Error tolerance**: `-fflags +genpts+discardcorrupt+igndts` for corrupt streams
- **VideoToolbox restrictions**: MPEG-4 codec software fallback on macOS
- **Extended timeouts**: 60s for Archive.org/Plex, 30s default
- **Reconnection**: Automatic reconnection for HTTP streams

### Features
- Smart codec detection (copy vs transcode)
- Multi-client broadcast to single stream
- Playout timeline tracking with resume
- 15 error types with recovery strategies
