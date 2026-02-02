{info:title=EXStreamTV Quick Start Guide}
Version 2.6.0 | Last Updated: 2026-01-31
{info}

h1. Quick Start Guide

Get your first channel streaming in 10 minutes!

----

h2. Prerequisites

* macOS 12+ (Monterey or later)
* Python 3.9+ (included with macOS)
* FFmpeg (we'll install it)

----

h2. Step 1: Install EXStreamTV

h3. Option A: macOS App (Easiest)

# Download {{EXStreamTV.dmg}} from GitHub Releases
# Drag to Applications folder
# Launch EXStreamTV from menu bar
# Follow the onboarding wizard

h3. Option B: Command Line

{code:language=bash}
# Clone the repository
git clone https://github.com/roto31/EXStreamTV.git
cd EXStreamTV

# Install dependencies
pip install -r requirements.txt

# Start the server
python -m exstreamtv
{code}

----

h2. Step 2: Access the Dashboard

Open your browser to:

{code}
http://localhost:8411
{code}

You should see the EXStreamTV dashboard:

{panel:title=Dashboard|borderStyle=solid}
* Quick stats for channels, playlists, streams
* System resource monitoring
* Active streams panel
* Recent activity feed
{panel}

----

h2. Step 3: Create Your First Channel

# Click *Channels* in the sidebar
# Click the *+* button to create a new channel
# Fill in the details:
** *Name*: My First Channel
** *Number*: 1
** *Group*: Entertainment
# Click *Save*

----

h2. Step 4: Add Content

h3. Option A: Quick Add (M3U Import)

# Go to *Import* in the sidebar
# Paste an M3U URL or upload a file
# Select channels to import
# Click *Import Selected*

h3. Option B: Create a Playlist

# Go to *Playlists* in the sidebar
# Click *+* to create a new playlist
# Search for content to add
# Drag items to your playlist
# Assign the playlist to your channel

h3. Option C: Local Media

# Go to *Libraries* in the sidebar
# Click *Add Library*
# Select *Local Folder*
# Browse to your media folder
# Wait for scan to complete
# Add items to playlists or channels

----

h2. Step 5: Watch Your Channel!

h3. Get Your Stream URL

Your channel is now available at:

{code}
http://localhost:8411/iptv/channels/1/stream.m3u8
{code}

h3. In VLC

# Open VLC
# Media > Open Network Stream
# Paste the stream URL
# Click Play

h3. In IPTV Apps

Get the M3U playlist for all channels:

{code}
http://localhost:8411/iptv/channels.m3u
{code}

Add this URL to any IPTV app (IPTV Smarters, TiviMate, etc.)

h3. In Plex/Jellyfin (HDHomeRun)

EXStreamTV emulates an HDHomeRun device:

# In Plex: Settings > Live TV & DVR > Set Up
# In Jellyfin: Dashboard > Live TV > Tuner Devices
# EXStreamTV should be auto-discovered
# Add the tuner and scan for channels

----

h2. Next Steps

h3. Set Up AI Channel Creator

Let AI help you create channels automatically:

# Go to *Channels* > *AI Channel Creator*
# Choose a persona (TV Executive, Movie Critic, etc.)
# Describe what kind of channel you want
# Review and approve the generated plan

{tip}See [AI Setup Guide|EXStreamTV:AI Setup] for configuration.{tip}

h3. Configure Hardware Transcoding

Speed up streaming with GPU acceleration:

# Go to *Settings* > *FFmpeg*
# Enable hardware acceleration
# Select your GPU type (VideoToolbox, NVENC, etc.)

{tip}See [Hardware Transcoding Guide|EXStreamTV:Hardware Transcoding] for details.{tip}

h3. Add Time-Based Scheduling

Create TV-like programming schedules:

# Go to *Schedules* > *Schedule Builder*
# Drag content to time slots
# Configure blocks for different times of day

{tip}See [Advanced Scheduling Guide|EXStreamTV:Advanced Scheduling] for details.{tip}

----

h2. Troubleshooting

h3. "Channel not streaming"

* Check that FFmpeg is installed: {{ffmpeg -version}}
* Verify the channel has content assigned
* Check the logs: Settings > Logs

h3. "Can't access dashboard"

* Ensure the server is running
* Check if port 8411 is in use: {{lsof -i :8411}}
* Try a different port in config.yaml

h3. "Media not found"

* Verify file paths are accessible
* Run a library rescan
* Check file permissions

----

h2. Quick Reference

h3. URLs

||Service||URL||
|Dashboard|http://localhost:8411|
|API|http://localhost:8411/api|
|M3U Playlist|http://localhost:8411/iptv/channels.m3u|
|EPG (XMLTV)|http://localhost:8411/iptv/xmltv.xml|
|HDHomeRun Discovery|http://localhost:8411/discover.json|
|API Docs (Swagger)|http://localhost:8411/api/docs|

h3. Keyboard Shortcuts

||Shortcut||Action||
|{{⌘ + K}}|Quick search|
|{{⌘ + N}}|New channel|
|{{⌘ + ,}}|Settings|
|{{⌘ + R}}|Refresh|

----

h2. Related Documentation

* [Installation Guide|EXStreamTV:Installation] - Detailed installation
* [AI Setup Guide|EXStreamTV:AI Setup] - Configure AI providers
* [Streaming Stability|EXStreamTV:Streaming Stability] - v2.6.0 streaming features
* [API Reference|EXStreamTV:API Reference] - REST API documentation
