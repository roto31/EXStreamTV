# EXStreamTV v1.0.8 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: FFmpeg Pipeline Enhancement

## Summary

ErsatzTV-compatible FFmpeg pipeline features including state management, filters, and encoders.

## FFmpeg Pipeline Components

### State Management
- `state/frame_state.py` - Frame tracking (size, format, location)
- `state/ffmpeg_state.py` - Pipeline configuration

### Video Filters (10)
- ScaleFilter, PadFilter, CropFilter, TonemapFilter, DeinterlaceFilter
- PixelFormatFilter, HardwareUploadFilter, HardwareDownloadFilter
- RealtimeFilter, WatermarkFilter

### Audio Filters (3)
- AudioNormalizeFilter, AudioResampleFilter, AudioPadFilter

### Video Encoders (14)
- **Software**: libx264, libx265, copy
- **VideoToolbox (macOS)**: h264_videotoolbox, hevc_videotoolbox
- **NVENC (NVIDIA)**: h264_nvenc, hevc_nvenc
- **QSV (Intel)**: h264_qsv, hevc_qsv
- **VAAPI (Linux)**: h264_vaapi, hevc_vaapi
- **AMF (AMD)**: h264_amf, hevc_amf

### Audio Encoders (4)
- aac, ac3, pcm_s16le, copy

## Previous Version

← v1.0.7: Import Path Updates

## Next Version

→ v1.0.9: ErsatzTV Playout Engine
