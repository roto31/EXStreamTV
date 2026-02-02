# Local Media Setup Guide

Connect your local media libraries to EXStreamTV for organized, scheduled playback.

## Table of Contents

- [Overview](#overview)
- [Supported Library Types](#supported-library-types)
- [Local Folder Library](#local-folder-library)
- [Plex Integration](#plex-integration)
- [Jellyfin Integration](#jellyfin-integration)
- [Emby Integration](#emby-integration)
- [Media Organization](#media-organization)
- [Metadata Management](#metadata-management)
- [Scanning and Syncing](#scanning-and-syncing)
- [Troubleshooting](#troubleshooting)

---

## Overview

EXStreamTV can stream content from multiple sources:

- **Local folders** - Direct access to video files on your system
- **Plex** - Connect to your Plex Media Server
- **Jellyfin** - Connect to your Jellyfin server
- **Emby** - Connect to your Emby server

Each library is scanned and indexed, allowing you to:
- Browse and search your media
- Create playlists and schedules
- Generate rich EPG data with metadata
- Stream in various qualities

---

## Supported Library Types

| Source | Movies | TV Shows | Music Videos | Live TV |
|--------|--------|----------|--------------|---------|
| Local Folder | ✅ | ✅ | ✅ | ❌ |
| Plex | ✅ | ✅ | ✅ | ✅ |
| Jellyfin | ✅ | ✅ | ✅ | ✅ |
| Emby | ✅ | ✅ | ✅ | ✅ |

### Supported Video Formats

EXStreamTV supports any format FFmpeg can handle:

- **Containers**: MP4, MKV, AVI, MOV, WMV, FLV, WebM, M2TS
- **Video Codecs**: H.264, H.265/HEVC, VP9, AV1, MPEG-2, MPEG-4
- **Audio Codecs**: AAC, AC3, EAC3, DTS, FLAC, MP3, Opus

---

## Local Folder Library

The simplest way to add media—point EXStreamTV at a folder.

### Adding a Local Library

**Via Web UI:**

1. Go to **Libraries** in the sidebar
2. Click **+ Add Library**
3. Select **Local Folder**
4. Enter details:
   - **Name**: `Movies` or descriptive name
   - **Path**: `/path/to/your/media`
   - **Media Type**: Movies, TV Shows, or Mixed
5. Click **Save**
6. Click **Scan** to discover media

**Via API:**

```bash
curl -X POST http://localhost:8411/api/libraries \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Movies",
    "library_type": "local",
    "path": "/media/movies",
    "media_type": "movie"
  }'
```

### Local Library Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Path | Root folder path | Required |
| Media Type | movie, show, mixed | mixed |
| File Extensions | Extensions to scan | mp4,mkv,avi,mov |
| Scan Interval | Hours between scans | 24 |
| Recursive | Scan subdirectories | true |

### File Organization

For best results, organize your files:

**Movies:**
```
/media/movies/
├── Movie Name (2024)/
│   ├── Movie Name (2024).mkv
│   └── Movie Name (2024).nfo    # Optional metadata
├── Another Movie (2023).mp4
```

**TV Shows:**
```
/media/tv/
├── Show Name/
│   ├── Season 01/
│   │   ├── Show Name - S01E01 - Episode Title.mkv
│   │   ├── Show Name - S01E02 - Episode Title.mkv
│   ├── Season 02/
│   │   ├── Show Name - S02E01 - Episode Title.mkv
```

---

## Plex Integration

Connect your Plex Media Server for seamless library access.

### Prerequisites

- Plex Media Server running and accessible
- Plex authentication token

### Getting Your Plex Token

**Option 1: From Plex Web**

1. Open Plex Web App
2. Play any media
3. Open browser developer tools (F12)
4. Go to **Network** tab
5. Look for requests to `plex.tv`
6. Find `X-Plex-Token` in headers

**Option 2: Via API**

```bash
curl -X POST 'https://plex.tv/users/sign_in.json' \
  -H 'X-Plex-Client-Identifier: EXStreamTV' \
  -d 'user[login]=your_email&user[password]=your_password'
```

### Adding Plex Library

**Via Web UI:**

1. Go to **Libraries** → **+ Add Library**
2. Select **Plex**
3. Enter connection details:
   - **Server URL**: `http://192.168.1.100:32400`
   - **Token**: Your Plex token
4. Click **Discover Libraries**
5. Select libraries to sync
6. Click **Save**

**Via API:**

```bash
curl -X POST http://localhost:8411/api/libraries \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Plex Movies",
    "library_type": "plex",
    "server_url": "http://192.168.1.100:32400",
    "token": "your-plex-token",
    "library_key": "1"
  }'
```

### Plex Features

- **Direct Play**: Stream optimized versions from Plex
- **Transcoding**: Use Plex's transcoding or EXStreamTV's
- **Metadata Sync**: Import Plex's rich metadata
- **Watch State**: Respect Plex's watched status (optional)

### Plex Settings

| Setting | Description |
|---------|-------------|
| Server URL | Plex server address |
| Token | Authentication token |
| Use Direct Play | Stream directly vs transcode |
| Sync Metadata | Import Plex metadata |
| Sync Collections | Import Plex collections |

---

## Jellyfin Integration

Connect to your Jellyfin server for free, open-source media management.

### Prerequisites

- Jellyfin server running
- API key or user credentials

### Getting Your Jellyfin API Key

1. Open Jellyfin Dashboard
2. Go to **Administration** → **API Keys**
3. Click **+** to create new key
4. Name it `EXStreamTV`
5. Copy the generated key

### Adding Jellyfin Library

**Via Web UI:**

1. Go to **Libraries** → **+ Add Library**
2. Select **Jellyfin**
3. Enter details:
   - **Server URL**: `http://192.168.1.100:8096`
   - **API Key**: Your Jellyfin API key
4. Click **Discover Libraries**
5. Select libraries to sync
6. Click **Save**

**Via API:**

```bash
curl -X POST http://localhost:8411/api/libraries \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jellyfin TV",
    "library_type": "jellyfin",
    "server_url": "http://192.168.1.100:8096",
    "api_key": "your-jellyfin-api-key",
    "user_id": "optional-user-id"
  }'
```

### Jellyfin Settings

| Setting | Description |
|---------|-------------|
| Server URL | Jellyfin server address |
| API Key | Authentication key |
| User ID | Specific user (optional) |
| Include Special Features | Import extras/featurettes |

---

## Emby Integration

Connect to your Emby server with similar functionality to Jellyfin.

### Prerequisites

- Emby server running
- API key

### Getting Your Emby API Key

1. Open Emby Dashboard
2. Go to **Advanced** → **Security**
3. Under **Api Keys**, click **New Api Key**
4. Name it `EXStreamTV`
5. Copy the key

### Adding Emby Library

**Via Web UI:**

1. Go to **Libraries** → **+ Add Library**
2. Select **Emby**
3. Enter details:
   - **Server URL**: `http://192.168.1.100:8096`
   - **API Key**: Your Emby API key
4. Click **Discover Libraries**
5. Select libraries to sync
6. Click **Save**

---

## Media Organization

### Automatic Recognition

EXStreamTV uses multiple methods to identify media:

1. **Filename Parsing**: Extracts title, year, season, episode
2. **NFO Files**: Reads Kodi-compatible metadata files
3. **Online Lookup**: Queries TMDB, TVDB for matches
4. **Folder Structure**: Infers organization from paths

### Naming Conventions

For best automatic recognition:

**Movies:**
```
Movie Title (Year).ext
Movie Title (Year) - Quality.ext
```

Examples:
```
The Matrix (1999).mkv
Inception (2010) - 1080p BluRay.mkv
```

**TV Shows:**
```
Show Name - S##E## - Episode Title.ext
Show.Name.S##E##.Episode.Title.ext
```

Examples:
```
Breaking Bad - S01E01 - Pilot.mkv
Game.of.Thrones.S08E06.The.Iron.Throne.mkv
```

### Collections

Group related content automatically:

- Movie franchises (Marvel, Star Wars)
- TV show seasons
- Custom collections

Create collections in **Libraries** → **Collections**.

---

## Metadata Management

### Metadata Sources

EXStreamTV fetches metadata from:

| Source | Movies | TV Shows | Priority |
|--------|--------|----------|----------|
| NFO Files | ✅ | ✅ | 1 (highest) |
| TMDB | ✅ | ✅ | 2 |
| TVDB | ❌ | ✅ | 3 |
| Embedded | ✅ | ✅ | 4 |

### NFO File Support

Create `.nfo` files alongside your media for manual metadata:

**Movie NFO:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <title>Movie Title</title>
  <year>2024</year>
  <plot>Movie description goes here...</plot>
  <genre>Action</genre>
  <genre>Thriller</genre>
  <rating>8.5</rating>
  <runtime>120</runtime>
  <thumb>poster.jpg</thumb>
</movie>
```

**TV Show NFO:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<tvshow>
  <title>Show Name</title>
  <year>2020</year>
  <plot>Show description...</plot>
  <genre>Drama</genre>
</tvshow>
```

### Refreshing Metadata

1. Go to **Libraries**
2. Select a library
3. Click **Refresh Metadata**

Or for individual items:
1. Go to **Browse** → Find the item
2. Click the menu (⋮) → **Refresh Metadata**

### API Keys for Metadata

Configure API keys in **Settings** → **Metadata**:

- **TMDB API Key**: Get from [themoviedb.org](https://www.themoviedb.org/settings/api)
- **TVDB API Key**: Get from [thetvdb.com](https://thetvdb.com/dashboard/account/apikey)

---

## Scanning and Syncing

### Manual Scan

**Single Library:**
1. Go to **Libraries**
2. Find the library
3. Click **Scan**

**All Libraries:**
1. Go to **Settings** → **Libraries**
2. Click **Scan All Libraries**

### Automatic Scanning

Configure scan intervals:

```yaml
# config.yaml
libraries:
  scan_on_startup: true
  scan_interval_hours: 24
  watch_for_changes: true  # File system watcher
```

### Scan Status

Monitor scan progress:
- View in **Libraries** → Library card shows progress
- Check **System Monitor** for background tasks
- API: `GET /api/libraries/{id}/scan/status`

### Syncing from Plex/Jellyfin

When connected to external servers:

1. **Initial Sync**: Full library import
2. **Incremental Sync**: Only changes synced
3. **Metadata Refresh**: Updates from server

Configure in library settings:
- **Sync Interval**: How often to check for changes
- **Sync Watched State**: Track what's been played

---

## Troubleshooting

### Library Not Showing Content

**Check path permissions:**
```bash
ls -la /path/to/media
```

**Verify file extensions:**
- Default: `.mp4, .mkv, .avi, .mov`
- Add custom extensions in library settings

**Check scan logs:**
1. Go to **Settings** → **Logs**
2. Filter by "scan" or library name

### Plex Connection Failed

- Verify Plex is running: `http://your-plex-ip:32400`
- Check token is valid
- Ensure EXStreamTV can reach Plex (firewall)
- Try: `curl -H "X-Plex-Token: YOUR_TOKEN" http://plex:32400/identity`

### Jellyfin/Emby Connection Issues

- Verify server URL (including port)
- Check API key has correct permissions
- Test: `curl -H "X-Emby-Token: YOUR_KEY" http://server:8096/System/Info`

### Missing Metadata

1. Check internet connectivity
2. Verify API keys are configured
3. Manually refresh: Library → Item → Refresh Metadata
4. Check filename matches expected format

### Slow Scanning

- Reduce concurrent scans in settings
- Disable FFprobe analysis for initial scan
- Use SSD for database storage
- Exclude unnecessary directories

### Duplicate Items

- Check for multiple library paths pointing to same content
- Remove overlapping library configurations
- Use **Libraries** → **Deduplicate** tool

---

## Best Practices

1. **Organize files properly** - Use standard naming conventions
2. **Use NFO files** - For custom or corrected metadata
3. **Configure API keys** - Enable rich metadata lookup
4. **Regular scans** - Keep library in sync with files
5. **Monitor logs** - Catch issues early

---

## See Also

- [Quick Start Guide](QUICK_START.md)
- [Hardware Transcoding](HW_TRANSCODING.md)
- [API Reference](../api/README.md)
