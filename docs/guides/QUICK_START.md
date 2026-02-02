# Quick Start Guide

Get your first EXStreamTV channel running in under 10 minutes.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Starting the Server](#starting-the-server)
- [Accessing the Web UI](#accessing-the-web-ui)
- [Creating Your First Channel](#creating-your-first-channel)
- [Adding Content](#adding-content)
- [Watching Your Channel](#watching-your-channel)
- [Next Steps](#next-steps)

---

## Prerequisites

Before starting, ensure you have:

1. **EXStreamTV installed** - See [Installation Guide](INSTALLATION.md)
2. **FFmpeg available** - Required for transcoding
3. **Media content** - Videos to add to your channel

---

## Starting the Server

### Option 1: Command Line

```bash
# Navigate to EXStreamTV directory
cd /path/to/EXStreamTV

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\Activate.ps1  # Windows

# Start the server
python -m exstreamtv
```

### Option 2: Start Script

```bash
./start.sh
```

### Option 3: macOS Menu Bar App (Recommended)

Launch the EXStreamTV app from your Applications folder.

On first launch, the **Onboarding Wizard** guides you through:
1. Dependency verification
2. AI provider setup
3. Server configuration
4. Media source connections

See [Onboarding Guide](ONBOARDING.md) for the complete walkthrough.

After onboarding, click "Start Server" from the menu bar icon.

You should see output like:

```
INFO:     Starting EXStreamTV v2.6.0
INFO:     Configuration loaded, server port: 8411
INFO:     Database initialized
INFO:     Uvicorn running on http://0.0.0.0:8411
```

---

## Accessing the Web UI

Open your browser and go to:

```
http://localhost:8411
```

You'll see the EXStreamTV Dashboard with:

- **Quick Stats** - Channels, playlists, media counts
- **System Resources** - CPU, memory, disk usage
- **Active Streams** - Currently playing channels
- **Quick Actions** - Shortcuts to common tasks

---

## Creating Your First Channel

### Option A: AI-Assisted Creation (Recommended)

If you configured AI during setup:

1. Go to **Channels** in the sidebar
2. Click **+ New Channel**
3. Click **AI-Assisted** tab
4. Describe your channel:
   - "Classic 80s action movies channel"
   - "Kids cartoons with morning schedule"
   - "Documentary channel about nature"
5. AI suggests content and schedule
6. Review and click **Create**

This creates a complete channel with:
- Curated content from your libraries
- Appropriate scheduling
- Channel branding suggestions

### Option B: Manual Creation

#### Step 1: Navigate to Channels

Click **Channels** in the sidebar or go to:

```
http://localhost:8411/channels
```

#### Step 2: Create New Channel

1. Click the **+ New Channel** button
2. Fill in the details:
   - **Channel Number**: `1`
   - **Channel Name**: `My First Channel`
   - **Group**: `Entertainment` (optional)
3. Click **Create**

#### Step 3: Channel Settings (Optional)

In the channel editor, you can configure:

- **Logo** - Upload a channel logo
- **FFmpeg Profile** - Select quality preset (Default 1080p, HD 720p, etc.)
- **Guide Color** - Color for EPG display

---

## Adding Content

### Option A: Create a Playlist with URLs

1. Go to **Playlists** in the sidebar
2. Click **+ New Playlist**
3. Name it `First Playlist`
4. Click **Add Item** and enter:
   - **Title**: `Sample Video`
   - **URL**: `http://example.com/video.mp4` or a YouTube URL
5. Repeat for more videos
6. Click **Save**

### Option B: Add Local Media

1. Go to **Libraries** in the sidebar
2. Click **+ Add Library**
3. Choose **Local Library**
4. Enter the path to your media folder: `/path/to/videos`
5. Click **Scan** to discover media
6. Create a playlist from the scanned media

### Option C: Import from Plex/Jellyfin

1. Go to **Libraries** → **+ Add Library**
2. Choose **Plex** or **Jellyfin**
3. Enter your server details:
   - **Server URL**: `http://localhost:32400` (Plex)
   - **Token/API Key**: Your authentication token
4. Select libraries to import
5. Click **Sync**

---

## Assigning Content to Channel

### Using a Playlist

1. Go to **Channels** and select your channel
2. Click **Edit Channel**
3. In the **Playlist Panel**, click **+ Add Content**
4. Select your playlist
5. Click **Save**

### Using the Schedule Builder

For more control over when content plays:

1. Go to **Schedules** in the sidebar
2. Click **+ New Schedule**
3. Add time blocks:
   - Morning: 6 AM - 12 PM
   - Afternoon: 12 PM - 6 PM
   - Evening: 6 PM - 12 AM
4. Assign playlists to each block
5. Apply the schedule to your channel

---

## Watching Your Channel

### Option 1: Built-in Player

1. Go to **Channels**
2. Click the **Play** button on your channel
3. The video will play in the browser

### Option 2: External Player

Copy the stream URL:

```
http://localhost:8411/channels/1/stream.m3u8
```

Open in VLC, mpv, or any HLS-compatible player:

```bash
# VLC
vlc http://localhost:8411/channels/1/stream.m3u8

# mpv
mpv http://localhost:8411/channels/1/stream.m3u8
```

### Option 3: HDHomeRun/IPTV Client

EXStreamTV emulates an HDHomeRun device. In Plex, Emby, or Jellyfin:

1. Go to Live TV settings
2. Click "Add DVR" or "Add Tuner"
3. It should auto-discover EXStreamTV
4. Or manually enter: `http://localhost:8411`

### Option 4: M3U Playlist

Download the M3U playlist:

```
http://localhost:8411/iptv/channels.m3u
```

Import into any IPTV app (IPTV Smarters, TiviMate, etc.)

---

## Quick Reference

### Common URLs

| Resource | URL |
|----------|-----|
| Dashboard | `http://localhost:8411/dashboard` |
| Channels | `http://localhost:8411/channels` |
| Guide | `http://localhost:8411/guide` |
| M3U Playlist | `http://localhost:8411/iptv/channels.m3u` |
| EPG (XML) | `http://localhost:8411/iptv/xmltv.xml` |
| API Docs | `http://localhost:8411/api/docs` |

### Keyboard Shortcuts

#### Web Player
| Shortcut | Action |
|----------|--------|
| `Space` | Play/Pause (in player) |
| `F` | Fullscreen |
| `M` | Mute |
| `←` / `→` | Seek 10 seconds |

#### macOS App Channel Switcher
| Shortcut | Action |
|----------|--------|
| `Cmd+G` | Open channel switcher |
| `Cmd+Up` | Previous channel |
| `Cmd+Down` | Next channel |
| `0-9` | Jump to channel number |
| `Esc` | Close switcher |

---

## Next Steps

Now that you have a working channel:

1. **[Configure AI](AI_SETUP.md)** - Set up AI-assisted channel creation
2. **[Add more content](LOCAL_MEDIA.md)** - Connect local libraries or streaming sources
3. **[Enable hardware transcoding](HW_TRANSCODING.md)** - Reduce CPU usage
4. **[Create a schedule](../api/README.md)** - Program your channels like real TV
5. **[Use the macOS app](MACOS_APP_GUIDE.md)** - Native player and keyboard shortcuts
6. **[Customize your setup](../architecture/SYSTEM_DESIGN.md)** - Advanced configuration

---

## Troubleshooting

### Channel Not Playing

- Check that FFmpeg is installed: `ffmpeg -version`
- Verify the source URL is accessible
- Check the logs: **Settings** → **Logs**

### Poor Video Quality

- Adjust the FFmpeg profile in channel settings
- Enable hardware transcoding for better performance

### Buffering Issues

- Reduce the output bitrate in FFmpeg profile
- Check network bandwidth
- Try a lower resolution preset

### Need Help?

- Check the [FAQ](FAQ.md)
- Browse [GitHub Issues](https://github.com/roto31/EXStreamTV/issues)
- Join our community on [Discord](https://discord.gg/exstreamtv)
