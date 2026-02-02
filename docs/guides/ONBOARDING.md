# Onboarding Guide

This guide walks you through the EXStreamTV first-run setup wizard.

## Table of Contents

- [Overview](#overview)
- [Step 1: Welcome](#step-1-welcome)
- [Step 2: AI Assistant](#step-2-ai-assistant)
- [Step 3: Server Setup](#step-3-server-setup)
- [Step 4: Media Sources](#step-4-media-sources)
- [Step 5: First Channel](#step-5-first-channel)
- [Step 6: Complete](#step-6-complete)
- [Re-running Onboarding](#re-running-onboarding)
- [Skipping Steps](#skipping-steps)

---

## Overview

The onboarding wizard appears when you first launch the EXStreamTV macOS app. It guides you through:

1. Checking dependencies (Python, FFmpeg)
2. Configuring AI assistance
3. Setting up the backend server
4. Connecting media sources
5. Creating your first channel

You can skip optional steps and configure them later in Settings.

---

## Step 1: Welcome

The Welcome step introduces EXStreamTV and checks your system.

### What It Shows

- **App Introduction**: Key features overview
- **Dependency Status**: Checks for Python and FFmpeg

### Dependency Checks

| Dependency | Status | Action Needed |
|------------|--------|---------------|
| Python 3.10+ | Green checkmark | None |
| Python | Red X | Install via Homebrew or python.org |
| FFmpeg | Green checkmark | None |
| FFmpeg | Red X | Install via Homebrew |

### If Dependencies Are Missing

Click **Run Install Script** to automatically install missing dependencies. This runs:

```bash
./scripts/install_macos.sh
```

The script installs:
- Python 3.11 via Homebrew
- FFmpeg with VideoToolbox support
- Python virtual environment and packages

### Moving Forward

Once all dependencies show green checkmarks, click **Next** to continue.

---

## Step 2: AI Assistant

Configure how EXStreamTV uses AI for channel creation and troubleshooting.

### AI Options

| Option | Badge | Description |
|--------|-------|-------------|
| **Cloud AI** | FREE | Uses Groq's cloud servers. Instant setup, requires internet. |
| **Local AI** | - | Runs on your Mac via Ollama. Works offline, uses more RAM. |
| **Hybrid** | - | Cloud primary, local backup. Best of both worlds. |
| **Skip for Now** | - | Configure AI later in Settings. |

### Choosing Cloud AI (Recommended)

1. Select **Cloud AI**
2. Click **Continue**
3. The Groq Setup wizard appears

**Groq Setup:**

1. Click **Open Groq Console** to get your free API key
2. Sign in with Google or GitHub (30 seconds)
3. Create and copy your API key
4. Paste it in the app
5. Click **Validate & Continue**

### Choosing Local AI

1. Select **Local AI**
2. Click **Continue**
3. The Local AI Setup wizard appears

**Local AI Setup:**

1. Your Mac's RAM is detected automatically
2. A model is recommended based on your RAM
3. If Ollama isn't installed, click **Install Ollama**
4. Click **Download Model** to download the recommended model
5. Wait for download to complete
6. Click **Continue**

### Choosing Hybrid

1. Select **Hybrid**
2. Click **Continue**
3. Set up Cloud AI first (Groq)
4. Optionally set up Local AI as fallback

### Skipping AI

1. Select **Skip for Now**
2. Click **Continue**
3. You can configure AI later in **Settings** > **AI** tab

---

## Step 3: Server Setup

Configure the EXStreamTV backend server.

### Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| **Server Port** | 8411 | Port for web UI and API |
| **Data Directory** | ~/Library/Application Support/EXStreamTV | Where data is stored |

### Changing the Port

If port 8411 is in use:

1. Enter a different port (e.g., 9000)
2. Remember this port for accessing the web UI

### Changing Data Directory

1. Click **Change**
2. Select a folder
3. Useful for storing data on external drives

### Starting the Server

1. Click **Start Server**
2. Wait for "Server is running" message
3. The port will show in green

### If Server Fails to Start

- Check that the port isn't in use
- Verify Python path in logs
- Click the error message for details

---

## Step 4: Media Sources

Connect your media libraries to create channel content.

### Available Sources

| Source | Description |
|--------|-------------|
| **Plex** | Connect to Plex Media Server |
| **Jellyfin** | Connect to Jellyfin server |
| **Emby** | Connect to Emby server |
| **Local Folders** | Add folders from your Mac |

### Connecting Plex

1. Click **Connect** next to Plex
2. Enter your Plex server URL (e.g., `http://localhost:32400`)
3. Enter your Plex token
4. Click **Connect**

**Finding Your Plex Token:**

1. Open Plex Web
2. Play any media
3. Click "Get Info" > "View XML"
4. Find `X-Plex-Token=` in the URL

### Connecting Jellyfin/Emby

1. Click **Connect** next to the service
2. Enter server URL
3. Enter API key (from server settings)
4. Click **Connect**

### Adding Local Folders

1. Click **Connect** next to Local Folders
2. Select one or more folders containing videos
3. Click **Open**
4. The folders will be scanned for media

### Skipping This Step

This step is optional. Click **Skip** or **Next** to continue without connecting sources. You can add sources later from the web dashboard.

---

## Step 5: First Channel

Create your first TV channel.

### Creation Options

| Option | Description |
|--------|-------------|
| **AI-Assisted** | AI helps you create a channel based on preferences |
| **Manual Configuration** | Configure everything yourself |
| **Import from M3U** | Import an existing playlist file |

### AI-Assisted Creation

*Requires AI to be configured in Step 2*

1. Click **AI-Assisted**
2. Describe the channel you want (e.g., "80s action movies channel")
3. AI suggests content and schedule
4. Review and approve
5. Channel is created

### Manual Configuration

1. Click **Manual Configuration**
2. Enter channel name and number
3. Add content from connected sources
4. Configure schedule (optional)
5. Click **Create**

### Import from M3U

1. Click **Import from M3U**
2. Select your .m3u or .m3u8 file
3. Review imported channels
4. Click **Import**

### Skipping This Step

Creating a channel is optional. Click **Skip** to proceed. You can create channels from the web dashboard later.

---

## Step 6: Complete

Setup is complete! This step shows a summary of your configuration.

### Summary Display

- **Server**: Port and status
- **AI Assistant**: Provider configured or "Not configured"
- **Media Sources**: Connected services

### Opening the Dashboard

Click **Open Dashboard** to:

1. Close the onboarding wizard
2. Open the web dashboard at `http://localhost:8411`
3. Start using EXStreamTV

### What Happens Next

- The server continues running in the background
- The menu bar icon appears
- You can control everything from the menu bar
- The onboarding won't show again on future launches

---

## Re-running Onboarding

To run the setup wizard again:

### Method 1: Reset Settings

1. Open **Settings** (Cmd+,)
2. Go to **Advanced** tab
3. Click **Reset All Settings**
4. Restart the app

### Method 2: Delete Preferences

```bash
defaults delete com.exstreamtv.EXStreamTVApp
```

Then restart the app.

### Method 3: Re-run Specific Steps

Instead of full reset, configure individual items:

- **AI**: Settings > AI tab
- **Server**: Settings > Server tab
- **Media Sources**: Web dashboard > Libraries
- **Channels**: Web dashboard > Channels

---

## Skipping Steps

### Steps You Can Skip

| Step | Skippable? | Impact |
|------|------------|--------|
| Welcome | No | Must verify dependencies |
| AI Assistant | Yes | AI features won't work until configured |
| Server Setup | No | Must start server to use app |
| Media Sources | Yes | Can add later from web dashboard |
| First Channel | Yes | Can create later from web dashboard |

### Configuring Later

Everything skipped can be configured later:

- **AI**: Settings > AI tab, or reopen onboarding
- **Media Sources**: Web dashboard > Libraries
- **Channels**: Web dashboard > Channels

---

## Troubleshooting

### Wizard Won't Advance

- Ensure required fields are filled
- Check for validation errors (red text)
- For Server step, server must be running

### Can't Install Dependencies

Run the install script manually:

```bash
cd /path/to/EXStreamTV
./scripts/install_macos.sh
```

### API Key Validation Fails

- Check for extra spaces in the key
- Verify you're using the correct provider's key
- Try clicking **Open Groq Console** to get a fresh key

### Server Won't Start

1. Check if port is in use: `lsof -i :8411`
2. Try a different port
3. Check Python installation: `python3 --version`

### Onboarding Appears Every Launch

Ensure you complete the wizard to Step 6. If it keeps appearing:

1. Check write permissions on preferences
2. Look for errors in Console.app
3. Try resetting and completing again

---

## Next Steps

After completing onboarding:

1. [Create more channels](QUICK_START.md#creating-your-first-channel)
2. [Configure AI in detail](AI_SETUP.md)
3. [Enable hardware transcoding](HW_TRANSCODING.md)
4. [Set up schedules](../api/README.md)
