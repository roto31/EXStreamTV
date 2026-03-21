# FFmpeg Apple Silicon Optimization

## Root Cause Summary

Based on `sample` profiling of FFmpeg (pid 55954) on macOS ARM64:

| Factor | Evidence | Impact |
|--------|----------|--------|
| **Software transcoding** | `enc0:0:libx264`, `x264_8_*_neon` in call stack; no VideoToolbox in decoder/encoder | **HIGH** – CPU-bound H.264 encode |
| **Thread oversubscription** | ~30+ threads (libavutil + x264 workers), many in `_pthread_cond_wait` | **HIGH** – context switching and scheduler load |
| **drawtext/libharfbuzz** | `vf#0:0` thread in `libharfbuzz`, `hb_shape_full` | **MEDIUM** – text shaping per frame |
| **Uncapped x264 threads** | `-threads` not passed → FFmpeg/x264 auto = CPU count; x264 spawns 20+ workers | **HIGH** |
| **Missing -hwaccel videotoolbox** | Decoder uses generic software path | **HIGH** when HW available |
| **Lavfi/drawtext pipeline** | `dmx0:lavfi` + filter graph (error screens or overlays) | **MEDIUM** – extra filter work |

**Primary cause:** Software H.264 encode (libx264) without hardware acceleration, combined with uncapped threading.

---

## Prioritized Fix List

1. **P1** – Enable `-hwaccel videotoolbox` for decoding on Darwin.
2. **P1** – Use `h264_videotoolbox` for encoding when VideoToolbox is available.
3. **P1** – Cap `-threads` when using libx264 (e.g. 8) to limit oversubscription.
4. **P2** – Reduce `-probesize` / `-analyzeduration` for live/streaming (e.g. 500k/1M).
5. **P2** – Use stream copy when input is already H.264/HEVC + AAC.
6. **P3** – For error screens: use `h264_videotoolbox` on Darwin instead of libx264.
7. **P3** – Set `-loglevel warning` to reduce logging overhead.

---

## Optimized FFmpeg/FFprobe Templates

### Main streaming (MPEG-TS, Apple Silicon)

```bash
# With VideoToolbox (preferred)
ffmpeg -loglevel warning \
  -hwaccel videotoolbox -hwaccel_output_format videotoolbox_vld \
  -fflags +genpts+discardcorrupt+fastseek -flags +low_delay \
  -probesize 500000 -analyzeduration 1000000 \
  -threads 8 \
  -i "INPUT_URL" \
  -c:v h264_videotoolbox -b:v 6M -profile:v high -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -f mpegts -muxrate 4M -flush_packets 1 -
```

### Software fallback (MPEG-4, or when VT unavailable)

```bash
ffmpeg -loglevel warning \
  -fflags +genpts+discardcorrupt+fastseek -flags +low_delay \
  -probesize 500000 -analyzeduration 1000000 \
  -threads 8 \
  -i "INPUT_URL" \
  -c:v libx264 -preset veryfast -crf 23 -maxrate 6M -bufsize 12M \
  -profile:v high -level 4.1 -pix_fmt yuv420p -g 50 \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -f mpegts -muxrate 4M -flush_packets 1 -
```

### Stream copy (no transcode)

```bash
ffmpeg -loglevel warning \
  -probesize 500000 -analyzeduration 1000000 \
  -i "INPUT_URL" \
  -c:v copy -bsf:v h264_mp4toannexb,dump_extra \
  -c:a copy \
  -vsync passthrough -copyts -start_at_zero \
  -f mpegts -muxrate 4M -flush_packets 1 -
```

### FFprobe (minimal probe)

```bash
ffprobe -v quiet -print_format json -show_format -show_streams \
  -probesize 500000 -analyzeduration 1000000 \
  "INPUT_URL"
```

---

## Safe Mode (minimal CPU)

```bash
ffmpeg -loglevel error -nostats \
  -hwaccel videotoolbox \
  -probesize 32768 -analyzeduration 50000 \
  -threads 4 \
  -i "INPUT_URL" \
  -c:v h264_videotoolbox -b:v 4M -realtime 1 \
  -c:a aac -b:a 128k \
  -f mpegts -muxrate 4M -
```

---

## System-Level Recommendations

| Topic | Recommendation |
|-------|----------------|
| **Rosetta** | Ensure FFmpeg is native ARM64: `file $(which ffmpeg)` → `arm64` |
| **Build** | Use Homebrew ARM64: `brew install ffmpeg` on Apple Silicon |
| **Thread scheduling** | Let macOS Grand Central Dispatch manage; avoid manual affinity |
| **CPU capping** | `cpulimit -l 400 -p PID` or `nice -n 19` for background jobs |
| **Compiler flags** | For custom build: `--enable-videotoolbox --enable-neon` |

---

## Code Locations

- **MPEG-TS streaming:** `exstreamtv/streaming/mpegts_streamer.py`
- **Error screens:** `exstreamtv/streaming/error_screens.py`
- **Profile-based builder:** `exstreamtv/transcoding/ffmpeg_builder.py`
- **Config:** `exstreamtv/config.py` (`FFmpegConfig`)

**Last Revised:** 2026-03-20
