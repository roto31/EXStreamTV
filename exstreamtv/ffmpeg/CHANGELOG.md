# FFmpeg Pipeline Component Changelog

All notable changes to the FFmpeg Pipeline component will be documented in this file.

## [2.6.0] - 2026-01-31
### Added - Tunarr Stream Pickers
- **SubtitleStreamPicker** (`subtitle_picker.py`) - Intelligent subtitle selection from Tunarr
  - `SubtitleStream` dataclass for stream metadata
  - `SubtitlePreferences` for user preferences
  - Language preference matching with priority
  - Text vs image subtitle type preference
  - SDH/CC detection and handling
  - FFmpeg argument generation for burn-in
  - `SubtitleType` enum (text, image, unknown)
- **AudioStreamPicker** (`audio_picker.py`) - Intelligent audio selection from Tunarr
  - `AudioStream` dataclass for stream metadata
  - `AudioPreferences` for user preferences
  - Language preference matching with priority
  - Surround vs stereo layout preference
  - Commentary track detection and handling
  - Downmix configuration (stereo, mono, 5.1)
  - `AudioLayout` enum (stereo, surround, mono, unknown)
- Updated `__init__.py` with new exports

## [2.5.0] - 2026-01-17
### Changed
- No changes to FFmpeg module in this release

## [1.8.0] - 2026-01-14
### Added
- `process_pool.py` - FFmpeg process manager
- Semaphore-based concurrency limiting
- Process health monitoring with CPU/memory tracking
- Graceful shutdown and error callbacks

## [1.0.8] - 2026-01-14
### Added
- **State Management**
  - `state/frame_state.py` - Frame tracking (size, format, location)
  - `state/ffmpeg_state.py` - Pipeline configuration

- **Video Filters** (10 filters)
  - ScaleFilter, PadFilter, CropFilter, TonemapFilter, DeinterlaceFilter
  - PixelFormatFilter, HardwareUploadFilter, HardwareDownloadFilter
  - RealtimeFilter, WatermarkFilter

- **Audio Filters** (3 filters)
  - AudioNormalizeFilter, AudioResampleFilter, AudioPadFilter

- **Video Encoders** (14 encoders)
  - Software: libx264, libx265, copy
  - VideoToolbox (macOS): h264_videotoolbox, hevc_videotoolbox
  - NVENC (NVIDIA): h264_nvenc, hevc_nvenc
  - QSV (Intel): h264_qsv, hevc_qsv
  - VAAPI (Linux): h264_vaapi, hevc_vaapi
  - AMF (AMD): h264_amf, hevc_amf

- **Audio Encoders** (4 encoders)
  - aac, ac3, pcm_s16le, copy

## [1.0.2] - 2026-01-14
### Added
- Initial FFmpeg module with hardware detection
- Pipeline builder with StreamTV bug fixes preserved
- Encoder auto-selection based on platform
