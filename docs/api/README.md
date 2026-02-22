# EXStreamTV API Documentation

Welcome to the EXStreamTV API documentation. This guide explains how to use the API to control your streaming server, manage channels, organize content, and build custom schedules. For HDHomeRun emulation, streaming lifecycle, and observability, see the [Platform Guide](../PLATFORM_GUIDE.md).

## Table of Contents

- [Getting Started](#getting-started)
- [How the API Works](#how-the-api-works)
- [Core APIs](#core-apis)
  - [Channels](#channels)
  - [Playlists](#playlists)
  - [Collections](#collections)
  - [Media Items](#media-items)
- [Scheduling APIs](#scheduling-apis)
  - [Schedules](#schedules)
  - [Playouts](#playouts)
  - [Blocks](#blocks)
  - [Templates](#templates)
- [Content Enhancement APIs](#content-enhancement-apis)
  - [Filler Presets](#filler-presets)
  - [Deco (Bumpers & Station IDs)](#deco-bumpers--station-ids)
  - [Multi-Collections](#multi-collections)
- [Advanced APIs](#advanced-apis)
  - [Scripted Schedule Builder](#scripted-schedule-builder)
  - [Build Sessions](#build-sessions)
- [Streaming & IPTV](#streaming--iptv)
- [System & Settings](#system--settings)
- [Error Handling](#error-handling)
- [Interactive Documentation](#interactive-documentation)

---

## Getting Started

### What is an API?

An API (Application Programming Interface) is a way for software programs to talk to each other. Think of it like a waiter at a restaurant: you tell the waiter what you want (make a request), and the waiter brings you your food (returns a response). The API is the waiter between you and the EXStreamTV server.

### Base URL

All API requests go to this address:

```
http://localhost:8411/api
```

If you're accessing EXStreamTV from another computer on your network, replace `localhost` with your server's IP address (like `192.168.1.100`).

### Making Your First Request

Here's how to get a list of all your channels:

**Using a web browser:** Just visit `http://localhost:8411/api/channels`

**Using the command line:**
```bash
curl http://localhost:8411/api/channels
```

**Using JavaScript:**
```javascript
const response = await fetch('http://localhost:8411/api/channels');
const data = await response.json();
console.log(data);
```

### Authentication

By default, EXStreamTV doesn't require a password for local use. For remote access, you can enable API key authentication in your configuration.

---

## How the API Works

### Request Methods

The API uses different "methods" to perform different actions:

| Method | What It Does | Example |
|--------|--------------|---------|
| **GET** | Retrieve information | Get a list of channels |
| **POST** | Create something new | Create a new channel |
| **PUT** | Update something existing | Change a channel's name |
| **DELETE** | Remove something | Delete a channel |

### Request and Response Format

All data is sent and received as JSON (JavaScript Object Notation). JSON is a simple text format that looks like this:

```json
{
  "name": "Movie Channel",
  "number": 5,
  "enabled": true
}
```

### Understanding Responses

When you make a request, you'll get back:

1. **A status code** - A number indicating success or failure
2. **Response data** - The information you requested (in JSON format)

Common status codes:
- **200** - Success! Everything worked.
- **201** - Created! A new item was made.
- **204** - Deleted! The item was removed.
- **400** - Bad request. Something was wrong with your request.
- **404** - Not found. The item doesn't exist.
- **500** - Server error. Something went wrong on our end.

---

## Core APIs

These are the fundamental APIs for managing your streaming content.

### Channels

Channels are virtual TV stations that stream your content. Each channel has a number, name, and plays content from a playlist or schedule.

#### List All Channels

Get a list of every channel you've created.

```
GET /api/channels
```

**Example Response:**
```json
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
```

#### Get a Single Channel

Get detailed information about one specific channel.

```
GET /api/channels/{id}
```

Replace `{id}` with the channel's ID number.

**Example:** `GET /api/channels/1`

#### Create a New Channel

Add a new channel to your lineup.

```
POST /api/channels
```

**What to send:**
```json
{
  "number": 3,
  "name": "Kids Shows",
  "group": "Family",
  "enabled": true
}
```

#### Update a Channel

Change a channel's settings.

```
PUT /api/channels/{id}
```

**What to send:** Only include the fields you want to change.
```json
{
  "name": "Children's Programming"
}
```

#### Delete a Channel

Remove a channel permanently.

```
DELETE /api/channels/{id}
```

#### Get Channel's Filler Configuration

See what filler content is assigned to a channel.

```
GET /api/channels/{id}/filler
```

**Example Response:**
```json
{
  "channel_id": 1,
  "fallback_filler_id": 5,
  "pre_roll_filler_id": 2,
  "post_roll_filler_id": null,
  "fallback_filler": {
    "id": 5,
    "name": "Commercial Breaks",
    "filler_mode": "duration"
  }
}
```

#### Update Channel's Filler Configuration

Assign filler presets to a channel.

```
PUT /api/channels/{id}/filler
```

**What to send:**
```json
{
  "fallback_filler_id": 5,
  "pre_roll_filler_id": 2
}
```

#### Get Channel's Deco Configuration

See what decorative content (bumpers, station IDs) is assigned.

```
GET /api/channels/{id}/deco
```

#### Update Channel's Deco Configuration

Assign deco groups to a channel.

```
PUT /api/channels/{id}/deco
```

**What to send:**
```json
{
  "deco_group_id": 3,
  "bumper_group_id": 1
}
```

#### Get Programming Guide

See what's scheduled to play on a channel.

```
GET /api/channels/{id}/programming?hours=24
```

**Parameters:**
- `hours` - How many hours of programming to show (default: 24)

---

### Playlists

Playlists are ordered lists of media items that play in sequence.

#### List All Playlists

```
GET /api/playlists
```

#### Get a Playlist

```
GET /api/playlists/{id}
```

Returns the playlist with all its items.

#### Create a Playlist

```
POST /api/playlists
```

**What to send:**
```json
{
  "name": "Saturday Night Movies",
  "description": "Action films for the weekend"
}
```

#### Add Item to Playlist

```
POST /api/playlists/{id}/items/{media_id}
```

#### Remove Item from Playlist

```
DELETE /api/playlists/{id}/items/{media_id}
```

#### Reorder Playlist Items

```
POST /api/playlists/{id}/reorder
```

**What to send:**
```json
{
  "item_ids": [5, 3, 1, 4, 2]
}
```

The items will be reordered to match the order you specify.

---

### Collections

Collections are groups of related media items. Unlike playlists, collections don't have a specific order—they're just ways to organize your content.

#### List All Collections

```
GET /api/collections
```

#### Get a Collection

```
GET /api/collections/{id}
```

#### Create a Collection

```
POST /api/collections
```

**What to send:**
```json
{
  "name": "80s Action Movies",
  "description": "The best action films from the 1980s"
}
```

#### Create a Smart Collection

Smart collections automatically find and include media based on search criteria.

```
POST /api/collections/smart
```

**Parameters:**
- `name` - Name for the collection
- `search_query` - What to search for
- `description` - Optional description

**Example:** Create a collection that automatically includes all Star Wars content:
```
POST /api/collections/smart?name=Star Wars&search_query=star wars
```

#### Refresh a Smart Collection

Re-run the search to update the collection with new matching items.

```
POST /api/collections/smart/{id}/refresh
```

#### Add Item to Collection

```
POST /api/collections/{id}/items/{media_id}
```

#### Remove Item from Collection

```
DELETE /api/collections/{id}/items/{media_id}
```

---

### Media Items

Media items are individual videos, movies, or TV episodes in your library.

#### List Media Items

```
GET /api/media
```

**Optional filters:**
- `library_id` - Only show items from a specific library
- `media_type` - Filter by type: `movie`, `episode`, `other_video`
- `query` - Search by title
- `limit` - Maximum number of results
- `offset` - Skip this many results (for pagination)

#### Get a Media Item

```
GET /api/media/{id}
```

Returns complete information about a media item including file paths, duration, and metadata.

---

## Scheduling APIs

These APIs control when and how content plays on your channels.

### Schedules

Schedules define what content plays and in what order.

#### List All Schedules

```
GET /api/schedules
```

#### Get a Schedule

```
GET /api/schedules/{id}
```

#### Create a Schedule

```
POST /api/schedules
```

**What to send:**
```json
{
  "name": "Weekday Programming",
  "keep_multi_part_episodes": true,
  "shuffle_schedule_items": false
}
```

#### Update a Schedule

```
PUT /api/schedules/{id}
```

#### Delete a Schedule

```
DELETE /api/schedules/{id}
```

---

### Playouts

A playout is the actual running program for a channel—it turns your schedule into a real-time stream of content.

#### List All Playouts

```
GET /api/playouts
```

#### Get a Playout

```
GET /api/playouts/{id}
```

#### Get Current Item

See what's currently playing on a playout.

```
GET /api/playouts/{id}/current
```

#### Get Upcoming Items

See what's coming up next.

```
GET /api/playouts/{id}/upcoming?count=10
```

#### Skip Current Item

Jump to the next item in the playout.

```
POST /api/playouts/{id}/skip
```

---

### Blocks

Blocks are time-based programming segments. For example, you might have a "Morning Cartoons" block from 6 AM to 9 AM.

#### Block Groups

Block groups help you organize related blocks together.

##### List All Block Groups

```
GET /api/block-groups
```

**Example Response:**
```json
[
  {
    "id": 1,
    "name": "Weekday Blocks",
    "block_count": 5
  },
  {
    "id": 2,
    "name": "Weekend Blocks",
    "block_count": 3
  }
]
```

##### Create a Block Group

```
POST /api/block-groups
```

**What to send:**
```json
{
  "name": "Holiday Specials"
}
```

##### Get a Block Group

```
GET /api/block-groups/{id}
```

##### Update a Block Group

```
PUT /api/block-groups/{id}
```

##### Delete a Block Group

Deletes the group and all blocks inside it.

```
DELETE /api/block-groups/{id}
```

#### Blocks

##### List All Blocks

```
GET /api/blocks
```

**Optional filter:**
- `group_id` - Only show blocks from a specific group

**Example Response:**
```json
[
  {
    "id": 1,
    "name": "Morning Cartoons",
    "group_id": 1,
    "start_time": "06:00",
    "duration_minutes": 180,
    "days_of_week": 127,
    "items": []
  }
]
```

##### Create a Block

```
POST /api/blocks
```

**What to send:**
```json
{
  "name": "Prime Time Movies",
  "group_id": 1,
  "start_time": "20:00",
  "duration_minutes": 180,
  "days_of_week": 127
}
```

**Understanding `days_of_week`:**

This is a number that represents which days the block is active. Each day has a value:

| Day | Value |
|-----|-------|
| Sunday | 1 |
| Monday | 2 |
| Tuesday | 4 |
| Wednesday | 8 |
| Thursday | 16 |
| Friday | 32 |
| Saturday | 64 |

Add up the values for the days you want. For example:
- All days = 1+2+4+8+16+32+64 = **127**
- Weekdays only = 2+4+8+16+32 = **62**
- Weekends only = 1+64 = **65**

##### Get a Block

```
GET /api/blocks/{id}
```

##### Update a Block

```
PUT /api/blocks/{id}
```

##### Delete a Block

```
DELETE /api/blocks/{id}
```

##### Add Item to Block

```
POST /api/blocks/{id}/items
```

**What to send:**
```json
{
  "collection_type": "collection",
  "collection_id": 5,
  "playback_order": "shuffled",
  "include_in_guide": true
}
```

**Playback order options:**
- `chronological` - Play in order
- `shuffled` - Randomize the order
- `random` - Pick randomly each time

##### Update a Block Item

```
PUT /api/blocks/{id}/items/{item_id}
```

##### Remove Item from Block

```
DELETE /api/blocks/{id}/items/{item_id}
```

##### Reorder Block Items

```
POST /api/blocks/{id}/items/reorder
```

**What to send:**
```json
{
  "item_ids": [3, 1, 2]
}
```

---

### Templates

Templates are reusable schedule patterns. Create a template once, then apply it to any channel.

#### Template Groups

##### List All Template Groups

```
GET /api/template-groups
```

##### Create a Template Group

```
POST /api/template-groups
```

**What to send:**
```json
{
  "name": "Standard Schedules"
}
```

##### Get a Template Group

```
GET /api/template-groups/{id}
```

##### Update a Template Group

```
PUT /api/template-groups/{id}
```

##### Delete a Template Group

```
DELETE /api/template-groups/{id}
```

#### Templates

##### List All Templates

```
GET /api/templates
```

**Optional filter:**
- `group_id` - Only show templates from a specific group

##### Create a Template

```
POST /api/templates
```

**What to send:**
```json
{
  "name": "Weekday Schedule",
  "group_id": 1,
  "is_enabled": true
}
```

##### Get a Template

```
GET /api/templates/{id}
```

##### Update a Template

```
PUT /api/templates/{id}
```

##### Delete a Template

```
DELETE /api/templates/{id}
```

##### Add Time Slot to Template

```
POST /api/templates/{id}/items
```

**What to send:**
```json
{
  "start_time": "18:00",
  "block_id": 5,
  "playback_order": "chronological"
}
```

Or reference a collection directly:
```json
{
  "start_time": "18:00",
  "collection_type": "collection",
  "collection_id": 10,
  "playback_order": "shuffled"
}
```

##### Update a Time Slot

```
PUT /api/templates/{id}/items/{item_id}
```

##### Remove a Time Slot

```
DELETE /api/templates/{id}/items/{item_id}
```

##### Apply Template to Channel

```
POST /api/templates/{id}/apply/{channel_id}
```

**What to send:**
```json
{
  "day_of_week": null
}
```

Set `day_of_week` to a number (0-6, where 0=Sunday) to apply only on that day, or `null` for all days.

---

## Content Enhancement APIs

These APIs help you add polish to your channels with filler content and branding.

### Filler Presets

Filler presets define what content plays in gaps between programs. This includes commercials, bumpers, or any short content.

#### List All Filler Presets

```
GET /api/filler-presets
```

**Example Response:**
```json
[
  {
    "id": 1,
    "name": "Commercial Breaks",
    "filler_mode": "duration",
    "duration_seconds": 180,
    "playback_order": "shuffled",
    "allow_repeats": true,
    "items": []
  }
]
```

#### Create a Filler Preset

```
POST /api/filler-presets
```

**What to send:**
```json
{
  "name": "30-Second Bumpers",
  "filler_mode": "duration",
  "duration_seconds": 30,
  "playback_order": "shuffled",
  "allow_repeats": false
}
```

**Filler modes:**

| Mode | Description | Required Field |
|------|-------------|----------------|
| `duration` | Fill a specific amount of time | `duration_seconds` |
| `count` | Play a specific number of items | `count` |
| `pad` | Fill until the next time boundary | `pad_to_minutes` |

**Examples:**
- Fill 3 minutes: `"filler_mode": "duration", "duration_seconds": 180`
- Play 2 items: `"filler_mode": "count", "count": 2`
- Pad to quarter hour: `"filler_mode": "pad", "pad_to_minutes": 15`

#### Get a Filler Preset

```
GET /api/filler-presets/{id}
```

#### Update a Filler Preset

```
PUT /api/filler-presets/{id}
```

#### Delete a Filler Preset

```
DELETE /api/filler-presets/{id}
```

#### Add Item to Filler Preset

```
POST /api/filler-presets/{id}/items
```

**What to send (for a collection):**
```json
{
  "collection_type": "collection",
  "collection_id": 15,
  "weight": 1
}
```

**What to send (for a single media item):**
```json
{
  "media_item_id": 42,
  "weight": 2
}
```

**Understanding weight:** Higher weight means the item is more likely to be selected. An item with weight 2 is twice as likely to be chosen as an item with weight 1.

#### Update a Filler Item

```
PUT /api/filler-presets/{id}/items/{item_id}
```

#### Remove Item from Filler Preset

```
DELETE /api/filler-presets/{id}/items/{item_id}
```

---

### Deco (Bumpers & Station IDs)

Deco items are decorative content like bumpers, station IDs, promos, and credits that add professional polish to your channels.

#### Deco Types

| Type | Description |
|------|-------------|
| `bumper` | Short transitional clips between programs |
| `commercial` | Advertisement or promotional content |
| `station_id` | Station identification clips ("You're watching...") |
| `promo` | Program promotional content |
| `credits` | Credit sequences |

#### Deco Groups

##### List All Deco Groups

```
GET /api/deco-groups
```

##### Create a Deco Group

```
POST /api/deco-groups
```

**What to send:**
```json
{
  "name": "Channel 5 Branding"
}
```

##### Get a Deco Group

```
GET /api/deco-groups/{id}
```

Returns the group with all its deco items.

##### Update a Deco Group

```
PUT /api/deco-groups/{id}
```

##### Delete a Deco Group

```
DELETE /api/deco-groups/{id}
```

#### Deco Items

##### List All Deco Items

```
GET /api/deco
```

**Optional filters:**
- `group_id` - Only show items from a specific group
- `deco_type` - Filter by type (bumper, commercial, etc.)

##### Create a Deco Item

```
POST /api/deco
```

**What to send:**
```json
{
  "name": "Station ID - Evening",
  "group_id": 1,
  "deco_type": "station_id",
  "file_path": "/media/branding/station_id_evening.mp4",
  "duration_seconds": 10,
  "weight": 1
}
```

##### Get a Deco Item

```
GET /api/deco/{id}
```

##### Update a Deco Item

```
PUT /api/deco/{id}
```

##### Delete a Deco Item

```
DELETE /api/deco/{id}
```

##### Get Available Deco Types

```
GET /api/deco/types
```

Returns a list of all valid deco types with descriptions.

---

### Multi-Collections

Multi-collections combine multiple collections into one, making it easy to schedule diverse content together.

#### List All Multi-Collections

```
GET /api/collections/multi
```

#### Create a Multi-Collection

```
POST /api/collections/multi
```

**Parameters:**
- `name` - Name for the multi-collection
- `description` - Optional description
- `collection_ids` - Optional list of collection IDs to include initially

**Example:**
```
POST /api/collections/multi?name=All Movies&description=Every movie collection combined
```

With initial collections:
```json
{
  "name": "All Movies",
  "collection_ids": [1, 5, 8, 12]
}
```

#### Get a Multi-Collection

```
GET /api/collections/multi/{id}
```

**Example Response:**
```json
{
  "id": 1,
  "name": "All Movies",
  "description": "Every movie collection combined",
  "collections": [
    {"id": 1, "name": "Action Movies", "position": 0},
    {"id": 5, "name": "Comedy Movies", "position": 1},
    {"id": 8, "name": "Drama Movies", "position": 2}
  ]
}
```

#### Update a Multi-Collection

```
PUT /api/collections/multi/{id}
```

#### Delete a Multi-Collection

```
DELETE /api/collections/multi/{id}
```

#### Add Collection to Multi-Collection

```
POST /api/collections/multi/{multi_id}/collections/{collection_id}
```

#### Remove Collection from Multi-Collection

```
DELETE /api/collections/multi/{multi_id}/collections/{collection_id}
```

---

## Advanced APIs

These APIs provide powerful programmatic control over your playouts.

### Scripted Schedule Builder

The Scripted Schedule API lets you build playout schedules step-by-step through code. This is perfect for creating complex, dynamic schedules programmatically.

#### How It Works

1. **Start a build session** for a playout
2. **Add content** using various commands
3. **Control timing** with padding and wait commands
4. **Toggle features** like watermarks and graphics
5. **Commit** to save or **cancel** to discard

### Build Sessions

#### Start a Build Session

```
POST /api/playouts/{playout_id}/build/start
```

**Example Response:**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "playout_id": 1,
  "status": "building",
  "current_time": "2026-01-17T10:00:00Z",
  "expires_at": "2026-01-17T11:00:00Z",
  "message": "Build session started"
}
```

**Important:** Save the `session_id`—you'll need it for all subsequent commands.

#### Get Build Context

See the current state of your build session.

```
GET /api/scripted/build/{session_id}/context
```

**Example Response:**
```json
{
  "build_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "playout_id": 1,
  "status": "building",
  "current_time": "2026-01-17T12:30:00Z",
  "items_buffered": 15,
  "watermark_enabled": true,
  "graphics_enabled": true,
  "pre_roll_enabled": true,
  "epg_group_active": false,
  "expires_at": "2026-01-17T13:00:00Z"
}
```

#### Commit Build Session

Save all your changes to the playout.

```
POST /api/playouts/{playout_id}/build/commit
```

**Optional parameter:**
- `session_id` - If you have multiple sessions

#### Cancel Build Session

Discard all changes without saving.

```
POST /api/playouts/{playout_id}/build/cancel
```

#### List Build Sessions

See all build sessions for a playout.

```
GET /api/playouts/{playout_id}/build/sessions
```

**Optional filter:**
- `status_filter` - Filter by status: `building`, `committed`, `cancelled`

---

### Adding Content to Build Sessions

#### Add a Collection

Add content from a collection to your schedule.

```
POST /api/scripted/build/{session_id}/add-collection
```

**What to send:**
```json
{
  "collection_id": 5,
  "count": 3,
  "playback_order": "shuffled"
}
```

**Options:**
- `collection_id` - Which collection to add
- `count` - How many items to add (optional)
- `duration_minutes` - Add items until this duration is filled (optional)
- `playback_order` - `chronological`, `shuffled`, or `random`

#### Add a Marathon

Add all episodes of a show in order.

```
POST /api/scripted/build/{session_id}/add-marathon
```

**What to send:**
```json
{
  "show_id": 42,
  "playback_order": "chronological"
}
```

#### Add a Multi-Collection

Add content from a multi-collection.

```
POST /api/scripted/build/{session_id}/add-multi-collection
```

**What to send:**
```json
{
  "multi_collection_id": 3,
  "playback_order": "shuffled"
}
```

#### Add a Playlist

```
POST /api/scripted/build/{session_id}/add-playlist
```

**What to send:**
```json
{
  "playlist_id": 10,
  "count": 5
}
```

#### Create and Add a Playlist

Create a new playlist on-the-fly and add it to the schedule.

```
POST /api/scripted/build/{session_id}/create-playlist
```

**What to send:**
```json
{
  "name": "Tonight's Special",
  "media_item_ids": [101, 102, 103, 104]
}
```

#### Add Search Results

Add media items matching a search query.

```
POST /api/scripted/build/{session_id}/add-search
```

**What to send:**
```json
{
  "query": "christmas",
  "count": 10,
  "media_type": "movie"
}
```

#### Add a Smart Collection

```
POST /api/scripted/build/{session_id}/add-smart-collection?collection_id=15&count=5
```

#### Add a Specific Show

```
POST /api/scripted/build/{session_id}/add-show
```

**What to send:**
```json
{
  "show_title": "Friends",
  "season": 3,
  "count": 4
}
```

#### Add All Items from a Collection

```
POST /api/scripted/build/{session_id}/add-all?collection_id=5
```

#### Add a Specific Count

```
POST /api/scripted/build/{session_id}/add-count
```

**What to send:**
```json
{
  "collection_id": 5,
  "count": 10
}
```

#### Add Items for a Duration

Fill a specific amount of time with content.

```
POST /api/scripted/build/{session_id}/add-duration
```

**What to send:**
```json
{
  "collection_id": 5,
  "duration_minutes": 120
}
```

---

### Timing and Padding Commands

#### Pad to Next Time Boundary

Fill time until the next quarter-hour, half-hour, or hour.

```
POST /api/scripted/build/{session_id}/pad-to-next
```

**What to send:**
```json
{
  "minutes": 30,
  "filler_preset_id": 5
}
```

This fills with filler content until the next 30-minute mark (e.g., 10:30, 11:00, 11:30).

#### Pad Until a Specific Time

Fill time until a specific clock time.

```
POST /api/scripted/build/{session_id}/pad-until
```

**What to send:**
```json
{
  "target_time": "20:00",
  "filler_preset_id": 5
}
```

#### Pad Until Exact Time

Same as above but with exact precision.

```
POST /api/scripted/build/{session_id}/pad-until-exact
```

#### Wait Until a Time (No Content)

Leave dead air until a specific time.

```
POST /api/scripted/build/{session_id}/wait-until
```

**What to send:**
```json
{
  "target_time": "18:00"
}
```

#### Wait Until Exact Time

```
POST /api/scripted/build/{session_id}/wait-until-exact
```

---

### Content Control Commands

#### Peek at Next Item

See what's next without consuming it.

```
GET /api/scripted/build/{session_id}/peek-next/{content_type}
```

**Content types:** `collection`, `playlist`, `show`

#### Skip Items

Skip over items in the current collection.

```
POST /api/scripted/build/{session_id}/skip-items
```

**What to send:**
```json
{
  "count": 2,
  "collection_id": 5
}
```

#### Skip to Specific Item

Jump to a specific item in a collection.

```
POST /api/scripted/build/{session_id}/skip-to-item
```

**What to send:**
```json
{
  "item_index": 10,
  "collection_id": 5
}
```

---

### EPG and Display Controls

#### Start EPG Group

Group upcoming items under a single title in the program guide.

```
POST /api/scripted/build/{session_id}/epg-group/start
```

**What to send:**
```json
{
  "title": "Movie Marathon"
}
```

All items added after this will appear under "Movie Marathon" in the guide.

#### Stop EPG Group

End the current EPG grouping.

```
POST /api/scripted/build/{session_id}/epg-group/stop
```

#### Toggle Graphics

Turn on-screen graphics on or off.

```
POST /api/scripted/build/{session_id}/graphics/on
POST /api/scripted/build/{session_id}/graphics/off
```

#### Toggle Watermark

Turn the channel watermark on or off.

```
POST /api/scripted/build/{session_id}/watermark/on
POST /api/scripted/build/{session_id}/watermark/off
```

#### Toggle Pre-Roll

Turn pre-roll content on or off.

```
POST /api/scripted/build/{session_id}/pre-roll/on
POST /api/scripted/build/{session_id}/pre-roll/off
```

---

## Streaming & IPTV

### Get M3U Playlist

Get an M3U playlist file for all your channels.

```
GET /iptv/channels.m3u
```

### Get EPG (Program Guide)

Get XMLTV format electronic program guide data.

```
GET /iptv/xmltv.xml?hours=24
```

### HDHomeRun Emulation

EXStreamTV emulates an HDHomeRun device for Plex, Jellyfin, and Emby. DeviceID must be 8 hex chars. See [Platform Guide §3](../PLATFORM_GUIDE.md#3-hdhomrun-emulation).

#### Device Discovery

```
GET /hdhomerun/discover.json
GET /discover.json  (redirects to /hdhomerun/discover.json)
```

Returns: FriendlyName, ModelNumber, DeviceID, BaseURL, LineupURL, GuideURL, TunerCount.

#### Channel Lineup

```
GET /hdhomerun/lineup.json
GET /lineup.json  (redirects to /hdhomerun/lineup.json)
```

Returns: Array of { GuideNumber, GuideName, URL } for enabled channels.

#### Tuner Stream

```
GET /hdhomerun/tuner{N}/stream?channel=auto:v{channel_number}
```

Streams MPEG-TS for the tuned channel. Plex uses the `url` parameter; EXStreamTV supports both.

### Prometheus Metrics

```
GET /metrics
```

Returns Prometheus text exposition format. See [Observability](../OBSERVABILITY.md) for metric reference.

---

## System & Settings

### Health Check

Check if the server is running properly.

```
GET /api/health
```

**Example Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "database": "ok",
  "ffmpeg": "ok"
}
```

### Dashboard Statistics

```
GET /api/dashboard/stats
```

### System Information

```
GET /api/system/info
```

### View Logs

```
GET /api/logs
```

---

## Error Handling

When something goes wrong, the API returns an error response:

```json
{
  "detail": "Channel not found",
  "status_code": 404
}
```

### Common Errors

| Code | Meaning | What to Do |
|------|---------|-----------|
| 400 | Bad Request | Check your request format and required fields |
| 404 | Not Found | The item you're looking for doesn't exist |
| 409 | Conflict | The item already exists (duplicate) |
| 422 | Validation Error | Check your data types and values |
| 500 | Server Error | Try again; check server logs if it persists |

---

## Interactive Documentation

When EXStreamTV is running, you can access interactive API documentation:

- **Swagger UI**: [http://localhost:8411/api/docs](http://localhost:8411/api/docs)
  - Try out API calls directly in your browser
  - See all available endpoints
  - View request/response schemas

- **ReDoc**: [http://localhost:8411/api/redoc](http://localhost:8411/api/redoc)
  - Clean, readable documentation
  - Great for reference

---

## Quick Reference

### Most Common Operations

| Task | Method | Endpoint |
|------|--------|----------|
| List channels | GET | `/api/channels` |
| Create channel | POST | `/api/channels` |
| Delete channel | DELETE | `/api/channels/{id}` |
| List playlists | GET | `/api/playlists` |
| Get M3U playlist | GET | `/iptv/channels.m3u` |
| Start stream | GET | `/api/channels/{id}/stream.m3u8` |
| Health check | GET | `/api/health` |

### ErsatzTV-Compatible Features

| Feature | Endpoints |
|---------|-----------|
| Time Blocks | `/api/blocks`, `/api/block-groups` |
| Templates | `/api/templates`, `/api/template-groups` |
| Filler Content | `/api/filler-presets` |
| Bumpers & Station IDs | `/api/deco`, `/api/deco-groups` |
| Multi-Collections | `/api/collections/multi` |
| Scripted Schedules | `/api/scripted/build/*` |
| Build Sessions | `/api/playouts/{id}/build/*` |

---

---

## AI Self-Healing API (NEW in v2.6.0)

The AI Self-Healing system provides autonomous issue detection and resolution.

### Get AI Health Status

```
GET /api/ai/health
```

**Example Response:**
```json
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
```

### Get Channel Health Metrics

```
GET /api/ai/channels/{channel_id}/health
```

**Example Response:**
```json
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
```

### Get Recent Errors

```
GET /api/ai/errors?minutes=60&max_errors=50
```

### Get Active Sessions

```
GET /api/ai/sessions
```

**Example Response:**
```json
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
```

### Trigger Manual Backup

```
POST /api/database/backup
```

**What to send:**
```json
{
  "description": "Manual backup before maintenance",
  "compress": true
}
```

### List Backups

```
GET /api/database/backups
```

### Restore Backup

```
POST /api/database/restore
```

**What to send:**
```json
{
  "backup_path": "backups/exstreamtv_backup_20260131.db.gz",
  "create_safety_backup": true
}
```

---

## Need Help?

- Check the [Quick Start Guide](../guides/QUICK_START.md)
- Read the [System Design](../architecture/SYSTEM_DESIGN.md)
- Read the [Tunarr/dizqueTV Integration](../architecture/TUNARR_DIZQUETV_INTEGRATION.md)
- Use the interactive docs at `/api/docs`
- View streaming logs at `/logs`
