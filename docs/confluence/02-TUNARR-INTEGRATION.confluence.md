{info:title=Tunarr/dizqueTV Integration Architecture}
Version 2.6.0 | Last Updated: 2026-01-31 | Status: Complete
{info}

h1. Tunarr/dizqueTV Integration Architecture

----

h2. Executive Summary

This document describes the comprehensive integration of proven patterns and components from *Tunarr* (TypeScript IPTV server) and *dizqueTV* (NodeJS streaming platform) into EXStreamTV. The integration enhances platform stability, streaming reliability, and introduces AI-powered self-healing capabilities.

----

h2. Integration Overview

{mermaid}
graph TB
    subgraph EXStreamTV_v260[EXStreamTV v2.6.0]
        subgraph Phase1[Phase 1: Stability]
            DCM[DatabaseConnectionManager]
            SM[SessionManager]
            ST[StreamThrottler]
        end
        
        subgraph Phase2[Phase 2: Error Handling]
            ESG[ErrorScreenGenerator]
        end
        
        subgraph Phase3[Phase 3: Scheduling]
            TSS[TimeSlotScheduler]
            BS[BalanceScheduler]
        end
        
        subgraph Phase4[Phase 4: Media Pipeline]
            SSP[SubtitleStreamPicker]
            ASP[AudioStreamPicker]
        end
        
        subgraph Phase5[Phase 5: Infrastructure]
            DBM[DatabaseBackupManager]
        end
        
        subgraph Phase6[Phase 6: AI Self-Healing]
            ULC[UnifiedLogCollector]
            FFM[FFmpegAIMonitor]
            PD[PatternDetector]
            AR[AutoResolver]
        end
    end
    
    subgraph Source_Projects[Source Projects]
        Tunarr[Tunarr TypeScript]
        dizqueTV[dizqueTV NodeJS]
    end
    
    Tunarr --> DCM
    Tunarr --> SM
    Tunarr --> TSS
    Tunarr --> BS
    Tunarr --> SSP
    Tunarr --> ASP
    Tunarr --> DBM
    
    dizqueTV --> ST
    dizqueTV --> ESG
{mermaid}

{panel:title=Legend|borderStyle=solid}
* (/) *Green*: Tunarr-sourced components
* (/) *Blue*: dizqueTV-sourced components
* (/) *Purple*: EXStreamTV AI enhancements
{panel}

----

h2. Phase 1: Critical Stability Fixes

h3. 1.1 Database Connection Manager

*Source:* Tunarr {{server/src/dao/connectionManager.ts}}
*Target:* {{exstreamtv/database/connection.py}}

{mermaid}
flowchart TB
    subgraph Connection_Pool[Connection Pool Management]
        Config[Channel Count Config]
        Calculator[Pool Size Calculator]
        Engine[SQLAlchemy Engine]
        Pool[Connection Pool]
        Sessions[Async Sessions]
    end
    
    subgraph Monitoring[Monitoring]
        Events[Pool Event Listeners]
        Metrics[ConnectionMetrics]
        Health[Health Check]
    end
    
    Config --> Calculator
    Calculator -->|channels x 2.5 + 10| Engine
    Engine --> Pool
    Pool --> Sessions
    
    Pool --> Events
    Events --> Metrics
    Metrics --> Health
{mermaid}

*Key Features:*

||Feature||Description||
|Dynamic Pool Sizing|Pool size = (channel_count × 2.5) + BASE_POOL_SIZE|
|Pool Event Monitoring|Tracks connections created, checked in/out, invalidated, recycled|
|Health Checks|Latency measurement and pool saturation metrics|
|Auto-Resize|Adjusts pool size when channel count changes|

*Pool Size Formula:*
{code}
optimal_pool_size = max(BASE_POOL_SIZE, min(calculated, MAX_POOL_SIZE))
where calculated = int(channel_count * CONNECTIONS_PER_CHANNEL) + BASE_POOL_SIZE

Constants:
- BASE_POOL_SIZE = 10
- MAX_POOL_SIZE = 100
- CONNECTIONS_PER_CHANNEL = 2.5
{code}

h3. 1.2 Session Manager

*Source:* Tunarr {{server/src/stream/SessionManager.ts}}
*Target:* {{exstreamtv/streaming/session_manager.py}}

{mermaid}
flowchart LR
    subgraph Client_Connections[Client Connections]
        C1[Client 1]
        C2[Client 2]
        C3[Client 3]
    end
    
    subgraph Session_Manager[Session Manager]
        SM[SessionManager]
        SS1[StreamSession]
        SS2[StreamSession]
        SS3[StreamSession]
    end
    
    subgraph Channel_Streams[Channel Streams]
        CH1[Channel 1]
        CH2[Channel 2]
    end
    
    C1 --> SM
    C2 --> SM
    C3 --> SM
    
    SM --> SS1
    SM --> SS2
    SM --> SS3
    
    SS1 --> CH1
    SS2 --> CH1
    SS3 --> CH2
{mermaid}

*StreamSession Dataclass:*

{code:language=python}
@dataclass
class StreamSession:
    session_id: str
    channel_id: int
    channel_number: int
    client_id: Optional[str]
    client_ip: Optional[str]
    user_agent: Optional[str]
    state: SessionState
    created_at: datetime
    last_activity: datetime
    bytes_sent: int
    errors: list[SessionError]
    restart_count: int
{code}

*Session Lifecycle:*

{mermaid}
stateDiagram-v2
    [*] --> Created: create_session
    Created --> Active: activate
    Active --> Active: record_data
    Active --> Error: record_error
    Error --> Active: recover
    Error --> Disconnected: max_errors
    Active --> Idle: no_activity
    Idle --> Active: resume
    Idle --> Disconnected: timeout
    Active --> Disconnected: disconnect
    Disconnected --> [*]
{mermaid}

h3. 1.3 Stream Throttler

*Source:* dizqueTV {{server/src/stream/throttler.ts}}
*Target:* {{exstreamtv/streaming/throttler.py}}

{mermaid}
flowchart TB
    subgraph Input_Stream[Input Stream]
        FFmpeg[FFmpeg Output]
        Rate[Raw Rate: Variable]
    end
    
    subgraph StreamThrottler[StreamThrottler]
        Buffer[Internal Buffer]
        Calculator[Rate Calculator]
        Timer[Delay Timer]
    end
    
    subgraph Output_Stream[Output Stream]
        Client[Client Connection]
        Target[Target Rate: 4 Mbps]
    end
    
    FFmpeg --> Buffer
    Buffer --> Calculator
    Calculator --> Timer
    Timer --> Client
{mermaid}

*Throttle Modes:*

||Mode||Behavior||Use Case||
|realtime|Match target bitrate exactly|Live streaming|
|burst|Allow 2x bursts, then throttle|VOD with seeking|
|adaptive|Adjust based on client feedback|Variable networks|
|disabled|No throttling|Direct connections|

----

h2. Phase 2: Error Handling System

h3. 2.1 Error Screen Generator

*Source:* dizqueTV {{server/src/stream/errorScreen.ts}}
*Target:* {{exstreamtv/streaming/error_screens.py}}

{mermaid}
flowchart TB
    subgraph Error_Detection[Error Detection]
        StreamError[Stream Error]
        Timeout[Connection Timeout]
        Restart[Channel Restart]
    end
    
    subgraph ErrorScreenGenerator[ErrorScreenGenerator]
        Config[ErrorScreenConfig]
        Builder[FFmpeg Command Builder]
        Generator[MPEG-TS Generator]
    end
    
    subgraph Visual_Modes[Visual Modes]
        Text[Text Overlay]
        Static[Static Image]
        Pattern[Test Pattern]
        Slate[Color Slate]
    end
    
    subgraph Audio_Modes[Audio Modes]
        Silent[Silent]
        Sine[Sine Wave]
        Noise[White Noise]
        Beep[Beep]
    end
    
    StreamError --> Config
    Timeout --> Config
    Restart --> Config
    
    Config --> Builder
    Builder --> Generator
    
    Generator --> Text
    Generator --> Static
    Generator --> Pattern
    Generator --> Slate
    
    Generator --> Silent
    Generator --> Sine
    Generator --> Noise
    Generator --> Beep
{mermaid}

----

h2. Phase 3: Advanced Scheduling

h3. 3.1 Time Slot Scheduler

*Source:* Tunarr {{server/src/services/TimeSlotScheduler.ts}}
*Target:* {{exstreamtv/scheduling/time_slots.py}}

{mermaid}
flowchart TB
    subgraph Schedule_Definition[Schedule Definition]
        Schedule[TimeSlotSchedule]
        Slot1[Slot: 06:00-09:00 Morning News]
        Slot2[Slot: 09:00-12:00 Talk Shows]
        Slot3[Slot: 12:00-18:00 Afternoon Movies]
        Slot4[Slot: 18:00-22:00 Prime Time]
        Slot5[Slot: 22:00-06:00 Late Night]
    end
    
    subgraph Scheduler[Scheduler]
        TSS[TimeSlotScheduler]
        Current[get_active_slot]
        Next[get_next_slot]
        Item[get_current_item]
    end
    
    Schedule --> Slot1
    Schedule --> Slot2
    Schedule --> Slot3
    Schedule --> Slot4
    Schedule --> Slot5
    
    TSS --> Current
    TSS --> Next
    TSS --> Item
{mermaid}

*TimeSlot Configuration:*

{code:language=python}
@dataclass
class TimeSlot:
    slot_id: str
    name: str
    start_time: time           # e.g., time(6, 0)
    duration_minutes: int      # e.g., 180
    collection_id: Optional[int]
    order_mode: TimeSlotOrderMode    # ordered, shuffle, random
    padding_mode: TimeSlotPaddingMode  # none, filler, loop, next
    flex_mode: TimeSlotFlexMode      # none, extend, compress
    days_of_week: int          # Bitmask (127 = all days)
{code}

h3. 3.2 Balance Scheduler

*Source:* Tunarr {{server/src/services/BalanceScheduler.ts}}
*Target:* {{exstreamtv/scheduling/balance.py}}

{mermaid}
flowchart TB
    subgraph Content_Sources[Content Sources]
        S1[Movies weight=40]
        S2[TV Shows weight=30]
        S3[Documentaries weight=20]
        S4[Specials weight=10]
    end
    
    subgraph Balance_Scheduler[Balance Scheduler]
        BS[BalanceScheduler]
        Weights[Weight Calculator]
        Cooldown[Cooldown Tracker]
        Selection[Source Selector]
    end
    
    subgraph Output[Output]
        Next[Next Item]
        Stats[Distribution Stats]
    end
    
    S1 --> BS
    S2 --> BS
    S3 --> BS
    S4 --> BS
    
    BS --> Weights
    Weights --> Cooldown
    Cooldown --> Selection
    Selection --> Next
    Selection --> Stats
{mermaid}

----

h2. Phase 4: Media Pipeline Improvements

h3. 4.1 Subtitle Stream Picker

*Source:* Tunarr {{server/src/ffmpeg/SubtitleStreamPicker.ts}}
*Target:* {{exstreamtv/ffmpeg/subtitle_picker.py}}

{mermaid}
flowchart TB
    subgraph FFprobe_Analysis[FFprobe Analysis]
        Probe[FFprobe JSON]
        Parser[Stream Parser]
    end
    
    subgraph Stream_Selection[Stream Selection]
        Streams[SubtitleStreams]
        Prefs[SubtitlePreferences]
        Picker[SubtitleStreamPicker]
    end
    
    subgraph Selection_Criteria[Selection Criteria]
        Lang[Language Match]
        Type[Text vs Image]
        SDH[SDH Detection]
        Default[Default Flag]
    end
    
    subgraph Output[Output]
        Selected[Selected Stream]
        Args[FFmpeg Arguments]
    end
    
    Probe --> Parser
    Parser --> Streams
    
    Streams --> Picker
    Prefs --> Picker
    
    Picker --> Lang
    Lang --> Type
    Type --> SDH
    SDH --> Default
    Default --> Selected
    
    Selected --> Args
{mermaid}

*Selection Priority:*
# Exact language match + preferred type
# Exact language match + any type
# Default stream
# First available stream

h3. 4.2 Audio Stream Picker

*Source:* Tunarr {{server/src/ffmpeg/AudioStreamPicker.ts}}
*Target:* {{exstreamtv/ffmpeg/audio_picker.py}}

*Downmix Options:*

||Input Layout||Target||FFmpeg Filter||
|5.1 Surround|Stereo|pan=stereo\|FL=...|
|7.1 Surround|5.1|pan=5.1\|...|
|Stereo|Mono|pan=mono\|c0=...|

----

h2. Phase 5: Database Infrastructure

h3. 5.1 Database Backup Manager

*Source:* Tunarr {{server/src/dao/BackupManager.ts}}
*Target:* {{exstreamtv/database/backup.py}}

{mermaid}
flowchart TB
    subgraph Backup_Triggers[Backup Triggers]
        Schedule[Scheduled Backup]
        Manual[Manual Backup]
        PreRestore[Pre-Restore Backup]
    end
    
    subgraph BackupManager[BackupManager]
        Config[BackupConfig]
        Creator[create_backup]
        Restorer[restore_backup]
        Cleaner[cleanup_old_backups]
    end
    
    subgraph Storage[Storage]
        Files[Backup Files]
        Compressed[Gzip Compressed]
        Metadata[BackupInfo]
    end
    
    Schedule --> Creator
    Manual --> Creator
    PreRestore --> Creator
    
    Creator --> Files
    Files --> Compressed
    Compressed --> Metadata
    
    Cleaner --> Files
    Restorer --> Files
{mermaid}

*Backup Configuration:*

{code:language=python}
@dataclass
class BackupConfig:
    enabled: bool = True
    backup_directory: str = "backups"
    interval_hours: int = 24
    keep_count: int = 7        # Keep N most recent
    keep_days: int = 30        # Delete older than N days
    compress: bool = True      # Gzip compression
{code}

----

h2. Phase 6: Enhanced AI Integration

h3. 6.1 Unified Log Collector

*Target:* {{exstreamtv/ai_agent/unified_log_collector.py}}

{mermaid}
flowchart TB
    subgraph Log_Sources[Log Sources]
        App[Application Logs]
        FFmpeg[FFmpeg Stderr]
        Plex[Plex Events]
        Jellyfin[Jellyfin Events]
        System[System Logs]
    end
    
    subgraph UnifiedLogCollector[UnifiedLogCollector]
        Parser[LogParser]
        Buffer[Ring Buffer]
        Correlator[Event Correlator]
    end
    
    subgraph Outputs[Outputs]
        Subscribers[Real-time Subscribers]
        Context[Context Windows]
        Errors[Recent Errors]
    end
    
    App --> Parser
    FFmpeg --> Parser
    Plex --> Parser
    Jellyfin --> Parser
    System --> Parser
    
    Parser --> Buffer
    Buffer --> Correlator
    
    Correlator --> Subscribers
    Correlator --> Context
    Correlator --> Errors
{mermaid}

h3. 6.2 FFmpeg AI Monitor

*Target:* {{exstreamtv/ai_agent/ffmpeg_monitor.py}}

{mermaid}
flowchart TB
    subgraph FFmpeg_Process[FFmpeg Process]
        Stderr[Stderr Output]
        Progress[Progress Lines]
        Errors[Error Messages]
    end
    
    subgraph FFmpegAIMonitor[FFmpegAIMonitor]
        Parser[Line Parser]
        Classifier[Error Classifier]
        HealthTracker[Health Tracker]
        Predictor[Failure Predictor]
    end
    
    subgraph Outputs[Outputs]
        Metrics[ChannelHealthMetrics]
        FFErrors[FFmpegError]
        Predictions[FailurePrediction]
        Analysis[AIAnalysis]
    end
    
    Stderr --> Parser
    Progress --> Parser
    Errors --> Parser
    
    Parser --> Classifier
    Classifier --> HealthTracker
    HealthTracker --> Predictor
    
    Predictor --> Metrics
    Predictor --> FFErrors
    Predictor --> Predictions
    Classifier --> Analysis
{mermaid}

*Error Classification:*

||Error Type||Pattern||Severity||Recoverable||
|CONNECTION_TIMEOUT|Connection timed out|ERROR|Yes|
|HTTP_ERROR|HTTP error 4xx/5xx|ERROR|Yes|
|CODEC_ERROR|Decoder not found|CRITICAL|No|
|HARDWARE_ERROR|videotoolbox error|ERROR|Yes|
|MEMORY_ERROR|Out of memory|CRITICAL|No|

h3. 6.3 Pattern Detector

*Target:* {{exstreamtv/ai_agent/pattern_detector.py}}

*Known Pattern Indicators:*

||Pattern||Indicators||Risk Level||
|DB Pool Exhaustion|pool exhausted, connection timeout, no connections|HIGH|
|FFmpeg Degradation|speed < 1.0x, dropping frames, buffer underrun|MEDIUM|
|URL Expiration|403 forbidden, 401 unauthorized, token expired|MEDIUM|
|Network Instability|connection reset, connection refused, timeout|HIGH|
|Memory Pressure|out of memory, allocation failed, swap usage|CRITICAL|

h3. 6.4 Auto Resolver

*Target:* {{exstreamtv/ai_agent/auto_resolver.py}}

{mermaid}
flowchart TB
    subgraph Issue_Detection[Issue Detection]
        Issue[DetectedIssue]
        Type[Issue Type]
        Severity[Severity Level]
    end
    
    subgraph AutoResolver[AutoResolver]
        StrategyMap[Strategy Mapping]
        RiskCheck[Risk Assessment]
        Executor[Fix Executor]
    end
    
    subgraph Resolution_Strategies[Resolution Strategies]
        Restart[RESTART]
        Refresh[REFRESH]
        Expand[EXPAND]
        Fallback[FALLBACK]
        Reduce[REDUCE]
        Escalate[ESCALATE]
    end
    
    subgraph Execution[Execution]
        Apply[apply_fix]
        Rollback[rollback]
        Learn[record_outcome]
    end
    
    Issue --> Type
    Type --> StrategyMap
    StrategyMap --> RiskCheck
    RiskCheck --> Executor
    
    Executor --> Restart
    Executor --> Refresh
    Executor --> Expand
    Executor --> Fallback
    Executor --> Reduce
    Executor --> Escalate
    
    Restart --> Apply
    Refresh --> Apply
    Apply --> Rollback
    Apply --> Learn
{mermaid}

*Issue-to-Strategy Mapping:*

||Issue Type||Primary Strategy||Risk Level||Confidence||
|FFMPEG_HANG|RESTART|MEDIUM|0.90|
|FFMPEG_CRASH|RESTART|MEDIUM|0.85|
|URL_EXPIRED|REFRESH|SAFE|0.95|
|DB_POOL_EXHAUSTED|EXPAND|LOW|0.80|
|AUTH_FAILED|REFRESH|SAFE|0.90|
|MEMORY_PRESSURE|REDUCE|MEDIUM|0.70|
|SOURCE_UNAVAILABLE|FALLBACK|SAFE|0.95|

----

h2. Complete Data Flow

{mermaid}
flowchart TB
    subgraph Client_Layer[Client Layer]
        Clients[IPTV Clients]
    end
    
    subgraph Streaming_Layer[Streaming Layer]
        SM[SessionManager]
        CM[ChannelManager]
        ST[StreamThrottler]
        ESG[ErrorScreenGenerator]
    end
    
    subgraph Scheduling_Layer[Scheduling Layer]
        TSS[TimeSlotScheduler]
        BS[BalanceScheduler]
    end
    
    subgraph Media_Layer[Media Layer]
        SSP[SubtitleStreamPicker]
        ASP[AudioStreamPicker]
        FFmpeg[FFmpeg Pipeline]
    end
    
    subgraph Data_Layer[Data Layer]
        DCM[DatabaseConnectionManager]
        DBM[DatabaseBackupManager]
        DB[(Database)]
    end
    
    subgraph AI_Layer[AI Layer]
        ULC[UnifiedLogCollector]
        FFM[FFmpegAIMonitor]
        PD[PatternDetector]
        AR[AutoResolver]
    end
    
    Clients <--> SM
    SM <--> CM
    CM <--> ST
    CM <--> ESG
    
    CM --> TSS
    CM --> BS
    TSS --> DCM
    BS --> DCM
    
    CM --> SSP
    CM --> ASP
    SSP --> FFmpeg
    ASP --> FFmpeg
    
    DCM --> DB
    DBM --> DB
    
    CM --> ULC
    FFmpeg --> FFM
    ULC --> PD
    FFM --> PD
    PD --> AR
    AR --> CM
    AR --> ESG
{mermaid}

----

h2. Configuration Reference

h3. AIAutoHealConfig

{code:language=yaml}
ai_auto_heal:
  enabled: true
  log_buffer_minutes: 30
  realtime_streaming: true
  ffmpeg_monitor_enabled: true
  ffmpeg_health_threshold: 0.8
  pattern_detection_enabled: true
  prediction_confidence_threshold: 0.75
  auto_resolve_enabled: true
  max_auto_fixes_per_hour: 50
  require_approval_above_risk: "MEDIUM"
  use_error_screen_fallback: true
  hot_swap_enabled: true
  learning_enabled: true
{code}

h3. DatabaseBackupConfig

{code:language=yaml}
database_backup:
  enabled: true
  backup_directory: "backups"
  interval_hours: 24
  keep_count: 7
  keep_days: 30
  compress: true
{code}

h3. SessionManagerConfig

{code:language=yaml}
session_manager:
  max_sessions_per_channel: 50
  idle_timeout_seconds: 300
  cleanup_interval_seconds: 60
{code}

h3. StreamThrottlerConfig

{code:language=yaml}
stream_throttler:
  enabled: true
  target_bitrate_bps: 4000000
  mode: "realtime"
{code}

----

h2. File Reference

h3. New Files Created

||File||Lines||Description||
|streaming/session_manager.py|~450|Session tracking from Tunarr|
|streaming/throttler.py|~380|Rate limiting from dizqueTV|
|streaming/error_screens.py|~420|Error streams from dizqueTV|
|scheduling/time_slots.py|~400|Time slot scheduling from Tunarr|
|scheduling/balance.py|~350|Balance scheduling from Tunarr|
|ffmpeg/subtitle_picker.py|~320|Subtitle selection from Tunarr|
|ffmpeg/audio_picker.py|~340|Audio selection from Tunarr|
|database/backup.py|~450|Backup management from Tunarr|
|ai_agent/unified_log_collector.py|~520|Log aggregation|
|ai_agent/ffmpeg_monitor.py|~480|FFmpeg monitoring|
|ai_agent/pattern_detector.py|~440|Pattern detection|
|ai_agent/auto_resolver.py|~500|Auto resolution|

h3. Modified Files

||File||Changes||
|database/connection.py|Added DatabaseConnectionManager|
|config.py|Added 4 new config classes|
|main.py|Initialize new components on startup|
|streaming/channel_manager.py|Integrated new components|
|streaming/__init__.py|Export new components|
|scheduling/__init__.py|Export new components|
|database/__init__.py|Export new components|
|ffmpeg/__init__.py|Export new components|

----

h2. Version History

||Version||Date||Changes||
|2.6.0|2026-01-31|Initial Tunarr/dizqueTV integration|

----

{tip}See [BUILD_PROGRESS|EXStreamTV:Build Progress] for overall development status.{tip}
