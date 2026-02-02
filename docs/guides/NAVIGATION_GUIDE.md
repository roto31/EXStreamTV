# EXStreamTV Navigation Guide

A complete reference guide for navigating the EXStreamTV platform. This guide covers every menu item and feature available in the web interface.

![Dashboard Overview](/docs/screenshots/nav-dashboard-overview.png)
*The EXStreamTV dashboard with the reorganized sidebar navigation*

## Table of Contents

1. [Getting Started](#getting-started)
2. [Interface Overview](#interface-overview)
3. [Top-Level Navigation](#top-level-navigation)
4. [Channels Group](#channels-group)
5. [Content Group](#content-group)
6. [Scheduling Group](#scheduling-group)
7. [Integrations Group](#integrations-group)
8. [System Group](#system-group)
9. [Help Group](#help-group)
10. [Diagnostics Group](#diagnostics-group)
11. [Developer Section](#developer-section)
12. [Quick Access Menu](#quick-access-menu)

---

## Getting Started

When you first access EXStreamTV, you'll be greeted by the **Dashboard** - your central hub for monitoring channels, streams, and system status.

### First Login Checklist

1. **Connect a Media Source** - Go to Integrations > Media Sources to connect Plex, Jellyfin, or local folders
2. **Create Your First Channel** - Use Channels > Manage Channels or try AI Create Channel for guided setup
3. **Configure Streaming** - Set up FFmpeg and HDHomeRun settings in the System section
4. **Test Your Setup** - Use Diagnostics > Test Stream to verify everything works

---

## Interface Overview

The EXStreamTV interface consists of three main areas:

### 1. Header Bar

Located at the top of every page:

- **Menu Button** (hamburger icon) - Toggle the sidebar on mobile devices
- **Quick Launch** - Fast access to common actions and channels
- **Theme Toggle** - Switch between light and dark modes

### 2. Sidebar Navigation

The left sidebar contains all navigation organized into logical groups. Each group has a header title and expandable content.

![Sidebar Navigation](/docs/screenshots/nav-sidebar-full.png)
*The complete sidebar showing all navigation groups*

### 3. Main Content Area

The central area where page content is displayed. This changes based on your current location in the app.

---

## Top-Level Navigation

These items appear at the very top of the sidebar and provide quick access to the most commonly used features.

### Dashboard

**Icon:** 📊 | **Path:** `/`

Your home base in EXStreamTV. The dashboard displays:

- **Quick Stats** - Channel count, media items, active streams, schedule items
- **Active Streams** - Currently playing channels with viewer counts
- **Quick Actions** - Fast links to common tasks
- **Library Breakdown** - Overview of your media sources
- **Activity Feed** - Recent system events and changes
- **System Monitor** - CPU, memory, and disk usage

### Player

**Icon:** ▶️ | **Path:** `/player`

The built-in video player for previewing channels:

- Live channel playback
- Channel switching via dropdown or quick launch
- Playback controls (play, pause, volume)
- Full-screen mode support

---

## Channels Group

Everything related to creating and managing your TV channels.

![Channels Page](/docs/screenshots/nav-channels-list.png)
*The channels management page with Add Channel and AI Create buttons*

### Manage Channels

**Icon:** 📺 | **Path:** `/channels`

The main channel management interface:

- **View all channels** - See channel number, name, logo, group, and status
- **Create channels** - Click "Add Channel" for manual creation
- **Edit channels** - Modify name, number, logo, group assignment
- **Enable/Disable** - Toggle channels on or off
- **Delete channels** - Remove channels you no longer need
- **Preview** - Quick preview of channel playback

**Toolbar Options:**
- **Add Channel** - Create a new channel manually
- **AI Create** - Use AI-powered guided channel creation
- **Show Disabled** - Toggle visibility of disabled channels

### AI Create Channel

**Icon:** 🤖 | **Path:** `/api/ai/channel`

The AI-powered channel creation wizard. Chat with "Max Sterling," a virtual TV programming executive who helps you:

![AI Channel Creator](/docs/screenshots/channel-ai-welcome.png)
*The AI Channel Creator interface with Max Sterling*

- Define your channel concept through natural conversation
- Set up scheduling (primetime, daytime, special blocks)
- Configure commercial breaks and filler content
- Choose content from your media libraries
- Generate complex schedules automatically

Best for: Complex channels with scheduling, themed programming, or when you want guidance on best practices.

### Import Channels

**Icon:** ⬆️ | **Path:** `/import`

Import channels from other platforms:

- **ErsatzTV** - Migrate existing ErsatzTV configurations
- **Other StreamTV instances** - Import from backup files
- **Configuration files** - Load JSON/YAML channel definitions

### Import M3U

**Icon:** 📋 | **Path:** `/import/m3u`

Import channels from M3U playlists:

- Paste M3U playlist URLs or content
- Map imported channels to local media
- Configure channel properties during import
- Support for IPTV playlist formats

---

## Content Group

Manage your media content, playlists, and collections.

### Media Items

**Icon:** 📹 | **Path:** `/media`

Browse and manage all media in your connected libraries:

- **Filter by type** - Movies, TV Shows, Episodes, Music Videos
- **Search** - Find specific titles across all sources
- **View details** - Duration, resolution, codec information
- **Manual refresh** - Update metadata for specific items

### Playlists

**Icon:** 📋 | **Path:** `/playlists`

Create and manage playlists of media:

- **Create playlists** - Manually curated content lists
- **Reorder items** - Drag and drop to arrange playback order
- **Assign to channels** - Use playlists as channel content sources
- **Smart playlists** - Auto-updating based on criteria

### Collections

**Icon:** 🗂️ | **Path:** `/collections`

Organize media into logical collections:

- **Smart Collections** - Auto-populate based on filters (genre, year, etc.)
- **Manual Collections** - Hand-picked content groupings
- **Use in scheduling** - Assign collections to schedule blocks

### Libraries

**Icon:** 📚 | **Path:** `/libraries`

Manage connections to your media libraries:

- **View connected libraries** - See all sources and their status
- **Refresh libraries** - Trigger a rescan of media
- **Library statistics** - Item counts, last scan time
- **Configure mappings** - Map remote paths to local paths

---

## Scheduling Group

Control when and how content plays on your channels.

### Playouts

**Icon:** ⏯️ | **Path:** `/playouts`

Active playback configurations connecting channels to schedules:

- **View active playouts** - See what's currently playing
- **Create playouts** - Link a channel to a schedule
- **Playout modes** - Continuous, scheduled, or looping
- **Anchor points** - Control episode progression

### Schedules

**Icon:** ⏰ | **Path:** `/schedules`

Time-based programming schedules:

- **Create schedules** - Define when content plays
- **Schedule items** - Add content to specific time slots
- **Recurring patterns** - Set up daily, weekly schedules
- **Preview timeline** - Visual schedule representation

### Blocks

**Icon:** 📊 | **Path:** `/blocks`

Programming blocks for schedule templates:

- **Create blocks** - Define themed content groupings (e.g., "Saturday Morning Cartoons")
- **Set duration** - Define block length
- **Content rules** - What types of content to include
- **Shuffle options** - Randomize within blocks

### Templates

**Icon:** 📄 | **Path:** `/templates`

Reusable schedule templates:

- **Create templates** - Design standard day layouts
- **Apply to schedules** - Use templates as starting points
- **Clone and modify** - Create variations easily

### Filler Presets

**Icon:** 🎬 | **Path:** `/filler-presets`

Configure commercial breaks and filler content:

- **Create presets** - Define filler content rules
- **Duration settings** - How long between content
- **Source selection** - Which content to use as filler
- **Period-appropriate options** - Match content era

### Deco

**Icon:** ✨ | **Path:** `/deco`

Channel branding and overlays:

- **Watermarks** - Add channel logos
- **Bumpers** - Intro/outro content
- **Overlays** - On-screen graphics
- **Positioning** - Control placement of elements

---

## Integrations Group

Connect external services and media sources.

### Plex API

**Icon:** 🔗 | **Path:** `/settings/plex`

Configure Plex Media Server connection:

- **Server URL** - Your Plex server address
- **Authentication** - Plex token configuration
- **Library selection** - Choose which libraries to use
- **Path mapping** - Map Plex paths to local paths

### Media Sources

**Icon:** 🖼️ | **Path:** `/settings/media-sources`

Manage all media source connections:

- **Add sources** - Connect Plex, Jellyfin, Emby, or local folders
- **Test connections** - Verify sources are accessible
- **Configure priorities** - Set source preferences
- **Manage credentials** - Update authentication

### Archive.org

**Icon:** 📦 | **Path:** `/api/auth/archive-org`

Connect to Internet Archive:

- **Authentication** - Log in with Archive.org account
- **Access public domain content** - Classic TV, movies, commercials
- **Prelinger Collection** - Vintage commercials and films

### YouTube

**Icon:** 📺 | **Path:** `/api/auth/youtube`

Connect YouTube for additional content:

- **OAuth authentication** - Secure login
- **Playlist access** - Use YouTube playlists in channels
- **Search integration** - Find content by query

---

## System Group

Core system configuration and settings.

### FFmpeg

**Icon:** ⚙️ | **Path:** `/settings/ffmpeg`

Video transcoding settings:

- **FFmpeg path** - Location of FFmpeg binary
- **Hardware acceleration** - Enable GPU encoding (VideoToolbox, NVENC, etc.)
- **Default profiles** - Output quality presets
- **Advanced options** - Custom encoding parameters

### HDHomeRun

**Icon:** 📡 | **Path:** `/settings/hdhr`

Virtual HDHomeRun tuner configuration:

- **Enable/disable** - Toggle virtual tuner
- **Tuner count** - Number of simultaneous streams
- **Device ID** - Virtual device identifier
- **Network settings** - Broadcast address configuration

### Playout Settings

**Icon:** 🎛️ | **Path:** `/settings/playout`

Global playback settings:

- **Buffer settings** - Stream buffering configuration
- **Error handling** - What to do on playback errors
- **Transition options** - Content transition behavior
- **Default behaviors** - System-wide playout defaults

### Quick Launch

**Icon:** 📱 | **Path:** `/settings/quick-launch`

Customize the Quick Launch menu:

- **Enable/disable items** - Choose what appears
- **Reorder items** - Set your preferred order
- **Channel shortcuts** - Add favorite channels
- **Reset to defaults** - Restore original configuration

---

## Help Group

Documentation and system health.

### Documentation

**Icon:** 📚 | **Dropdown menu**

Access to all guides and documentation:

- **Quick Start** - Get up and running fast
- **Beginner Guide** - Comprehensive introduction
- **Navigation Guide** - This document
- **Channel Creation** - How to create channels
- **Installation Guide** - Setup instructions
- **Troubleshooting** - Common issues and solutions

### Health Check

**Icon:** 🏥 | **Path:** `/health-check`

System diagnostics and status:

- **Service status** - Check all components
- **Configuration validation** - Verify settings
- **Resource usage** - Memory, CPU, disk
- **Connectivity tests** - Verify external connections

---

## Diagnostics Group

Troubleshooting and testing tools.

### Streaming Logs

**Icon:** 💻 | **Path:** `/logs`

Real-time streaming activity logs:

- **Live log stream** - See events as they happen
- **Filter by level** - Error, warning, info, debug
- **Search logs** - Find specific events
- **Export logs** - Download for analysis

### Plex Server Logs

**Icon:** 📺 | **Path:** `/plex-logs`

View Plex Media Server logs:

- **Plex activity** - Transcoding, playback events
- **Error tracking** - Identify Plex issues
- **Filter and search** - Find relevant entries

### AI Troubleshooting

**Icon:** 🧠 | **Path:** `/ollama`

AI-powered error analysis:

- **Automatic analysis** - AI interprets error messages
- **Fix suggestions** - Recommended solutions
- **Learn from patterns** - Improves over time
- **Requires Ollama** - Local AI model installation

### Test Stream

**Icon:** 📹 | **Path:** `/test-stream`

Test channel playback:

- **Select channel** - Choose what to test
- **View output** - See actual stream
- **Debug information** - Detailed playback data
- **Error reporting** - Identify issues

---

## Developer Section

Advanced tools for developers (hidden by default).

### Enabling Developer Tools

Developer tools are hidden by default. To enable:

1. Open browser console (F12 or Cmd+Option+I)
2. Run: `toggleDevTools(true)`
3. The Developer section will appear in the sidebar

Or enable permanently:
```javascript
localStorage.setItem('showDevTools', 'true')
```

### API Documentation

**Icon:** 🔌 | **Path:** `/docs` | **Opens in new tab**

Interactive Swagger UI for the API:

- **Explore endpoints** - See all available APIs
- **Try requests** - Test API calls directly
- **View schemas** - Request/response formats
- **Authentication info** - How to authenticate

### ReDoc

**Icon:** 📰 | **Path:** `/redoc` | **Opens in new tab**

Alternative API documentation view:

- **Clean layout** - Easy-to-read format
- **Search** - Find endpoints quickly
- **Code examples** - Sample requests

---

## Quick Access Menu

The Quick Access menu provides fast access to common features without navigating through the sidebar.

### Accessing Quick Access

Click the **Quick Launch** button in the header bar (shows "Quick Launch" with dropdown arrow).

### Default Quick Access Items

- **All Channels** - Go to channel management
- **AI Create Channel** - Start AI channel creation
- **Schedules** - View and edit schedules
- **Import** - Import channels
- **M3U Playlist** - Download M3U file (external link)
- **XMLTV EPG** - Download EPG file (external link)
- **Settings** - System settings
- **Health Check** - System diagnostics

### Customizing Quick Access

Go to System > Quick Launch to:

- Add or remove menu items
- Reorder items by priority
- Add channel shortcuts
- Configure which channels appear

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Esc` | Close modals and dialogs |
| `/` | Focus search (on supported pages) |
| `?` | Show help (on supported pages) |

---

## Getting Help

If you need assistance:

1. **Check the Documentation** - Help > Documentation
2. **Run Health Check** - Help > Health Check
3. **Use AI Troubleshooting** - Diagnostics > AI Troubleshooting
4. **View Logs** - Diagnostics > Streaming Logs

---

*Last updated: January 2026*
