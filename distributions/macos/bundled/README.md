# Bundled Dependencies

This directory contains bundled versions of Python and FFmpeg for the EXStreamTV macOS installer.

## Structure

```
bundled/
├── python/          # Python 3.11 distribution
│   ├── bin/
│   │   └── python3
│   ├── lib/
│   └── ...
├── ffmpeg/          # FFmpeg binaries
│   ├── bin/
│   │   ├── ffmpeg
│   │   └── ffprobe
│   └── lib/
└── README.md
```

## Building Bundled Dependencies

### Python

Download and extract Python from python.org:

```bash
# Download Python 3.11 framework
curl -O https://www.python.org/ftp/python/3.11.7/python-3.11.7-macos11.pkg

# Or build from source for both architectures
./scripts/build_python.sh
```

### FFmpeg

Download pre-built FFmpeg with VideoToolbox support:

```bash
# From evermeet.cx (static builds with macOS hardware acceleration)
curl -O https://evermeet.cx/ffmpeg/ffmpeg-6.1.1.zip
unzip ffmpeg-6.1.1.zip -d ffmpeg/bin/

curl -O https://evermeet.cx/ffmpeg/ffprobe-6.1.1.zip
unzip ffprobe-6.1.1.zip -d ffmpeg/bin/

# Or build with Homebrew (universal binary)
brew install --build-from-source ffmpeg
```

## Universal Binaries

For distribution, create universal (fat) binaries that work on both Intel and Apple Silicon:

```bash
# Check architecture
file ffmpeg/bin/ffmpeg
# Should show: Mach-O universal binary with 2 architectures: [x86_64:Mach-O 64-bit executable x86_64] [arm64]

# If not universal, combine:
lipo -create ffmpeg_x86_64 ffmpeg_arm64 -output ffmpeg
```

## Size Optimization

To reduce package size:

1. **Python**: Strip test files and unnecessary stdlib modules
2. **FFmpeg**: Use minimal build with only required codecs

```bash
# Strip Python
find python/lib -name "test" -type d -exec rm -rf {} +
find python/lib -name "__pycache__" -type d -exec rm -rf {} +

# Reduce FFmpeg (build with minimal options)
./configure --disable-doc --disable-debug --enable-small \
  --enable-videotoolbox --enable-audiotoolbox \
  --enable-libx264 --enable-libx265 --enable-libvpx
```

## Notes

- Bundled Python includes pip and essential packages
- FFmpeg is built with VideoToolbox for hardware acceleration on macOS
- Total bundled size: ~150MB (Python ~100MB, FFmpeg ~50MB)
