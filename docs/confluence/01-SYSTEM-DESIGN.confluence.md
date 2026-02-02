{info:title=EXStreamTV System Design}
Version 2.6.0 | Last Updated: 2026-01-31
{info}

h1. EXStreamTV System Design

----

h2. Overview

EXStreamTV is a unified IPTV streaming platform that combines:
* *StreamTV*: Python/FastAPI web application with AI agent
* *ErsatzTV*: Advanced scheduling, transcoding, and local media features
* *Tunarr*: Session management, time slot scheduling, database backup
* *dizqueTV*: Stream throttling, error screens

This document describes the system architecture and design decisions.

----

h2. Architecture Diagram

{mermaid}
flowchart TB
    subgraph Platform[EXStreamTV Platform]
        subgraph WebUI_Layer[WebUI - Jinja2 Templates]
            Channels_UI[Channels]
            Playlists_UI[Playlists]
            Schedules_UI[Schedules]
            Libraries_UI[Libraries]
            Settings_UI[Settings]
        end
        
        subgraph FastAPI_Layer[FastAPI Application]
            REST[REST API]
            IPTV[IPTV M3U/EPG]
            HDHomeRun_API[HDHomeRun Emulator]
            SSDP[SSDP Discovery]
        end
        
        subgraph Core_Services[Core Services]
            CM[Channel Manager]
            Playout[Playout Engine]
            Scanner[Media Scanner]
            AI[AI Agent]
        end
        
        subgraph FFmpeg_Pipeline[FFmpeg Pipeline]
            Decoders[Decoders HW/SW]
            Filters[Filters V/A]
            Encoders[Encoders HW/SW]
            Formats[Formats TS/HLS]
            Profiles[Profiles]
        end
        
        subgraph Data_Layer[Data Layer]
            DB[(SQLite/PostgreSQL)]
            MediaSources[Media Sources]
        end
    end
    
    subgraph Clients[Clients]
        Plex[Plex Client]
        Jellyfin_Client[Jellyfin Client]
        IPTV_Player[IPTV Player]
    end
    
    WebUI_Layer --> FastAPI_Layer
    FastAPI_Layer --> Core_Services
    Core_Services --> FFmpeg_Pipeline
    Core_Services --> Data_Layer
    
    Platform --> Clients
{mermaid}

----

h2. Core Components

h3. 1. FastAPI Application

{code:title=exstreamtv/main.py}
The main application entry point using FastAPI:

- Lifespan Management: Async startup/shutdown for database, channel manager
- Router Registration: REST API, IPTV, HDHomeRun, WebUI routes
- Static Files: CSS, JavaScript, images
- Templates: Jinja2 template rendering
{code}

h3. 2. Channel Manager

{code:title=exstreamtv/streaming/channel_manager.py}
Manages continuous channel streaming (ErsatzTV-style):

- Background Streams: Each channel runs continuously in background
- Client Connections: Multiple clients can connect to same stream
- Seamless Transitions: Smooth switching between playlist items
- Buffer Management: 2MB buffer with 64KB read chunks
{code}

h3. 3. Playout Engine

{code:title=exstreamtv/scheduling/engine/}
Advanced scheduling system ported from ErsatzTV:

- Schedule Modes: Flood, Duration, Multiple, One
- Collection Enumerators: Chronological, Shuffled, Random
- Block Scheduling: Time-based programming blocks
- Filler System: Pre-roll, mid-roll, post-roll, fallback
{code}

h3. 4. FFmpeg Pipeline

{code:title=exstreamtv/ffmpeg/}
Hardware-accelerated transcoding pipeline:

- Hardware Detection: Auto-detect VideoToolbox, NVENC, QSV, VAAPI, AMF
- Encoder Selection: Choose optimal encoder based on capabilities
- Filter Chains: Scale, pad, overlay, deinterlace, watermark
- Profile System: Saved encoding presets
{code}

h3. 5. Media Scanner

{code:title=exstreamtv/media/scanner/}
Local media library management:

- Library Sources: Plex, Jellyfin, Emby, local folders
- Metadata Providers: TVDB, TMDB, local NFO files
- Collection Building: Automatic show/season/episode grouping
- Change Detection: Efficient incremental scanning
{code}

h3. 6. AI Agent

{code:title=exstreamtv/ai_agent/}
Intelligent log analysis and error detection:

- Pattern Matching: Detect FFmpeg, network, auth errors
- Fix Suggestions: Recommend solutions for common issues
- Auto-Fix Mode: Optional automatic remediation
- Learning: Improve suggestions based on outcomes
{code}

----

h2. New Components in v2.6.0

{panel:title=Tunarr/dizqueTV Integration|borderStyle=solid|borderColor=#4CAF50}
The following components were added in v2.6.0 from the Tunarr/dizqueTV integration.
{panel}

h3. 7. Session Manager (NEW)

{code:title=exstreamtv/streaming/session_manager.py}
Tunarr-style client session tracking:

- StreamSession: Individual client connection tracking
- SessionManager: Centralized session lifecycle management
- Health Monitoring: Error counting, restart tracking
- Idle Cleanup: Automatic cleanup of inactive sessions
{code}

h3. 8. Stream Throttler (NEW)

{code:title=exstreamtv/streaming/throttler.py}
dizqueTV-style rate limiting for MPEG-TS delivery:

- Rate Limiting: Match target bitrate to prevent buffer overruns
- Multiple Modes: realtime, burst, adaptive, disabled
- Keepalive: Packet support during stream stalls
{code}

h3. 9. Error Screen Generator (NEW)

{code:title=exstreamtv/streaming/error_screens.py}
dizqueTV-style fallback streams during failures:

- Visual Modes: text, static, test_pattern, slate
- Audio Modes: silent, sine_wave, white_noise, beep
- FFmpeg Integration: Generate MPEG-TS error streams
{code}

h3. 10. AI Self-Healing System (NEW)

{code:title=exstreamtv/ai_agent/}
Enhanced AI capabilities for autonomous issue resolution:

- UnifiedLogCollector: Multi-source log aggregation with real-time streaming
- FFmpegAIMonitor: Intelligent FFmpeg monitoring with error classification
- PatternDetector: ML-based pattern detection and failure prediction
- AutoResolver: Autonomous issue resolution with zero-downtime fixes
{code}

----

h2. Data Models

h3. Channel

{code:language=python}
class Channel:
    id: int
    number: int
    name: str
    logo_url: str
    streaming_mode: str  # "iptv" | "hdhomerun" | "both"
    ffmpeg_profile_id: int
    fallback_filler_id: int
    playouts: List[Playout]
{code}

h3. Playout (ErsatzTV-compatible)

{code:language=python}
class Playout:
    id: int
    channel_id: int
    program_schedule_id: int
    anchor: PlayoutAnchor
    items: List[PlayoutItem]
{code}

h3. PlayoutItem

{code:language=python}
class PlayoutItem:
    id: int
    playout_id: int
    media_item_id: int
    start_time: datetime
    finish_time: datetime
    in_point: timedelta
    out_point: timedelta
    filler_kind: str
{code}

----

h2. Streaming Flow

h3. 1. IPTV Request Flow (v2.6.0 Enhanced)

{mermaid}
flowchart LR
    Client[Client Request]
    SM[SessionManager]
    CM[ChannelManager]
    ST[StreamThrottler]
    FFmpeg[FFmpeg Pipeline]
    Stream[MPEG-TS Stream]
    
    Client --> SM
    SM --> CM
    CM --> FFmpeg
    FFmpeg --> ST
    ST --> Stream
    Stream --> Client
{mermaid}

{noformat}
Client Request → SessionManager → Channel Manager → FFmpeg Pipeline → Throttler → MPEG-TS Stream
{noformat}

h3. 2. HDHomeRun Flow

{noformat}
Plex/Jellyfin → SSDP Discovery → HDHomeRun API → Channel Manager → Stream
{noformat}

h3. 3. Playout Flow (v2.6.0 Enhanced)

{mermaid}
flowchart LR
    Schedule[Schedule Timer]
    TSS[TimeSlotScheduler]
    BS[BalanceScheduler]
    Media[Media Selection]
    SSP[SubtitlePicker]
    ASP[AudioPicker]
    FFmpeg[FFmpeg]
    Stream[Channel Stream]
    
    Schedule --> TSS
    Schedule --> BS
    TSS --> Media
    BS --> Media
    Media --> SSP
    Media --> ASP
    SSP --> FFmpeg
    ASP --> FFmpeg
    FFmpeg --> Stream
{mermaid}

h3. 4. AI Self-Healing Flow (NEW v2.6.0)

{mermaid}
flowchart TB
    Logs[Application Logs]
    FFmpegErr[FFmpeg Stderr]
    
    ULC[UnifiedLogCollector]
    FFM[FFmpegAIMonitor]
    PD[PatternDetector]
    AR[AutoResolver]
    
    ESG[ErrorScreenGenerator]
    CM[ChannelManager]
    
    Logs --> ULC
    FFmpegErr --> FFM
    ULC --> PD
    FFM --> PD
    PD --> AR
    AR --> ESG
    AR --> CM
{mermaid}

----

h2. Configuration

Configuration is managed via config.yaml with environment variable overrides:

{code:language=yaml|title=config.yaml}
server:
  host: "0.0.0.0"
  port: 8411

ffmpeg:
  hardware_acceleration:
    preferred: "auto"  # auto, nvenc, qsv, vaapi, videotoolbox

libraries:
  plex:
    enabled: true
    url: "http://localhost:32400"
    token: "xxx"

# NEW in v2.6.0
session_manager:
  max_sessions_per_channel: 50
  idle_timeout_seconds: 300

stream_throttler:
  enabled: true
  target_bitrate_bps: 4000000
  mode: "realtime"

ai_auto_heal:
  enabled: true
  auto_resolve_enabled: true
{code}

Environment variables use EXSTREAMTV_ prefix:
{code}
EXSTREAMTV_PORT=8411
EXSTREAMTV_PLEX_TOKEN=xxx
{code}

----

h2. Security Considerations

# *API Authentication*: Optional password protection
# *Credential Storage*: Secure keyring for tokens
# *Input Validation*: Pydantic models for all inputs
# *Rate Limiting*: slowapi for API rate limiting

----

h2. Deployment Options

# *Direct Install*: ./install_macos.sh
# *Docker*: docker-compose up
# *macOS App*: EXStreamTVApp.app (menu bar)
# *Kubernetes*: Helm chart in containers/kubernetes/

----

h2. Version History

||Version||Date||Changes||
|1.0.0|2026-01-14|Initial project structure|
|1.0.1|2026-01-14|Config system, database foundation|
|2.0.0|2026-01-14|Complete platform with all integrations|
|2.5.0|2026-01-17|AI Channel Creator, Block Scheduling|
|2.6.0|2026-01-31|Tunarr/dizqueTV integration, AI self-healing|

----

h2. Related Documentation

* [BUILD_PROGRESS|EXStreamTV:Build Progress] - Current development status
* [TUNARR_DIZQUETV_INTEGRATION|EXStreamTV:Tunarr Integration] - v2.6.0 integration details
* [API Documentation|EXStreamTV:API Reference] - REST API reference
