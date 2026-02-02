# Hardware Transcoding Guide

Leverage your GPU for efficient video transcoding with significantly reduced CPU usage.

## Table of Contents

- [Overview](#overview)
- [Supported Hardware](#supported-hardware)
- [macOS VideoToolbox](#macos-videotoolbox)
- [NVIDIA NVENC](#nvidia-nvenc)
- [Intel Quick Sync (QSV)](#intel-quick-sync-qsv)
- [AMD AMF/VCE](#amd-amfvce)
- [Linux VAAPI](#linux-vaapi)
- [FFmpeg Profiles](#ffmpeg-profiles)
- [Performance Tuning](#performance-tuning)
- [Troubleshooting](#troubleshooting)

---

## Overview

Hardware transcoding uses your GPU's dedicated video processing unit instead of the CPU. Benefits include:

- **Lower CPU usage** - Free up CPU for other tasks
- **Higher throughput** - Transcode multiple streams simultaneously
- **Reduced power consumption** - GPUs are more efficient for video
- **Cooler operation** - Less heat generated

### Quality Comparison

| Method | Speed | Quality | Power Usage |
|--------|-------|---------|-------------|
| Software (libx264) | Slow | Excellent | High |
| NVENC | Fast | Very Good | Low |
| QSV | Fast | Good | Very Low |
| VideoToolbox | Fast | Very Good | Low |
| VAAPI | Fast | Good | Low |
| AMF | Fast | Good | Low |

---

## Supported Hardware

### Quick Compatibility Check

```bash
# Check available encoders in FFmpeg
ffmpeg -encoders 2>/dev/null | grep -E "h264|hevc"
```

Look for these encoder names:

| Hardware | H.264 Encoder | HEVC Encoder |
|----------|--------------|--------------|
| macOS | `h264_videotoolbox` | `hevc_videotoolbox` |
| NVIDIA | `h264_nvenc` | `hevc_nvenc` |
| Intel | `h264_qsv` | `hevc_qsv` |
| AMD | `h264_amf` | `hevc_amf` |
| Linux/VAAPI | `h264_vaapi` | `hevc_vaapi` |

---

## macOS VideoToolbox

VideoToolbox is Apple's hardware acceleration framework, available on all modern Macs.

### Requirements

- macOS 10.13 or later
- Any Mac with Intel HD Graphics 4000+ or Apple Silicon

### Verification

```bash
# Check for VideoToolbox support
ffmpeg -encoders | grep videotoolbox
```

Expected output:
```
V....D h264_videotoolbox    VideoToolbox H.264 Encoder (codec h264)
V....D hevc_videotoolbox    VideoToolbox HEVC Encoder (codec hevc)
```

### Configuration

In EXStreamTV, VideoToolbox is automatically detected and used. To force it:

```yaml
# config.yaml
transcoding:
  hardware_acceleration: videotoolbox
  encoder: h264_videotoolbox
  decoder: h264  # or h264_videotoolbox for full HW pipeline
```

### Recommended Settings

```yaml
transcoding:
  hardware_acceleration: videotoolbox
  profile: high
  level: 4.1
  bitrate: 8M
  options:
    realtime: true
    allow_sw: false  # Fail if HW not available
```

### Apple Silicon Notes

On M1/M2/M3 Macs:
- Both encoding and decoding are hardware accelerated
- H.264 and HEVC are fully supported
- HDR tonemapping works in software

---

## NVIDIA NVENC

NVIDIA's dedicated hardware encoder, available on GeForce GTX 600+ and all RTX cards.

### Requirements

- NVIDIA GPU (GTX 600 series or newer)
- NVIDIA Driver 418.81+ (Windows/Linux)
- CUDA Toolkit (optional, for CUDA filters)

### Verification

```bash
# Check NVIDIA driver
nvidia-smi

# Check for NVENC support
ffmpeg -encoders | grep nvenc
```

Expected output:
```
V....D h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)
V....D hevc_nvenc           NVIDIA NVENC HEVC encoder (codec hevc)
```

### Configuration

```yaml
# config.yaml
transcoding:
  hardware_acceleration: nvenc
  encoder: h264_nvenc
  decoder: h264_cuvid  # Hardware decoding
```

### Recommended Settings

```yaml
transcoding:
  hardware_acceleration: nvenc
  encoder: h264_nvenc
  preset: p4  # p1 (fastest) to p7 (best quality)
  tune: ll    # Low latency for streaming
  rc: vbr    # Rate control: cbr, vbr, cq
  bitrate: 8M
  maxrate: 12M
  bufsize: 16M
  options:
    b_adapt: 0       # Disable B-frame adaptation for low latency
    spatial_aq: 1    # Enable spatial adaptive quantization
    temporal_aq: 1   # Enable temporal adaptive quantization
    rc-lookahead: 20
```

### Docker with NVIDIA GPU

```yaml
# docker-compose.yml
services:
  exstreamtv:
    image: exstreamtv/exstreamtv:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu, video]
```

---

## Intel Quick Sync (QSV)

Intel's hardware encoder, available on CPUs with integrated graphics.

### Requirements

- Intel CPU with integrated graphics (6th gen Skylake or newer recommended)
- Intel Media Driver (Linux) or Intel Graphics Driver (Windows)

### Linux Setup

```bash
# Ubuntu/Debian
sudo apt install intel-media-va-driver-non-free vainfo

# Verify installation
vainfo
```

### Verification

```bash
# Check for QSV support
ffmpeg -encoders | grep qsv
```

Expected output:
```
V....D h264_qsv             H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
V....D hevc_qsv             HEVC (codec hevc)
```

### Configuration

```yaml
# config.yaml
transcoding:
  hardware_acceleration: qsv
  encoder: h264_qsv
  decoder: h264_qsv
```

### Recommended Settings

```yaml
transcoding:
  hardware_acceleration: qsv
  encoder: h264_qsv
  preset: fast     # veryfast, fast, medium, slow
  global_quality: 23
  options:
    look_ahead: 1
    look_ahead_depth: 40
```

### QSV in Docker

Mount the Intel render device:

```yaml
services:
  exstreamtv:
    devices:
      - /dev/dri:/dev/dri
```

---

## AMD AMF/VCE

AMD's Video Coding Engine, available on recent AMD GPUs.

### Requirements

- AMD GPU with VCE/VCN (Radeon HD 7700+ or RX series)
- AMD drivers with AMF support
- Windows or Linux with AMDGPU driver

### Verification

```bash
# Check for AMF support
ffmpeg -encoders | grep amf
```

Expected output:
```
V....D h264_amf             AMD AMF H.264 Encoder (codec h264)
V....D hevc_amf             AMD AMF HEVC Encoder (codec hevc)
```

### Configuration

```yaml
# config.yaml
transcoding:
  hardware_acceleration: amf
  encoder: h264_amf
```

### Recommended Settings

```yaml
transcoding:
  hardware_acceleration: amf
  encoder: h264_amf
  quality: balanced  # speed, balanced, quality
  rc: vbr_latency
  bitrate: 8M
```

---

## Linux VAAPI

VA-API (Video Acceleration API) works with Intel, AMD, and some NVIDIA GPUs on Linux.

### Requirements

- Linux with Mesa/VAAPI support
- Appropriate VA-API driver for your GPU

### Installation

```bash
# Ubuntu/Debian
sudo apt install vainfo libva-dev

# For Intel
sudo apt install intel-media-va-driver-non-free

# For AMD
sudo apt install mesa-va-drivers

# Verify
vainfo
```

### Configuration

```yaml
# config.yaml
transcoding:
  hardware_acceleration: vaapi
  encoder: h264_vaapi
  vaapi_device: /dev/dri/renderD128
```

### Recommended Settings

```yaml
transcoding:
  hardware_acceleration: vaapi
  encoder: h264_vaapi
  vaapi_device: /dev/dri/renderD128
  options:
    qp: 23
```

### VAAPI in Docker

```yaml
services:
  exstreamtv:
    devices:
      - /dev/dri:/dev/dri
    environment:
      - LIBVA_DRIVER_NAME=iHD  # or radeonsi for AMD
```

---

## FFmpeg Profiles

EXStreamTV includes pre-configured profiles for common use cases.

### Built-in Profiles

| Profile | Resolution | Bitrate | Use Case |
|---------|------------|---------|----------|
| `1080p-high` | 1920x1080 | 10 Mbps | High quality local streaming |
| `1080p-medium` | 1920x1080 | 6 Mbps | Balanced quality/bandwidth |
| `720p-high` | 1280x720 | 5 Mbps | HD streaming |
| `720p-medium` | 1280x720 | 3 Mbps | Good for most devices |
| `480p` | 854x480 | 1.5 Mbps | Mobile/low bandwidth |

### Custom Profile Example

Create custom profiles in the WebUI or config:

```yaml
# config.yaml
ffmpeg_profiles:
  my_4k_profile:
    name: "4K HEVC"
    video_codec: hevc_videotoolbox  # or hevc_nvenc, hevc_qsv
    audio_codec: aac
    resolution: 3840x2160
    bitrate: 25M
    framerate: 60
    preset: slow
    options:
      profile: main10
      level: 5.1
```

### Selecting a Profile

In the channel editor:

1. Go to **Channels** → Select channel → **Edit**
2. Find **FFmpeg Profile**
3. Select from dropdown or create custom
4. Click **Save**

---

## Performance Tuning

### Concurrent Streams

Each GPU can handle multiple streams. Typical limits:

| GPU | Estimated Concurrent 1080p Streams |
|-----|-----------------------------------|
| GTX 1650 | 2-3 |
| RTX 3070 | 5-8 |
| RTX 4090 | 12-15 |
| Intel UHD 630 | 2-3 |
| Apple M1 | 4-6 |
| Apple M2 Pro | 8-10 |

### Optimizing Latency

For live streaming with minimal delay:

```yaml
transcoding:
  hardware_acceleration: nvenc
  encoder: h264_nvenc
  preset: p1  # Fastest
  tune: ull   # Ultra-low latency
  options:
    zerolatency: 1
    rc: cbr
    bf: 0      # No B-frames
```

### Balancing Quality and Speed

```yaml
# Quality focused (VOD)
transcoding:
  preset: p6
  rc: vbr
  cq: 19
  options:
    2pass: 1

# Speed focused (Live)
transcoding:
  preset: p2
  rc: cbr
  options:
    zerolatency: 1
```

---

## Troubleshooting

### Hardware Acceleration Not Working

```bash
# Check FFmpeg build
ffmpeg -hwaccels

# Test encoding
ffmpeg -f lavfi -i testsrc=duration=5 -c:v h264_nvenc test.mp4
```

### "No NVENC capable devices found"

- Update NVIDIA drivers
- Ensure GPU supports NVENC (check NVIDIA's matrix)
- On Docker, verify GPU passthrough: `docker run --gpus all nvidia/cuda:11.0-base nvidia-smi`

### QSV Initialization Failed

```bash
# Check Intel driver
vainfo

# If missing, install driver
sudo apt install intel-media-va-driver-non-free
```

### VideoToolbox Errors on macOS

- Ensure FFmpeg was built with VideoToolbox support
- Try reinstalling: `brew reinstall ffmpeg`

### VAAPI Permission Denied

```bash
# Add user to video/render group
sudo usermod -aG video $USER
sudo usermod -aG render $USER

# Log out and back in
```

### Encoder Performance Issues

Monitor GPU usage:

```bash
# NVIDIA
nvidia-smi -l 1

# Intel
intel_gpu_top

# General (with iotop-like display)
watch -n 1 cat /sys/class/drm/card0/device/gpu_busy_percent
```

---

## Best Practices

1. **Match source resolution** - Don't upscale, only downscale
2. **Use appropriate bitrates** - Higher isn't always better
3. **Enable hardware decoding** - Full GPU pipeline when possible
4. **Monitor temperatures** - GPUs can throttle when hot
5. **Keep drivers updated** - New drivers often improve performance

---

## See Also

- [FFmpeg Hardware Acceleration Wiki](https://trac.ffmpeg.org/wiki/HWAccelIntro)
- [NVIDIA Video Codec SDK](https://developer.nvidia.com/nvidia-video-codec-sdk)
- [Intel Media Driver](https://github.com/intel/media-driver)
