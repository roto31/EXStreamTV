# Channel Creation Guide

A comprehensive guide to creating TV channels in EXStreamTV, from the simplest setup to advanced multi-block scheduled programming.

## Table of Contents

1. [Introduction](#introduction)
2. [Quick Start: Your First Channel in 5 Minutes](#quick-start-your-first-channel-in-5-minutes)
3. [Method 1: Basic Manual Channel](#method-1-basic-manual-channel)
4. [Method 2: AI-Powered Channel Creation](#method-2-ai-powered-channel-creation)
5. [Method 3: Scheduled Channel](#method-3-scheduled-channel)
6. [Method 4: Advanced Multi-Block Channel](#method-4-advanced-multi-block-channel)
7. [Method 5: Import and Customize](#method-5-import-and-customize)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Introduction

### What is a Channel in EXStreamTV?

A channel in EXStreamTV represents a continuous stream of video content, similar to a traditional TV channel. Each channel consists of:

- **Content Source** - Where your media comes from (playlists, collections, or individual items)
- **Schedule** (optional) - Rules for when specific content plays
- **Playout** - The active playback configuration
- **Branding** (optional) - Logos, watermarks, and overlays

### Channel Components

```
Channel
├── Basic Info (name, number, logo, group)
├── Content
│   ├── Playlist (ordered list of items)
│   └── Collection (filtered set of media)
├── Schedule (optional)
│   ├── Time Blocks
│   ├── Recurring Patterns
│   └── Filler/Commercials
├── Playout
│   ├── Mode (continuous, scheduled, loop)
│   └── Anchor Points
└── Deco (optional)
    ├── Watermarks
    └── Bumpers
```

### Choosing the Right Method

| Method | Complexity | Best For |
|--------|------------|----------|
| Quick Start | Beginner | Single playlist, continuous playback |
| Basic Manual | Beginner | Simple channel with custom settings |
| AI-Powered | Intermediate | Complex themed channels, scheduling help |
| Scheduled | Intermediate | Time-based programming |
| Multi-Block | Advanced | Full broadcast-style scheduling |
| Import | Varies | Migration from other platforms |

---

## Quick Start: Your First Channel in 5 Minutes

Get a channel up and running as fast as possible.

![Basic Channel Creation Walkthrough](/docs/screenshots/basic-channel-creation.gif)
*Animated walkthrough of the basic channel creation process*

### Prerequisites

- At least one media source connected (Plex, Jellyfin, or local folder)
- Some media scanned into the system

### Step-by-Step

**Step 1: Navigate to Channels**

Go to **Channels > Manage Channels** in the sidebar.

![Channels Page](/docs/screenshots/nav-channels-list.png)
*The channels management page showing the toolbar with Add Channel and AI Create buttons*

**Step 2: Click Add Channel**

Click the **Add Channel** button in the toolbar. You'll see both "Add Channel" for manual creation and "AI Create" for guided setup.

![Create Channel Dialog](/docs/screenshots/step2-create-dialog-empty.png)
*The Create Channel dialog with empty form fields*

**Step 3: Fill Basic Information**

![Filled Channel Form](/docs/screenshots/step3-create-dialog-filled.png)
*Example: Creating "Classic Movies" channel (101) in the Entertainment group*

- **Channel Number**: Enter a number (e.g., "101")
- **Channel Name**: Give it a name (e.g., "Movies")
- **Group**: Optional category (e.g., "Entertainment")

**Step 4: Select Content**

Under "Content Source," choose:
- **Playlist**: Select an existing playlist, OR
- **Collection**: Choose a collection, OR
- **Quick Setup**: The system will create a playlist for you

**Step 5: Save and Enable**

1. Click **Save** to create the channel
2. Toggle the channel to **Enabled**
3. Your channel is now streaming!

### Test Your Channel

1. Go to **Player** in the sidebar
2. Select your new channel from the dropdown
3. Press play to verify it works

**Congratulations!** You've created your first channel.

---

## Method 1: Basic Manual Channel

For more control over channel settings while keeping things simple.

### When to Use

- You want a single collection or playlist to play continuously
- No complex scheduling needed
- Simple 24/7 playback of similar content

### Step-by-Step Guide

#### 1. Prepare Your Content

Before creating the channel, organize your content:

1. Go to **Content > Playlists** or **Content > Collections**
2. Create a new playlist/collection if needed
3. Add media items to your playlist

**Tip**: Playlists maintain order, collections are more dynamic.

#### 2. Create the Channel

1. Navigate to **Channels > Manage Channels**
2. Click **Add Channel**
3. Fill in the form:

| Field | Description | Example |
|-------|-------------|---------|
| Number | Unique channel number | 201 |
| Name | Display name | Classic Movies |
| Group | Category for organization | Movies |
| Logo | Upload or URL to channel logo | (optional) |
| Enabled | Whether channel is active | On |

#### 3. Configure Content Source

- **Playlist Mode**: Choose an existing playlist for ordered playback
- **Collection Mode**: Select a collection for dynamic content
- **Playback Order**: Chronological, random, or shuffle

#### 4. Set Playback Options

- **Continuous**: Plays forever, looping when content ends
- **Keep Position**: Remember where viewers left off
- **Episode Tracking**: For TV shows, track episode progression

#### 5. Save and Test

1. Click **Save**
2. Enable the channel if not already enabled
3. Go to **Player** and test playback

### Best Practices for Basic Channels

- **Name clearly**: Use descriptive names like "80s Action Movies"
- **Group logically**: Use groups to organize similar channels
- **Add a logo**: Channels with logos look more professional
- **Test playback**: Always verify your channel works before sharing

---

## Method 2: AI-Powered Channel Creation

Use the AI Channel Creator for guided setup with expert personas specialized in different content types.

![AI Channel Conversation](/docs/screenshots/ai-channel-conversation.gif)
*Animated preview of the AI Channel Creator interface*

### When to Use

- You want guidance on channel setup
- Creating themed channels (e.g., "1970s Nostalgia")
- Need help with scheduling and commercial breaks
- Want best practices built-in

### Accessing AI Create

1. Go to **Channels > AI Create Channel**, OR
2. Click **AI Create** in the channels toolbar, OR
3. Use the **AI Create** quick action from the dashboard

![AI Channel Creator](/docs/screenshots/ai-channel-creator.png)
*The AI Channel Creator with expert persona selection*

![AI Channel Personas](/docs/screenshots/ai-channel-personas.png)
*Choose from 6 expert personas, each specialized in different content types*

### Available Expert Personas

Choose from specialized AI experts for different content types:

| Persona | Specialty | Best For |
|---------|-----------|----------|
| Max Sterling | TV Programming Executive | Classic TV, scheduling, dayparts |
| Howard Kowalski | Sports Savant | Sports, classic games, documentaries |
| Steve Nakamura | Tech Savant | Technology, Apple, computing |
| Vincent & Clara | Movie Critics | Films, film history, directors |
| Professor Chen | Kids Programming | Children, Disney, animation |
| Dr. Eleanor Marsh | PBS Expert | Documentary, educational, PBS |

### How It Works

You'll chat with your selected expert, who will:

- Asks questions about your channel concept
- Suggests scheduling approaches
- Recommends content organization
- Handles technical configuration

### Example Conversation

**You**: "I want a 1970s and 1980s TV channel with commercials"

**Max**: "Ah, the golden age of television! Let me ask you a few questions:

1. What's your content library situation? Do you have TV shows from Plex?
2. Are you looking for a 24-hour schedule or specific dayparts?
3. Should we include Saturday morning cartoons?
4. Any particular genres you want to emphasize?"

**You**: "I have Plex with classic TV shows. I want 24-hour with Saturday cartoons. Primetime should be dramas and comedies."

**Max**: "Perfect! Here's how I'd structure this..."

### The AI Process

1. **Describe Your Vision**: Tell the AI what kind of channel you want
2. **Answer Questions**: The AI asks clarifying questions
3. **Review Specification**: See a preview of the channel structure
4. **Create Channel**: Let the AI build everything for you

The right panel shows a live preview of your channel specification as you chat, updating in real-time as Max gathers information about your preferences.

### AI-Created Components

The AI can automatically create:

- The channel with proper settings
- Smart collections for content filtering
- Schedules with daypart assignments
- Filler presets for commercials
- Playout configuration

### Tips for AI Channel Creation

- **Be specific about eras**: "1970s-1980s" works better than "old"
- **Describe your library**: Tell the AI what content you have
- **Mention preferences**: Commercials, start times, special blocks
- **Ask for suggestions**: The AI knows classic TV programming patterns

---

## Method 3: Scheduled Channel

Create channels with time-based programming.

![Schedule Creation](/docs/screenshots/schedule-creation.gif)
*Overview of the scheduling interface*

### When to Use

- Different content at different times of day
- Specific shows at specific times
- Weekly programming patterns
- More broadcast-like experience

### Understanding Schedules

A schedule defines WHEN content plays:

```
Schedule
├── Monday-Friday
│   ├── 6:00 AM - Morning News
│   ├── 9:00 AM - Talk Shows
│   ├── 12:00 PM - Soap Operas
│   ├── 6:00 PM - Evening News
│   └── 8:00 PM - Primetime Dramas
└── Saturday
    ├── 8:00 AM - Cartoons
    └── 8:00 PM - Movies
```

### Step-by-Step

#### 1. Create a Schedule

1. Go to **Scheduling > Schedules**
2. Click **Add Schedule**
3. Give it a descriptive name (e.g., "Classic TV Daily Schedule")

![Schedules Page](/docs/screenshots/schedules-page.png)
*The Schedules management page with Add Schedule button*

![Create Schedule Dialog](/docs/screenshots/schedule-create.png)
*The Create Schedule dialog with options for multi-part episodes and shuffle settings*

#### 2. Add Schedule Items

For each time slot:

1. Click **Add Item**
2. Set the **Start Time**
3. Choose the **Content Source** (collection/playlist)
4. Set **Duration** or let it auto-calculate
5. Configure playback options

#### 3. Configure Recurring Patterns

- **Daily**: Same schedule every day
- **Weekdays**: Monday-Friday only
- **Weekends**: Saturday-Sunday only
- **Specific Days**: Choose individual days

#### 4. Create the Channel

1. Go to **Channels > Manage Channels**
2. Create a new channel
3. Under Playout settings, select **Scheduled Mode**
4. Choose your created schedule

#### 5. Create a Playout

1. Go to **Scheduling > Playouts**
2. Click **Create Playout**
3. Link your channel and schedule
4. Set to **Active**

### Schedule Tips

- **Plan on paper first**: Sketch your schedule before building
- **Use collections**: Easier to manage than individual items
- **Buffer time**: Add a few minutes between shows for flexibility
- **Test transitions**: Make sure shows switch correctly

---

## Method 4: Advanced Multi-Block Channel

Full broadcast-style channel with blocks, filler, and branding.

### When to Use

- Replicating traditional TV experience
- Complex programming with commercials
- Multiple themed blocks per day
- Professional presentation with branding

### Architecture Overview

```
Channel: "Retro TV"
├── Schedule: "Retro TV Master Schedule"
│   ├── Morning Block
│   │   ├── 6:00 - Wake Up Cartoons
│   │   └── Commercial Break (Filler Preset A)
│   ├── Daytime Block
│   │   ├── 9:00 - Game Shows
│   │   ├── 12:00 - Soaps
│   │   └── Commercial Breaks (Filler Preset B)
│   └── Primetime Block
│       ├── 8:00 - Drama Hour
│       ├── 9:00 - Comedy Block
│       └── Commercial Breaks (Filler Preset C)
├── Filler Presets
│   ├── Preset A: Short breaks (30 sec)
│   ├── Preset B: Standard breaks (2 min)
│   └── Preset C: Long breaks (3 min)
└── Deco
    ├── Channel Watermark (logo)
    └── Bumpers (station ID)
```

### Building It Step by Step

#### Phase 1: Organize Your Content

1. **Create Collections** by genre and era:
   - "70s-80s Cartoons"
   - "Classic Game Shows"
   - "Daytime Soaps"
   - "Primetime Dramas"
   - "Sitcoms"

2. **Create a Filler Collection** for commercials:
   - Archive.org Prelinger collection
   - Custom bumpers/promos

#### Phase 2: Create Programming Blocks

1. Go to **Scheduling > Blocks**
2. Create blocks for each daypart:

![Blocks Page](/docs/screenshots/blocks-page.png)
*The Blocks management page for creating time-based programming blocks*

**Morning Cartoon Block**
- Name: "Saturday Morning Cartoons"
- Duration: 4 hours
- Source: "70s-80s Cartoons" collection
- Shuffle: Yes

**Primetime Drama Block**
- Name: "Drama Hour"
- Duration: 1 hour
- Source: "Primetime Dramas" collection
- Shuffle: No (chronological)

#### Phase 3: Configure Filler Presets

1. Go to **Scheduling > Filler Presets**
2. Create presets for different contexts:

![Filler Presets Page](/docs/screenshots/filler-presets.png)
*The Filler Presets page for configuring commercial breaks and filler content*

**Standard Commercial Break**
- Duration: 2 minutes
- Frequency: Every 15 minutes
- Source: Filler collection
- Shuffle: Yes

#### Phase 4: Build the Schedule

1. Go to **Scheduling > Templates** (optional: create reusable template)

![Templates Page](/docs/screenshots/templates-page.png)
*The Templates page for creating reusable schedule patterns*

2. Go to **Scheduling > Schedules**
3. Create master schedule
4. Add blocks and filler:

```
6:00 AM - Morning Block
  → Insert Filler Preset: Short Breaks
9:00 AM - Daytime Block
  → Insert Filler Preset: Standard Breaks
8:00 PM - Primetime Block
  → Insert Filler Preset: Long Breaks
11:00 PM - Late Night
  → Movies with minimal breaks
```

#### Phase 5: Add Branding (Deco)

1. Go to **Scheduling > Deco**

![Deco Page](/docs/screenshots/deco-page.png)
*The Deco page for bumpers, station IDs, and promotional content*

2. Create channel watermark:
   - Upload logo image
   - Position: Bottom-right
   - Opacity: 70%

3. Create station ID bumpers:
   - 5-second clips between shows
   - "You're watching Retro TV"

#### Phase 6: Connect Everything

1. Create the channel at **Channels > Manage Channels**
2. Create playout at **Scheduling > Playouts**:
   - Link channel to schedule
   - Enable filler presets
   - Enable deco

#### Phase 7: Test Thoroughly

1. Use **Diagnostics > Test Stream**
2. Verify:
   - Content plays in correct order
   - Commercial breaks insert properly
   - Watermark displays correctly
   - Bumpers play between shows

### Advanced Tips

- **Use templates**: Create schedule templates for consistency
- **Time alignment**: Set shows to start on the hour or half-hour
- **Vary filler**: Mix commercial lengths for authenticity
- **Preview schedule**: Check the visual timeline before going live

---

## Method 5: Import and Customize

Migrate from other platforms or M3U sources.

![Import Channels Page](/docs/screenshots/import-channels.png)
*The Import Channels page for importing from YAML configuration files*

### Importing from ErsatzTV

1. Go to **Channels > Import Channels**
2. Select **ErsatzTV** as source
3. Provide your ErsatzTV database or export file
4. Map channels to local media sources
5. Review and import

### Importing from M3U

1. Go to **Channels > Import M3U**
2. Paste your M3U playlist URL or content
3. Configure import options:

![Import M3U Page](/docs/screenshots/import-m3u.png)
*The Import M3U page for importing from M3U playlists or the curated stream library*
   - Channel number assignment
   - Group mapping
   - Logo handling
4. Review channels before import
5. Click **Import**

### Post-Import Customization

After importing, you may want to:

- Update channel logos
- Reassign content sources to local media
- Adjust channel numbers
- Modify playback settings

---

## Best Practices

### Content Organization

1. **Use descriptive names**: "80s Action Movies" not "Movies 1"
2. **Create smart collections**: Filter by genre, year, rating
3. **Separate content types**: Don't mix movies and TV episodes
4. **Maintain metadata**: Good metadata = better filtering

### Schedule Design

1. **Know your dayparts**: 
   - Morning (6-9 AM): Light content
   - Daytime (9 AM-5 PM): Talk shows, soaps
   - Early fringe (5-8 PM): Transition content
   - Primetime (8-11 PM): Best content
   - Late night (11 PM+): Movies, adult content

2. **Lead-in strategy**: Put popular shows before new content
3. **Consistent timing**: Start shows at predictable times
4. **Genre flow**: Similar content should flow together

### Commercial Breaks

1. **Period-appropriate**: Match commercials to content era
2. **Varied length**: 30 seconds to 3 minutes
3. **Natural breaks**: Insert at logical story breaks
4. **Don't overdo it**: 8-12 minutes per hour maximum

### Performance

1. **Test before publishing**: Always verify playback
2. **Monitor resources**: Watch CPU/memory during transcoding
3. **Use hardware acceleration**: Enable GPU encoding if available
4. **Optimize source files**: Pre-transcode if possible

### Channel Maintenance

1. **Refresh content**: Update collections regularly
2. **Monitor playback**: Check logs for errors
3. **Update schedules**: Seasonal or holiday changes
4. **Backup configuration**: Export settings regularly

---

## Troubleshooting

### Channel Not Playing

**Symptoms**: Black screen, buffering, or error message

**Check**:
1. Is the channel enabled?
2. Is the playout active?
3. Does the content source have items?
4. Are media files accessible?

**Fix**:
- Enable channel and playout
- Verify playlist/collection has content
- Check media source connectivity
- Review streaming logs for errors

### Content Not Appearing

**Symptoms**: Empty playlist, missing items

**Check**:
1. Is the media source connected?
2. Has the library been scanned?
3. Are collection filters correct?

**Fix**:
- Refresh media source
- Rescan libraries
- Adjust collection filter criteria

### Schedule Not Following

**Symptoms**: Wrong content at wrong times

**Check**:
1. Is the schedule linked to the channel?
2. Are schedule items correctly configured?
3. Is the time zone correct?

**Fix**:
- Verify playout connects schedule to channel
- Check schedule item times
- Verify server time zone setting

### AI Not Responding

**Symptoms**: AI Channel Creator not working

**Check**:
1. Is Ollama installed and running?
2. Is the AI model downloaded?
3. Check Diagnostics > AI Troubleshooting

**Fix**:
- Install Ollama following the guide
- Download required AI model
- Check Ollama connection in settings

### Using AI Troubleshooting

For persistent issues:

1. Go to **Diagnostics > AI Troubleshooting**
2. Describe your problem
3. Include relevant error messages
4. The AI will analyze and suggest fixes

---

## Next Steps

After creating your first channels:

1. **Set up HDHomeRun** - Share channels with TV apps
2. **Configure EPG** - Electronic program guide for clients
3. **Add more sources** - Connect additional media libraries
4. **Explore scheduling** - Try more complex programming

---

*Last updated: January 2026*
