{info:title=EXStreamTV API Documentation}
Version 2.6.0 | Last Updated: 2026-01-31
{info}

h1. EXStreamTV API Documentation

Welcome to the EXStreamTV API documentation. This guide explains how to use the API to control your streaming server, manage channels, organize content, and build custom schedules.

----

h2. Table of Contents

* [Getting Started|#getting-started]
* [How the API Works|#how-the-api-works]
* [Core APIs|#core-apis]
* [Scheduling APIs|#scheduling-apis]
* [AI Self-Healing API|#ai-self-healing-api]
* [Streaming & IPTV|#streaming-iptv]
* [Error Handling|#error-handling]

----

h2. Getting Started

h3. What is an API?

An API (Application Programming Interface) is a way for software programs to talk to each other. Think of it like a waiter at a restaurant: you tell the waiter what you want (make a request), and the waiter brings you your food (returns a response).

h3. Base URL

All API requests go to this address:

{code}
http://localhost:8411/api
{code}

If you're accessing EXStreamTV from another computer on your network, replace {{localhost}} with your server's IP address (like {{192.168.1.100}}).

h3. Making Your First Request

*Using a web browser:* Just visit {{http://localhost:8411/api/channels}}

*Using the command line:*
{code:language=bash}
curl http://localhost:8411/api/channels
{code}

*Using JavaScript:*
{code:language=javascript}
const response = await fetch('http://localhost:8411/api/channels');
const data = await response.json();
console.log(data);
{code}

h3. Authentication

By default, EXStreamTV doesn't require a password for local use. For remote access, you can enable API key authentication in your configuration.

----

h2. How the API Works

h3. Request Methods

||Method||What It Does||Example||
|*GET*|Retrieve information|Get a list of channels|
|*POST*|Create something new|Create a new channel|
|*PUT*|Update something existing|Change a channel's name|
|*DELETE*|Remove something|Delete a channel|

h3. Request and Response Format

All data is sent and received as JSON:

{code:language=json}
{
  "name": "Movie Channel",
  "number": 5,
  "enabled": true
}
{code}

h3. Understanding Responses

Common status codes:
* *200* - Success! Everything worked.
* *201* - Created! A new item was made.
* *204* - Deleted! The item was removed.
* *400* - Bad request. Something was wrong with your request.
* *404* - Not found. The item doesn't exist.
* *500* - Server error. Something went wrong on our end.

----

h2. Core APIs

h3. Channels

Channels are virtual TV stations that stream your content.

h4. List All Channels

{code}
GET /api/channels
{code}

*Example Response:*
{code:language=json}
[
  {
    "id": 1,
    "number": 1,
    "name": "Movies 24/7",
    "group": "Entertainment",
    "enabled": true,
    "logo_url": "/api/channels/1/logo"
  },
  {
    "id": 2,
    "number": 2,
    "name": "Classic TV",
    "group": "Entertainment",
    "enabled": true
  }
]
{code}

h4. Get a Single Channel

{code}
GET /api/channels/{id}
{code}

h4. Create a New Channel

{code}
POST /api/channels
{code}

*What to send:*
{code:language=json}
{
  "number": 3,
  "name": "Kids Shows",
  "group": "Family",
  "enabled": true
}
{code}

h4. Update a Channel

{code}
PUT /api/channels/{id}
{code}

h4. Delete a Channel

{code}
DELETE /api/channels/{id}
{code}

h3. Playlists

Playlists are ordered lists of media items that play in sequence.

h4. List All Playlists

{code}
GET /api/playlists
{code}

h4. Get a Playlist

{code}
GET /api/playlists/{id}
{code}

h4. Create a Playlist

{code}
POST /api/playlists
{code}

*What to send:*
{code:language=json}
{
  "name": "Saturday Night Movies",
  "description": "Action films for the weekend"
}
{code}

h4. Add Item to Playlist

{code}
POST /api/playlists/{id}/items/{media_id}
{code}

h4. Remove Item from Playlist

{code}
DELETE /api/playlists/{id}/items/{media_id}
{code}

----

h2. Scheduling APIs

h3. Schedules

Schedules define what content plays and in what order.

h4. List All Schedules

{code}
GET /api/schedules
{code}

h4. Create a Schedule

{code}
POST /api/schedules
{code}

*What to send:*
{code:language=json}
{
  "name": "Weekday Programming",
  "keep_multi_part_episodes": true,
  "shuffle_schedule_items": false
}
{code}

h3. Playouts

A playout is the actual running program for a channel.

h4. List All Playouts

{code}
GET /api/playouts
{code}

h4. Get Current Item

{code}
GET /api/playouts/{id}/current
{code}

h4. Skip Current Item

{code}
POST /api/playouts/{id}/skip
{code}

h3. Blocks

Blocks are time-based programming segments.

h4. List All Blocks

{code}
GET /api/blocks
{code}

h4. Create a Block

{code}
POST /api/blocks
{code}

*What to send:*
{code:language=json}
{
  "name": "Prime Time Movies",
  "group_id": 1,
  "start_time": "20:00",
  "duration_minutes": 180,
  "days_of_week": 127
}
{code}

*Understanding days_of_week:*

||Day||Value||
|Sunday|1|
|Monday|2|
|Tuesday|4|
|Wednesday|8|
|Thursday|16|
|Friday|32|
|Saturday|64|

Examples:
* All days = 127 (1+2+4+8+16+32+64)
* Weekdays only = 62 (2+4+8+16+32)
* Weekends only = 65 (1+64)

----

h2. AI Self-Healing API

{panel:title=NEW in v2.6.0|borderStyle=solid|borderColor=#9C27B0}
The AI Self-Healing system provides autonomous issue detection and resolution.
{panel}

h3. Get AI Health Status

{code}
GET /api/ai/health
{code}

*Example Response:*
{code:language=json}
{
  "log_collector": {
    "running": true,
    "buffer_size": 5000,
    "total_events": 125000,
    "errors_count": 42
  },
  "ffmpeg_monitor": {
    "channels_monitored": 12,
    "total_errors": 15,
    "active_predictions": 2
  },
  "pattern_detector": {
    "patterns_detected": 8,
    "predictions_made": 25,
    "accuracy": 0.88
  },
  "auto_resolver": {
    "enabled": true,
    "total_resolutions": 45,
    "success_rate": 0.93,
    "fixes_this_hour": 3
  }
}
{code}

h3. Get Channel Health Metrics

{code}
GET /api/ai/channels/{channel_id}/health
{code}

*Example Response:*
{code:language=json}
{
  "channel_id": 1,
  "status": "healthy",
  "current_fps": 29.97,
  "expected_fps": 30.0,
  "current_speed": 1.02,
  "current_bitrate_kbps": 4250,
  "dropped_frames": 5,
  "duplicate_frames": 12,
  "error_count": 0,
  "restart_count": 1
}
{code}

h3. Get Recent Errors

{code}
GET /api/ai/errors?minutes=60&max_errors=50
{code}

h3. Get Active Sessions

{code}
GET /api/ai/sessions
{code}

*Example Response:*
{code:language=json}
{
  "total_sessions": 15,
  "sessions_by_channel": {
    "1": 8,
    "2": 4,
    "3": 3
  },
  "sessions": [
    {
      "session_id": "abc123",
      "channel_id": 1,
      "client_ip": "192.168.1.100",
      "state": "active",
      "bytes_sent": 125000000,
      "duration_seconds": 3600
    }
  ]
}
{code}

h3. Database Backup Operations

h4. Trigger Manual Backup

{code}
POST /api/database/backup
{code}

*What to send:*
{code:language=json}
{
  "description": "Manual backup before maintenance",
  "compress": true
}
{code}

h4. List Backups

{code}
GET /api/database/backups
{code}

h4. Restore Backup

{code}
POST /api/database/restore
{code}

*What to send:*
{code:language=json}
{
  "backup_path": "backups/exstreamtv_backup_20260131.db.gz",
  "create_safety_backup": true
}
{code}

----

h2. Streaming & IPTV

h3. Get M3U Playlist

{code}
GET /iptv/channels.m3u
{code}

h3. Get EPG (Program Guide)

{code}
GET /iptv/xmltv.xml?hours=24
{code}

h3. HDHomeRun Emulation

h4. Device Discovery

{code}
GET /discover.json
{code}

h4. Channel Lineup

{code}
GET /lineup.json
{code}

----

h2. Error Handling

When something goes wrong, the API returns an error response:

{code:language=json}
{
  "detail": "Channel not found",
  "status_code": 404
}
{code}

h3. Common Errors

||Code||Meaning||What to Do||
|400|Bad Request|Check your request format and required fields|
|404|Not Found|The item you're looking for doesn't exist|
|409|Conflict|The item already exists (duplicate)|
|422|Validation Error|Check your data types and values|
|500|Server Error|Try again; check server logs if it persists|

----

h2. Interactive Documentation

When EXStreamTV is running, you can access interactive API documentation:

* *Swagger UI*: [http://localhost:8411/api/docs|http://localhost:8411/api/docs]
* *ReDoc*: [http://localhost:8411/api/redoc|http://localhost:8411/api/redoc]

----

h2. Quick Reference

h3. Most Common Operations

||Task||Method||Endpoint||
|List channels|GET|/api/channels|
|Create channel|POST|/api/channels|
|Delete channel|DELETE|/api/channels/\{id\}|
|List playlists|GET|/api/playlists|
|Get M3U playlist|GET|/iptv/channels.m3u|
|Start stream|GET|/api/channels/\{id\}/stream.m3u8|
|Health check|GET|/api/health|
|AI health|GET|/api/ai/health|

h3. ErsatzTV-Compatible Features

||Feature||Endpoints||
|Time Blocks|/api/blocks, /api/block-groups|
|Templates|/api/templates, /api/template-groups|
|Filler Content|/api/filler-presets|
|Bumpers & Station IDs|/api/deco, /api/deco-groups|
|Multi-Collections|/api/collections/multi|
|Scripted Schedules|/api/scripted/build/*|
|Build Sessions|/api/playouts/\{id\}/build/*|

h3. v2.6.0 Features

||Feature||Endpoints||
|AI Self-Healing|/api/ai/*|
|Session Management|/api/ai/sessions|
|Channel Health|/api/ai/channels/\{id\}/health|
|Database Backup|/api/database/backup, /api/database/backups|
|Database Restore|/api/database/restore|

----

h2. Need Help?

* Check the [Quick Start Guide|EXStreamTV:Quick Start]
* Read the [System Design|EXStreamTV:System Design]
* Read the [Tunarr/dizqueTV Integration|EXStreamTV:Tunarr Integration]
* Use the interactive docs at /api/docs
* View streaming logs at /logs
