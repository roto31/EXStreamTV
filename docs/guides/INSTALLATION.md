# Installation Guide

This guide covers installing EXStreamTV on various platforms.

## Table of Contents

- [Requirements](#requirements)
- [macOS Installation](#macos-installation)
- [Linux Installation](#linux-installation)
- [Windows Installation](#windows-installation)
- [Docker Installation](#docker-installation)
- [From Source](#from-source)
- [AI Configuration](#ai-configuration)
- [Verifying Installation](#verifying-installation)
- [Troubleshooting](#troubleshooting)

---

## Requirements

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 2 GB | 4+ GB |
| Storage | 500 MB | 2+ GB |
| Network | 10 Mbps | 100+ Mbps |

### Software Requirements

- **Python**: 3.10 or higher
- **FFmpeg**: 5.0+ with hardware acceleration support
- **pip**: Latest version recommended

### Optional Requirements

For hardware transcoding:
- **macOS**: VideoToolbox (built-in on Apple Silicon/Intel Macs)
- **NVIDIA**: CUDA 11.0+, NVENC-capable GPU
- **Intel**: QSV-capable CPU (6th gen+)
- **AMD**: AMF-capable GPU
- **Linux**: VAAPI drivers

For AI features:
- **Cloud AI**: Free API key from Groq, SambaNova, or OpenRouter
- **Local AI**: Ollama with 4GB+ RAM (8GB+ recommended)

---

## macOS Installation

### Using the Installer Script

The easiest way to install on macOS:

```bash
# Clone the repository
git clone https://github.com/roto31/EXStreamTV.git
cd EXStreamTV

# Run the installer
./scripts/install_macos.sh
```

The installer will:
1. Check/install Homebrew
2. Check/install Python 3.10+
3. Check/install FFmpeg with VideoToolbox
4. Create a virtual environment
5. Install Python dependencies
6. Initialize the database
7. Optionally install Ollama for local AI

### Manual Installation on macOS

```bash
# Install Python (if needed)
brew install python@3.11

# Install FFmpeg with hardware acceleration
brew install ffmpeg

# Clone repository
git clone https://github.com/roto31/EXStreamTV.git
cd EXStreamTV

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -m exstreamtv.database init
```

### Menu Bar App (Recommended)

Build and install the native macOS menu bar app:

```bash
cd EXStreamTVApp
swift build -c release
cp -r .build/release/EXStreamTVApp.app /Applications/
```

On first launch, the app guides you through:
1. Dependency verification
2. AI provider setup (cloud or local)
3. Server configuration
4. Media source connections
5. First channel creation

See [Onboarding Guide](ONBOARDING.md) for details.

---

## Linux Installation

### Ubuntu/Debian

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt install python3 python3-pip python3-venv -y

# Install FFmpeg with hardware support
sudo apt install ffmpeg -y

# For NVIDIA GPU support
sudo apt install nvidia-cuda-toolkit -y

# For Intel QSV support
sudo apt install intel-media-va-driver-non-free -y

# Clone repository
git clone https://github.com/roto31/EXStreamTV.git
cd EXStreamTV

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Fedora/RHEL

```bash
# Install Python
sudo dnf install python3 python3-pip -y

# Install FFmpeg (enable RPM Fusion first)
sudo dnf install https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm -y
sudo dnf install ffmpeg -y

# Clone and install
git clone https://github.com/roto31/EXStreamTV.git
cd EXStreamTV
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running as a Service

Create a systemd service:

```bash
sudo nano /etc/systemd/system/exstreamtv.service
```

Add the following content:

```ini
[Unit]
Description=EXStreamTV IPTV Streaming Server
After=network.target

[Service]
Type=simple
User=exstreamtv
WorkingDirectory=/opt/EXStreamTV
ExecStart=/opt/EXStreamTV/venv/bin/python -m exstreamtv
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable exstreamtv
sudo systemctl start exstreamtv
```

---

## Windows Installation

### Using PowerShell

```powershell
# Install Python (if needed) - using winget
winget install Python.Python.3.11

# Install FFmpeg
winget install Gyan.FFmpeg

# Clone repository
git clone https://github.com/roto31/EXStreamTV.git
cd EXStreamTV

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Running as a Windows Service

Use NSSM (Non-Sucking Service Manager):

```powershell
# Install NSSM
winget install NSSM.NSSM

# Install as service
nssm install EXStreamTV "C:\EXStreamTV\venv\Scripts\python.exe" "-m exstreamtv"
nssm set EXStreamTV AppDirectory "C:\EXStreamTV"
nssm start EXStreamTV
```

---

## Docker Installation

### Using Docker Compose (Recommended)

```bash
# Clone repository
git clone https://github.com/roto31/EXStreamTV.git
cd EXStreamTV/containers/docker

# Configure environment (optional - for AI)
cp env.example .env
# Edit .env to add your GROQ_API_KEY

# Start the container
docker-compose up -d
```

### Using Docker Directly

```bash
# Pull the image
docker pull exstreamtv/exstreamtv:latest

# Run the container
docker run -d \
  --name exstreamtv \
  -p 8411:8411 \
  -v exstreamtv_data:/app/data \
  -v /path/to/media:/media:ro \
  exstreamtv/exstreamtv:latest
```

### Docker Compose with GPU Support

For NVIDIA GPU acceleration:

```yaml
version: '3.8'
services:
  exstreamtv:
    image: exstreamtv/exstreamtv:latest
    ports:
      - "8411:8411"
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}  # For cloud AI
    volumes:
      - exstreamtv_data:/app/data
      - /path/to/media:/media:ro
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  exstreamtv_data:
```

### Docker with Local AI

To include Ollama for local AI:

```bash
docker-compose --profile ai-local up -d
```

This starts an Ollama container alongside EXStreamTV.

---

## From Source

### Development Installation

```bash
# Clone repository
git clone https://github.com/roto31/EXStreamTV.git
cd EXStreamTV

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or .\venv\Scripts\Activate.ps1 on Windows

# Install in development mode
pip install -e ".[dev]"

# Or install all dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Building from Source

```bash
# Build the package
python -m build

# Install the built package
pip install dist/exstreamtv-*.whl
```

---

## AI Configuration

EXStreamTV uses AI for channel creation, troubleshooting, and log analysis. Choose from cloud or local providers.

### Quick Setup: Cloud AI (Recommended)

1. Get a free API key from [console.groq.com](https://console.groq.com)
2. Set the environment variable:

```bash
export GROQ_API_KEY="gsk_your_key_here"
```

3. Or add to `config.yaml`:

```yaml
ai_agent:
  enabled: true
  provider_type: "cloud"
  cloud:
    provider: "groq"
    api_key: "gsk_your_key_here"
```

### Quick Setup: Local AI

1. Install Ollama:

```bash
brew install ollama
ollama serve  # Start the service
```

2. Download a model (based on your RAM):

```bash
# 4GB RAM
ollama pull phi4-mini:3.8b-q4

# 8GB RAM
ollama pull qwen2.5:7b

# 16GB+ RAM
ollama pull qwen2.5:14b
```

3. Configure in `config.yaml`:

```yaml
ai_agent:
  enabled: true
  provider_type: "local"
  local:
    model: "auto"  # Auto-selects based on RAM
```

For detailed AI configuration, see [AI Setup Guide](AI_SETUP.md).

---

## Verifying Installation

### Check Python Dependencies

```bash
# Activate virtual environment
source venv/bin/activate

# Verify imports
python -c "import exstreamtv; print(exstreamtv.__version__)"
```

### Check FFmpeg

```bash
# Verify FFmpeg installation
ffmpeg -version

# Check for hardware encoders
ffmpeg -encoders | grep -E "(h264|hevc)_(nvenc|qsv|videotoolbox|vaapi)"
```

### Start the Server

```bash
# Start EXStreamTV
python -m exstreamtv

# Or use the start script
./start.sh
```

### Access the Web Interface

Open your browser and navigate to:

```
http://localhost:8411
```

You should see the EXStreamTV dashboard.

---

## Troubleshooting

### Common Issues

#### Port Already in Use

```bash
# Check what's using port 8411
lsof -i :8411  # macOS/Linux
netstat -ano | findstr :8411  # Windows

# Use a different port
EXSTREAMTV_PORT=9000 python -m exstreamtv
```

#### Permission Denied on Media Folder

```bash
# Check permissions
ls -la /path/to/media

# Fix permissions (Linux/macOS)
sudo chown -R $USER:$USER /path/to/media
chmod -R 755 /path/to/media
```

#### FFmpeg Not Found

```bash
# Add FFmpeg to PATH
export PATH="/usr/local/bin:$PATH"

# Or specify path in config
echo "ffmpeg_path: /usr/local/bin/ffmpeg" >> config.yaml
```

#### Database Errors

```bash
# Reset the database
rm -rf data/exstreamtv.db
python -m exstreamtv.database init
```

### Getting Help

- Check the [FAQ](FAQ.md)
- Search [GitHub Issues](https://github.com/roto31/EXStreamTV/issues)
- Join our [Discord community](https://discord.gg/exstreamtv)

---

## Next Steps

After installation:
1. [Quick Start Guide](QUICK_START.md) - Get your first channel running
2. [AI Setup Guide](AI_SETUP.md) - Configure AI-assisted features
3. [macOS App Guide](MACOS_APP_GUIDE.md) - Use the menu bar app
4. [Configure Hardware Transcoding](HW_TRANSCODING.md) - Enable GPU acceleration
5. [Add Local Media](LOCAL_MEDIA.md) - Connect your media libraries
