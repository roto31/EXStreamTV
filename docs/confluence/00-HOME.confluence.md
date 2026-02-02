{info:title=EXStreamTV Documentation}
Version 2.6.0 | Last Updated: 2026-01-31
{info}

h1. EXStreamTV Documentation

Welcome to the EXStreamTV documentation. This guide will help you set up, configure, and use EXStreamTV for your IPTV streaming needs.

----

h2. Quick Links

||Document||Description||
|[Quick Start|EXStreamTV:Quick Start]|Get started in 10 minutes|
|[Installation|EXStreamTV:Installation]|Complete installation guide|
|[API Reference|EXStreamTV:API Reference]|REST API documentation|
|[System Design|EXStreamTV:System Design]|Architecture overview|

----

h2. Documentation Structure

{code:title=Documentation Structure}
docs/
├── README.md                    # This file
├── VERSION                      # Documentation version
├── CHANGELOG.md                 # Documentation changes
│
├── guides/                      # User Guides
│   ├── QUICK_START.md          
│   ├── INSTALLATION.md         
│   ├── AI_SETUP.md             
│   ├── STREAMING_STABILITY.md  # NEW in v2.6.0
│   └── ADVANCED_SCHEDULING.md  # NEW in v2.6.0
│
├── api/                         # API Documentation
│   └── README.md               
│
├── architecture/                # Architecture Documentation
│   ├── SYSTEM_DESIGN.md        
│   └── TUNARR_DIZQUETV_INTEGRATION.md # NEW in v2.6.0
│
└── BUILD_PROGRESS.md           # Build tracking
{code}

----

h2. Getting Started

h3. New Users

# *[Installation Guide|EXStreamTV:Installation]* - Install EXStreamTV on your system
# *[Quick Start|EXStreamTV:Quick Start]* - Create your first channel in 10 minutes
# *[AI Setup|EXStreamTV:AI Setup]* - Configure AI for smart channel creation

h3. Intermediate Users

# *[Channel Creation Guide|EXStreamTV:Channel Creation]* - Advanced channel options
# *[Local Media Setup|EXStreamTV:Local Media]* - Add your own media libraries
# *[Hardware Transcoding|EXStreamTV:Hardware Transcoding]* - GPU acceleration setup

h3. Advanced Users

# *[Advanced Scheduling|EXStreamTV:Advanced Scheduling]* - Time slots and balance scheduling
# *[Streaming Stability|EXStreamTV:Streaming Stability]* - Session management and throttling
# *[API Reference|EXStreamTV:API Reference]* - Build integrations

----

h2. New in v2.6.0

{panel:title=Tunarr/dizqueTV Integration|borderStyle=solid|borderColor=#4CAF50}
EXStreamTV v2.6.0 introduces major enhancements from the Tunarr/dizqueTV integration.
{panel}

h3. Streaming Stability

{mermaid}
flowchart LR
    Client[Client]
    SM[SessionManager]
    ST[StreamThrottler]
    ESG[ErrorScreenGenerator]
    
    Client --> SM
    SM --> ST
    ST -.-> ESG
    ESG -.-> Client
{mermaid}

* *Session Management* - Track and manage client connections
* *Stream Throttling* - Prevent buffer overruns
* *Error Screens* - Graceful fallback during failures

{tip}See [Streaming Stability Guide|EXStreamTV:Streaming Stability] for details.{tip}

h3. Advanced Scheduling

{mermaid}
flowchart LR
    Channel[Channel]
    TSS[TimeSlotScheduler]
    BS[BalanceScheduler]
    Content[Content]
    
    Channel --> TSS
    Channel --> BS
    TSS --> Content
    BS --> Content
{mermaid}

* *Time Slot Scheduling* - Time-of-day programming blocks
* *Balance Scheduling* - Weight-based content distribution

{tip}See [Advanced Scheduling Guide|EXStreamTV:Advanced Scheduling] for details.{tip}

h3. AI Self-Healing

{mermaid}
flowchart LR
    Logs[Logs]
    Collector[LogCollector]
    Detector[PatternDetector]
    Resolver[AutoResolver]
    
    Logs --> Collector
    Collector --> Detector
    Detector --> Resolver
{mermaid}

* *Unified Log Collector* - Multi-source log aggregation
* *FFmpeg AI Monitor* - Intelligent process monitoring
* *Pattern Detector* - ML-based issue detection
* *Auto Resolver* - Autonomous issue resolution

{tip}See [AI Setup Guide|EXStreamTV:AI Setup] for details.{tip}

----

h2. Architecture Overview

{mermaid}
flowchart TB
    subgraph Client_Layer[Client Layer]
        Clients[IPTV Clients]
    end
    
    subgraph Application_Layer[Application Layer]
        WebUI[WebUI]
        API[REST API]
        HDHomeRun[HDHomeRun Emulator]
    end
    
    subgraph Streaming_Layer[Streaming Layer]
        SM[SessionManager]
        CM[ChannelManager]
        ST[StreamThrottler]
    end
    
    subgraph Scheduling_Layer[Scheduling Layer]
        TSS[TimeSlotScheduler]
        BS[BalanceScheduler]
    end
    
    subgraph Media_Layer[Media Layer]
        SSP[SubtitlePicker]
        ASP[AudioPicker]
        FFmpeg[FFmpeg Pipeline]
    end
    
    subgraph AI_Layer[AI Layer]
        ULC[UnifiedLogCollector]
        FFM[FFmpegAIMonitor]
        PD[PatternDetector]
        AR[AutoResolver]
    end
    
    subgraph Data_Layer[Data Layer]
        DCM[DatabaseConnectionManager]
        DBM[DatabaseBackupManager]
        DB[(Database)]
    end
    
    Clients --> WebUI
    Clients --> API
    Clients --> HDHomeRun
    
    API --> SM
    SM --> CM
    CM --> ST
    CM --> TSS
    CM --> BS
    
    TSS --> SSP
    BS --> SSP
    SSP --> FFmpeg
    ASP --> FFmpeg
    
    FFmpeg --> ULC
    ULC --> PD
    FFM --> PD
    PD --> AR
    AR --> CM
    
    CM --> DCM
    DCM --> DB
    DBM --> DB
{mermaid}

{tip}See [System Design|EXStreamTV:System Design] and [Tunarr/dizqueTV Integration|EXStreamTV:Tunarr Integration] for full details.{tip}

----

h2. API Overview

||Category||Endpoints||Description||
|Channels|/api/channels|Channel CRUD, filler, deco|
|Playlists|/api/playlists|Playlist management|
|Schedules|/api/schedules|Schedule configuration|
|Playouts|/api/playouts|Playout control|
|Blocks|/api/blocks|Time-based blocks|
|Templates|/api/templates|Reusable schedules|
|AI|/api/ai|AI self-healing, health|
|System|/api/health|System monitoring|

{tip}See [Complete API Reference|EXStreamTV:API Reference] for full documentation.{tip}

----

h2. Component Versions

||Component||Version||Last Modified||
|backend_core|2.6.0|2026-01-31|
|streaming|2.6.0|2026-01-31|
|database|2.6.0|2026-01-31|
|ai_agent|2.6.0|2026-01-31|
|scheduling|2.6.0|2026-01-31|
|ffmpeg|2.6.0|2026-01-31|
|docs|2.6.0|2026-01-31|

----

h2. Support

* *GitHub Issues*: Report bugs and request features
* *Documentation*: This documentation site
* *Logs*: Check Settings > Logs for troubleshooting

----

h2. Related Resources

* [CHANGELOG|EXStreamTV:Changelog] - Version history
* [CONTRIBUTING|EXStreamTV:Contributing] - Contribution guidelines
* [LICENSE|EXStreamTV:License] - MIT license
