# macOS App User Guide

Complete guide to using the EXStreamTV macOS menu bar application.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [First Launch](#first-launch)
- [Menu Bar Interface](#menu-bar-interface)
- [Server Management](#server-management)
- [AI Configuration](#ai-configuration)
- [Native Video Player](#native-video-player)
- [Channel Switcher](#channel-switcher)
- [Notifications](#notifications)
- [Settings](#settings)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Troubleshooting](#troubleshooting)

---

## Overview

The EXStreamTV macOS app provides:

- **Menu Bar Control**: Quick access to server controls from the menu bar
- **Native Video Player**: Watch channels directly in the app with PiP support
- **Channel Switcher**: Quick channel navigation with keyboard shortcuts
- **AI Integration**: Configure and manage AI providers
- **System Notifications**: Alerts for server events and AI suggestions
- **Launch at Login**: Start automatically with your Mac

**Requirements:**
- macOS 13.0 (Ventura) or later
- Python 3.10+ with EXStreamTV installed
- FFmpeg for streaming

---

## Installation

### From DMG

1. Download `EXStreamTV-Installer.dmg`
2. Open the DMG file
3. Drag EXStreamTV to Applications folder
4. Launch from Applications or Spotlight

### From Source

```bash
cd EXStreamTVApp
swift build -c release
cp -r .build/release/EXStreamTVApp.app /Applications/
```

---

## First Launch

When you first launch EXStreamTV, the **Onboarding Wizard** guides you through setup:

### Step 1: Welcome

- Checks for Python and FFmpeg dependencies
- Shows installation status
- Offers to run the install script if dependencies are missing

### Step 2: AI Assistant Setup

Choose your AI configuration:

| Option | Description |
|--------|-------------|
| **Cloud AI** | Uses Groq's free cloud service. Recommended for most users. |
| **Local AI** | Runs on your Mac with Ollama. Works offline. |
| **Hybrid** | Cloud primary with local fallback. Best reliability. |
| **Skip** | Configure AI later in Settings. |

### Step 3: Server Setup

- Set the server port (default: 8411)
- Choose data directory location
- Start the server

### Step 4: Media Sources

Connect your media libraries (optional):
- Plex Media Server
- Jellyfin
- Emby
- Local folders

### Step 5: First Channel

Create your first channel:
- **AI-Assisted**: Let AI help create a channel
- **Manual**: Configure everything yourself
- **Import M3U**: Import existing playlist

### Step 6: Complete

- Summary of your configuration
- Link to open the web dashboard

---

## Menu Bar Interface

The EXStreamTV icon appears in your macOS menu bar.

### Icon States

| Icon | Meaning |
|------|---------|
| TV icon (gray) | Server stopped |
| TV icon (green) | Server running |
| TV icon with number | Active stream count |

### Popover Menu

Click the menu bar icon to see:

- **Server Status**: Running/Stopped with uptime
- **Start/Stop Button**: Control the server
- **Quick Actions**: Open Web UI, Dashboard, Channels
- **Active Streams**: List of current streams
- **Settings Gear**: Open preferences

---

## Server Management

### Starting the Server

1. Click the menu bar icon
2. Click **Start Server**
3. Wait for "Server running" status

Or use keyboard shortcut: **Cmd+Shift+S**

### Stopping the Server

1. Click the menu bar icon
2. Click **Stop Server**

### Auto-Start

Enable in Settings to start the server automatically when the app launches.

### Restart After Sleep

The app can automatically restart the server when your Mac wakes from sleep. Enable in **Settings** > **General**.

---

## AI Configuration

Configure AI providers in **Settings** > **AI** tab.

### Provider Selection

1. **Provider Type**: Choose Cloud, Local, or Hybrid
2. **Cloud Service**: Select Groq, SambaNova, or OpenRouter
3. **API Key**: Enter your provider's API key

### Adding an API Key

1. Click **Get Free API Key** to open the provider's website
2. Sign up and create an API key
3. Paste the key in the API Key field
4. Click **Validate & Save**

### Local AI Setup

1. Select **Local AI** as provider type
2. Ensure Ollama is running (green status)
3. Select a model from the dropdown
4. Models are auto-recommended based on your RAM

### Validation

The app shows:
- Green checkmark: AI configured and working
- Orange warning: Configuration incomplete
- **Test** button: Send a test request

---

## Native Video Player

Watch channels directly in the app with the native video player.

### Opening the Player

1. Go to Channels in the web dashboard
2. Click **Play** on a channel
3. Select "Open in App" (or it opens automatically)

### Player Controls

| Control | Action |
|---------|--------|
| **Play/Pause** | Click center button or press Space |
| **Mute** | Click speaker icon or press M |
| **Volume** | Drag slider or use scroll |
| **Fullscreen** | Click expand icon or press F |
| **Picture in Picture** | Click PiP icon |

### Picture in Picture (PiP)

1. Click the PiP icon in the player controls
2. The video floats above other windows
3. Click again to exit PiP

### Quality Indicator

The player shows current stream quality (1080p, 720p, etc.) in the bottom right.

---

## Channel Switcher

Quickly switch between channels using the overlay.

### Opening the Switcher

- Press **Cmd+G** to open the channel switcher
- Or click **Channels** in the menu bar popover

### Navigation

| Key | Action |
|-----|--------|
| **Up/Down Arrow** | Navigate channels |
| **Enter** | Select channel |
| **0-9** | Type channel number to jump |
| **Escape** | Close switcher |

### Quick Channel Change

- **Cmd+Up Arrow**: Previous channel
- **Cmd+Down Arrow**: Next channel

### Direct Channel Access

Type a channel number (e.g., "12") to jump directly. The switcher waits 1.5 seconds for additional digits, then switches.

---

## Notifications

EXStreamTV sends macOS notifications for important events.

### Notification Types

| Event | Description |
|-------|-------------|
| **Server Started** | Server is running and ready |
| **Server Stopped** | Server has stopped |
| **Server Error** | An error occurred |
| **Stream Started** | A channel started playing |
| **AI Fix Found** | AI troubleshooting found solutions |

### Configuring Notifications

Go to **Settings** > **Notifications**:

- **Enable notifications**: Master toggle
- **Server started/stopped**: Startup notifications
- **Server errors**: Error alerts
- **Stream started**: Playback notifications

### Dock Badge

When streams are active, the dock icon shows a badge with the count.

To disable: Go to **Settings** > **Notifications** and disable dock badge.

---

## Settings

Access settings via:
- Click gear icon in menu bar popover
- Press **Cmd+,**
- Menu: EXStreamTV > Settings

### General Tab

| Setting | Description |
|---------|-------------|
| Start server on launch | Auto-start when app opens |
| Restart after sleep | Restart server after Mac wakes |
| Launch at login | Start app when you log in |

### Server Tab

| Setting | Description |
|---------|-------------|
| Port | Server port (default: 8411) |
| Python Path | Path to Python executable |
| Server Path | Path to EXStreamTV directory |

### AI Tab

Configure AI providers. See [AI Configuration](#ai-configuration).

### Notifications Tab

Configure notification preferences. See [Notifications](#notifications).

### Advanced Tab

| Setting | Description |
|---------|-------------|
| Debug mode | Enable verbose logging |
| Log level | Set logging verbosity |
| Health check interval | Server monitoring frequency |
| Reset settings | Restore defaults |

---

## Keyboard Shortcuts

### Global Shortcuts

| Shortcut | Action |
|----------|--------|
| **Cmd+G** | Open channel switcher |
| **Cmd+Up** | Channel up |
| **Cmd+Down** | Channel down |
| **Cmd+,** | Open Settings |
| **Cmd+Q** | Quit app |

### Player Shortcuts

| Shortcut | Action |
|----------|--------|
| **Space** | Play/Pause |
| **M** | Mute/Unmute |
| **F** | Toggle fullscreen |
| **Esc** | Exit fullscreen/Close |

### Channel Switcher

| Shortcut | Action |
|----------|--------|
| **Up/Down** | Navigate |
| **Enter** | Select |
| **0-9** | Jump to channel |
| **Esc** | Close |

---

## Troubleshooting

### App Won't Launch

1. Check macOS version (requires 13.0+)
2. Right-click app > Open (bypasses Gatekeeper first time)
3. Check Console.app for crash logs

### Server Won't Start

1. Check Python path in Settings > Server
2. Verify EXStreamTV is installed: `python -c "import exstreamtv"`
3. Check if port is in use: `lsof -i :8411`
4. View logs in Settings > Advanced > Open Logs Folder

### Dependencies Missing

Run the install script:

1. Click "Run Install Script" in Welcome step
2. Or run manually: `./scripts/install_macos.sh`

### AI Not Working

1. Check Settings > AI shows green status
2. Verify API key is entered correctly
3. For local AI, ensure Ollama is running
4. Click "Test" to verify connection

### No Notifications

1. Check Settings > Notifications are enabled
2. Verify macOS notification permissions:
   - System Settings > Notifications > EXStreamTV

### Video Player Issues

1. Ensure FFmpeg is installed
2. Check the channel has valid content
3. Try the web player as alternative

### Re-run Onboarding

To restart the setup wizard:

1. Go to Settings > Advanced
2. Click "Reset All Settings"
3. Restart the app

---

## Next Steps

- [AI Setup Guide](AI_SETUP.md) - Detailed AI configuration
- [Quick Start Guide](QUICK_START.md) - Create your first channel
- [Installation Guide](INSTALLATION.md) - Platform-specific setup
