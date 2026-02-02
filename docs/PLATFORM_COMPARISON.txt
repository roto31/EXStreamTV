# EXStreamTV vs dizqueTV vs Tunarr: Comprehensive Platform Comparison

**Prepared by:** Principal Senior Integration Engineer & Principal Senior Application Developer  
**Date:** January 31, 2026  
**Purpose:** Platform analysis for EXStreamTV codebase improvement and potential module adoption

---

## Executive Summary

This document provides a comprehensive analysis comparing EXStreamTV with two major open-source IPTV platforms: **dizqueTV** and **Tunarr**. The analysis covers architecture, features, data flow, and identifies opportunities for code/module adoption to resolve current EXStreamTV issues.

### Platform Overview

| Aspect | EXStreamTV | dizqueTV | Tunarr |
|--------|------------|----------|--------|
| **Language** | Python (FastAPI) | JavaScript (Node.js/Express) | TypeScript (Node.js/Fastify) |
| **Database** | SQLAlchemy (SQLite/PostgreSQL) | JSON files + lowdb | Drizzle ORM + Kysely (SQLite) |
| **Frontend** | HTML/Jinja2 templates | jQuery + Bootstrap | React + Material-UI |
| **Architecture** | Monolithic async | Monolithic sync/event-driven | Monorepo with DI (Inversify) |
| **Stars** | Private | 1,722 | 1,954 |
| **Active Development** | Yes | Maintenance mode | Very active |

---

## 1. Architecture Comparison

### 1.1 EXStreamTV Architecture

```mermaid
flowchart TB
    subgraph "EXStreamTV Architecture"
        subgraph "API Layer"
            FastAPI[FastAPI Application]
            Routers[40+ API Routers]
            HDHR[HDHomeRun Emulation]
        end
        
        subgraph "Core Services"
            ChannelMgr[Channel Manager]
            PlayoutBuilder[Playout Builder]
            Scheduler[Schedule Engine]
            Streaming[MPEG-TS Streamer]
        end
        
        subgraph "Media Layer"
            URLResolver[URL Resolver]
            MediaLibs[Media Libraries<br/>Plex/Jellyfin/Local]
            Metadata[Metadata Engine<br/>TMDB/TVDB/AI]
        end
        
        subgraph "Encoding"
            FFmpegPipeline[FFmpeg Pipeline]
            HWAccel[Hardware Acceleration<br/>VideoToolbox/NVENC/QSV]
        end
        
        subgraph "Storage"
            SQLAlchemy[SQLAlchemy 2.0 Async]
            SQLite[(SQLite/PostgreSQL)]
        end
        
        FastAPI --> Routers
        Routers --> ChannelMgr
        Routers --> HDHR
        ChannelMgr --> PlayoutBuilder
        ChannelMgr --> Streaming
        PlayoutBuilder --> Scheduler
        Streaming --> FFmpegPipeline
        FFmpegPipeline --> HWAccel
        ChannelMgr --> URLResolver
        URLResolver --> MediaLibs
        MediaLibs --> Metadata
        ChannelMgr --> SQLAlchemy
        SQLAlchemy --> SQLite
    end
```

### 1.2 dizqueTV Architecture

```mermaid
flowchart TB
    subgraph "dizqueTV Architecture"
        subgraph "API Layer"
            Express[Express.js Server]
            HDHR_API[HDHomeRun API]
            WebUI[jQuery Web UI]
        end
        
        subgraph "Core Services"
            ChannelCache[Channel Cache]
            ProgramPlayer[Program Player]
            PlexPlayer[Plex Player]
            OfflinePlayer[Offline Player]
        end
        
        subgraph "Transcoding"
            FFmpeg[FFMPEG Class]
            PlexTranscoder[Plex Transcoder]
            Throttler[Stream Throttler]
        end
        
        subgraph "Data Access"
            DAO[DAO Layer]
            JSONFiles[(JSON Files<br/>.dizquetv/)]
        end
        
        Express --> HDHR_API
        Express --> WebUI
        Express --> ChannelCache
        ChannelCache --> ProgramPlayer
        ProgramPlayer --> PlexPlayer
        ProgramPlayer --> OfflinePlayer
        PlexPlayer --> PlexTranscoder
        PlexTranscoder --> FFmpeg
        OfflinePlayer --> FFmpeg
        FFmpeg --> Throttler
        ChannelCache --> DAO
        DAO --> JSONFiles
    end
```

### 1.3 Tunarr Architecture

```mermaid
flowchart TB
    subgraph "Tunarr Architecture"
        subgraph "API Layer"
            Fastify[Fastify Server + Zod]
            OpenAPI[OpenAPI Spec]
            WebApp[React Web App<br/>Material-UI + TanStack]
        end
        
        subgraph "Dependency Injection"
            Container[Inversify Container]
            Modules[Service Modules<br/>DB/Stream/FFmpeg]
        end
        
        subgraph "Services Layer"
            SessionMgr[Session Manager]
            Scheduling[Scheduling Services<br/>TimeSlot/RandomSlot/Balance]
            Scanner[Media Scanner]
        end
        
        subgraph "Streaming Pipeline"
            VideoStream[Video Stream]
            ConcatSession[Concat Session]
            ProgramStream[Program Stream Factory]
            StreamThrottler[Stream Throttler]
        end
        
        subgraph "External Media"
            PlexAPI[Plex API Client]
            JellyfinAPI[Jellyfin API Client]
            EmbyAPI[Emby API Client]
            LocalMedia[Local Media Scanner]
        end
        
        subgraph "FFmpeg Layer"
            FFmpegBuilder[FFmpeg Builder<br/>Pattern-based]
            SubtitlePicker[Subtitle Stream Picker]
            PtsCalculator[PTS Duration Calculator]
        end
        
        subgraph "Database Layer"
            DrizzleORM[Drizzle ORM]
            Kysely[Kysely<br/>Legacy queries]
            SQLite[(SQLite)]
            Backups[Scheduled Backups]
        end
        
        Fastify --> OpenAPI
        Fastify --> Container
        Container --> Modules
        Modules --> SessionMgr
        Modules --> Scheduling
        Modules --> Scanner
        SessionMgr --> VideoStream
        SessionMgr --> ConcatSession
        ConcatSession --> ProgramStream
        ProgramStream --> StreamThrottler
        Scanner --> PlexAPI
        Scanner --> JellyfinAPI
        Scanner --> EmbyAPI
        Scanner --> LocalMedia
        ProgramStream --> FFmpegBuilder
        FFmpegBuilder --> SubtitlePicker
        FFmpegBuilder --> PtsCalculator
        SessionMgr --> DrizzleORM
        DrizzleORM --> SQLite
        Kysely --> SQLite
        SQLite --> Backups
    end
```

---

## 2. Feature Comparison Matrix

### 2.1 Core Features

| Feature | EXStreamTV | dizqueTV | Tunarr |
|---------|------------|----------|--------|
| **HDHomeRun Emulation** | ✅ Full SSDP + API | ✅ Full | ✅ Full |
| **M3U Playlist Generation** | ✅ | ✅ | ✅ |
| **XMLTV EPG** | ✅ | ✅ | ✅ |
| **HLS Streaming** | ✅ | ❌ | ✅ |
| **MPEG-TS Streaming** | ✅ | ✅ | ✅ |
| **Browser Playback** | ⚠️ Limited | ❌ | ✅ Full |
| **Dark Mode UI** | ⚠️ Partial | ❌ | ✅ |

### 2.2 Media Sources

| Source | EXStreamTV | dizqueTV | Tunarr |
|--------|------------|----------|--------|
| **Plex** | ✅ | ✅ | ✅ |
| **Jellyfin** | ✅ | ❌ | ✅ |
| **Emby** | ⚠️ Partial | ❌ | ✅ |
| **Local Files** | ✅ | ❌ | ✅ |
| **YouTube** | ✅ | ❌ | ❌ |
| **Archive.org** | ✅ | ❌ | ❌ |
| **IPTV URLs** | ✅ | ❌ | ❌ |

### 2.3 Scheduling Features

| Feature | EXStreamTV | dizqueTV | Tunarr |
|---------|------------|----------|--------|
| **Time Slots** | ✅ | ✅ | ✅ Advanced |
| **Random Slots** | ⚠️ Basic | ❌ | ✅ Advanced |
| **Balance/Weighting** | ❌ | ❌ | ✅ |
| **Filler Content** | ✅ Pre/Mid/Post | ✅ | ✅ |
| **Block Scheduling** | ✅ | ⚠️ Manual | ⚠️ Basic |
| **AI-Powered Scheduling** | ✅ | ❌ | ❌ |
| **Replicate/Consolidate** | ❌ | ❌ | ✅ |

### 2.4 Transcoding & Encoding

| Feature | EXStreamTV | dizqueTV | Tunarr |
|---------|------------|----------|--------|
| **Hardware Acceleration** | ✅ All major | ✅ NVIDIA only | ✅ All major |
| **VideoToolbox (macOS)** | ✅ | ❌ | ✅ |
| **NVENC** | ✅ | ✅ | ✅ |
| **QSV** | ✅ | ❌ | ✅ |
| **VAAPI** | ✅ | ✅ | ✅ |
| **AMF** | ✅ | ❌ | 🔄 Coming |
| **Subtitle Support** | ⚠️ Basic | ✅ | ✅ Advanced |
| **Deinterlacing** | ⚠️ Basic | ✅ Auto | ✅ |
| **Per-Channel Transcode Config** | ✅ | ✅ | ✅ |

### 2.5 Advanced Features

| Feature | EXStreamTV | dizqueTV | Tunarr |
|---------|------------|----------|--------|
| **AI Channel Creation** | ✅ | ❌ | ❌ |
| **AI Metadata Enhancement** | ✅ | ❌ | ❌ |
| **Smart Collections** | ✅ | ❌ | ✅ |
| **NFO File Parsing** | ⚠️ Basic | ❌ | ✅ |
| **Scheduled Backups** | ❌ | ❌ | ✅ |
| **Audio Language Preference** | ❌ | ❌ | ✅ |
| **Advanced Subtitle Config** | ❌ | ❌ | ✅ |
| **macOS App** | ✅ Native Swift | ❌ | ✅ |
| **Meilisearch Integration** | ❌ | ❌ | ✅ |

---

## 3. Data Flow Diagrams

### 3.1 Channel Streaming Data Flow

```mermaid
sequenceDiagram
    participant Client
    participant EX as EXStreamTV
    participant DQ as dizqueTV
    participant TN as Tunarr
    
    Note over Client,TN: Client Requests Channel Stream
    
    rect rgb(200, 220, 255)
        Note over EX: EXStreamTV Flow
        Client->>EX: GET /hdhomerun/auto/v{channel}
        EX->>EX: ChannelManager.get_stream()
        EX->>EX: Load playout from DB
        EX->>EX: URLResolver.resolve(media_item)
        EX->>EX: FFmpegPipeline.build_command()
        EX->>EX: Spawn FFmpeg process
        EX-->>Client: StreamingResponse (MPEG-TS chunks)
    end
    
    rect rgb(220, 255, 220)
        Note over DQ: dizqueTV Flow
        Client->>DQ: GET /video?channel={id}
        DQ->>DQ: ChannelCache.getCurrentPlayingProgram()
        DQ->>DQ: ProgramPlayer.play()
        DQ->>DQ: PlexPlayer.getStream() or OfflinePlayer
        DQ->>DQ: FFMPEG.spawn()
        DQ->>DQ: Throttler.throttle()
        DQ-->>Client: Piped MPEG-TS stream
    end
    
    rect rgb(255, 220, 220)
        Note over TN: Tunarr Flow
        Client->>TN: GET /stream/channel/{id}
        TN->>TN: SessionManager.getSession()
        TN->>TN: StreamProgramCalculator.calculate()
        TN->>TN: ProgramStreamFactory.create()
        TN->>TN: FfmpegStreamFactory.spawn()
        TN->>TN: StreamThrottler.throttle()
        TN-->>Client: VideoStream (MPEG-TS)
    end
```

### 3.2 Playout/Schedule Building Flow

```mermaid
flowchart LR
    subgraph "EXStreamTV Playout Building"
        EX_Schedule[ProgramSchedule] --> EX_Items[ScheduleItems]
        EX_Items --> EX_Enum[Enumerators<br/>Chrono/Shuffle/Random]
        EX_Enum --> EX_Builder[PlayoutBuilder]
        EX_Builder --> EX_State[PlayoutState]
        EX_State --> EX_PlayoutItems[PlayoutItems<br/>with start/finish times]
    end
    
    subgraph "dizqueTV Playout Building"
        DQ_Channel[Channel Config] --> DQ_Programs[Programs Array]
        DQ_Programs --> DQ_Shuffle[Shuffle Logic]
        DQ_Shuffle --> DQ_Cache[ChannelCache]
        DQ_Cache --> DQ_Current[getCurrentPlayingProgram]
    end
    
    subgraph "Tunarr Playout Building"
        TN_Config[Channel + Lineup] --> TN_Slots[TimeSlot/RandomSlot Service]
        TN_Slots --> TN_Iterator[ProgramIterator<br/>Ordered/Shuffle/Static]
        TN_Iterator --> TN_Calculator[StreamProgramCalculator]
        TN_Calculator --> TN_Session[ConcatSession<br/>with lineup items]
    end
```

### 3.3 FFmpeg Pipeline Comparison

```mermaid
flowchart TB
    subgraph "EXStreamTV FFmpeg"
        EX_Input[Input Source] --> EX_Detect[Detect Online/Local]
        EX_Detect --> EX_HW[Hardware Accel Flags]
        EX_HW --> EX_Filters[Filter Chain<br/>Scale/Pad/Format]
        EX_Filters --> EX_Encode[Encoder Selection<br/>VideoToolbox/NVENC/etc]
        EX_Encode --> EX_BSF[Bitstream Filters<br/>h264_mp4toannexb]
        EX_BSF --> EX_Out[MPEG-TS Output]
        
        EX_Detect -.->|Bug Fix| EX_Flags[Error Tolerance Flags<br/>genpts/discardcorrupt]
        EX_Detect -.->|Bug Fix| EX_RT[-re realtime flag]
    end
    
    subgraph "dizqueTV FFmpeg"
        DQ_Input[Input Stream] --> DQ_Opts[Transcoding Options]
        DQ_Opts --> DQ_Filters[Filter Complex<br/>Scale/Pad/Overlay/Deinterlace]
        DQ_Filters --> DQ_Encode[Video/Audio Encode]
        DQ_Encode --> DQ_Out[MPEG-TS pipe:1]
        
        DQ_Input -.->|Feature| DQ_WM[Watermark Overlay]
        DQ_Input -.->|Feature| DQ_Error[Error Screen Generation]
        DQ_Input -.->|Feature| DQ_Offline[Offline Screen with Audio]
    end
    
    subgraph "Tunarr FFmpeg"
        TN_Input[Program Source] --> TN_Builder[FFmpeg Builder Pattern]
        TN_Builder --> TN_Subtitle[SubtitleStreamPicker]
        TN_Builder --> TN_Params[PlaybackParamsCalculator]
        TN_Params --> TN_Process[FfmpegProcess]
        TN_Process --> TN_PTS[PTS Duration Calculator]
        TN_PTS --> TN_Out[Stream Output]
        
        TN_Builder -.->|Feature| TN_Lang[Audio Language Selection]
        TN_Builder -.->|Feature| TN_SubConfig[Subtitle Type Config]
    end
```

### 3.4 Media Source Integration Flow

```mermaid
flowchart TB
    subgraph "EXStreamTV Media Sources"
        EX_Plex[Plex Library] --> EX_Resolver[URL Resolver]
        EX_Jellyfin[Jellyfin Library] --> EX_Resolver
        EX_Local[Local Files] --> EX_Resolver
        EX_YT[YouTube URLs] --> EX_Resolver
        EX_Archive[Archive.org] --> EX_Resolver
        EX_IPTV[IPTV Sources] --> EX_Resolver
        
        EX_Resolver --> EX_Cache[Library Cache]
        EX_Cache --> EX_Stream[Streaming URL]
        
        EX_Stream --> EX_Meta[Metadata Engine]
        EX_Meta --> EX_TMDB[TMDB]
        EX_Meta --> EX_TVDB[TVDB]
        EX_Meta --> EX_AI[AI Enhancer]
    end
    
    subgraph "dizqueTV Media Sources"
        DQ_Plex[Plex Only] --> DQ_API[Plex API]
        DQ_API --> DQ_Trans[Plex Transcoder<br/>or Direct]
        DQ_Trans --> DQ_URL[Stream URL]
    end
    
    subgraph "Tunarr Media Sources"
        TN_Plex[Plex Client] --> TN_Factory[MediaSourceApiFactory]
        TN_Jellyfin[Jellyfin Client] --> TN_Factory
        TN_Emby[Emby Client] --> TN_Factory
        TN_Local[Local Media DB] --> TN_Factory
        
        TN_Factory --> TN_Canon[Canonicalization]
        TN_Canon --> TN_Details[ExternalStreamDetailsFetcher]
        TN_Details --> TN_URL[Stream URL]
        
        TN_Canon --> TN_Search[Meilisearch Index]
    end
```

---

## 4. Pros and Cons Analysis

### 4.1 EXStreamTV

#### Pros ✅
1. **Python/FastAPI Stack** - Modern async Python with excellent type hints
2. **Unique Media Sources** - YouTube, Archive.org, IPTV URL support not found elsewhere
3. **AI-Powered Features** - Channel creation, metadata enhancement, troubleshooting
4. **Comprehensive Hardware Acceleration** - All major platforms including VideoToolbox
5. **Native macOS App** - Swift-based menu bar application
6. **ErsatzTV-Style Continuous Streaming** - Anchor time-based position tracking
7. **Hybrid Architecture** - Combines best of StreamTV and ErsatzTV
8. **Rich Metadata** - TMDB, TVDB, and AI-enhanced metadata

#### Cons ❌
1. **Database Connection Pool Issues** - Pool exhaustion with many channels
2. **Mixed Async/Sync Code** - ChannelManager uses sync DB sessions
3. **Debug Code in Production** - Agent logging statements remain
4. **High Restart Counts** - 31-51 restarts observed on channels
5. **Cold Start Timeouts** - 10s timeout insufficient for FFmpeg startup
6. **No Scheduled Backups** - Missing database backup automation
7. **Limited Subtitle Support** - Basic compared to Tunarr
8. **No Audio Language Selection** - Per-channel audio preferences missing

### 4.2 dizqueTV

#### Pros ✅
1. **Simplicity** - Straightforward JavaScript codebase
2. **Battle-Tested** - Mature project with known stability
3. **Excellent Error Handling** - Error screens, offline screens with audio
4. **Watermark System** - Robust channel logo overlay
5. **Auto Deinterlacing** - Automatic based on scan type detection
6. **Throttler** - Stream rate limiting for smooth playback
7. **Filler Content** - Comprehensive commercial/filler support
8. **Low Resource Usage** - Efficient for single-purpose deployment

#### Cons ❌
1. **Plex Only** - No Jellyfin, Emby, or local file support
2. **No HLS** - MPEG-TS only, limits browser playback
3. **JSON Storage** - Not scalable for large libraries
4. **Maintenance Mode** - Limited active development
5. **No Modern UI** - jQuery/Bootstrap vs React
6. **No Hardware Acceleration Options** - NVIDIA only
7. **No macOS VideoToolbox** - Not optimized for Mac
8. **No Smart Collections** - Manual programming only

### 4.3 Tunarr

#### Pros ✅
1. **Modern TypeScript** - Type-safe with Zod schemas throughout
2. **Dependency Injection** - Clean Inversify-based architecture
3. **Advanced Scheduling** - TimeSlots, RandomSlots, Balance, Replicate
4. **Modern React UI** - Material-UI with TanStack Router/Query
5. **Multi-Source** - Plex, Jellyfin, Emby, Local with unified API
6. **Advanced Subtitles** - Language preference, type selection, extraction
7. **Audio Preferences** - Per-channel audio language selection
8. **Scheduled Backups** - Automatic database backup system
9. **Meilisearch** - Fast full-text search across media
10. **Browser Streaming** - Full in-browser playback support
11. **Active Development** - Very active with regular releases
12. **OpenAPI Spec** - Auto-generated API client for frontend

#### Cons ❌
1. **No YouTube/Archive.org** - Missing online streaming sources
2. **No IPTV URL Support** - Cannot add arbitrary stream URLs
3. **No AI Features** - No AI-powered channel creation
4. **Heavier Resource Usage** - More complex stack
5. **Dual ORM** - Transitioning from Kysely to Drizzle adds complexity
6. **No Real Python** - Harder to extend for Python-native integrations

---

## 5. Current EXStreamTV Issues & Resolution Mapping

### 5.1 Issue Analysis

| Issue | Severity | Root Cause | Tunarr Solution | dizqueTV Solution |
|-------|----------|------------|-----------------|-------------------|
| **DB Pool Exhaustion** | Critical | Pool size too small for concurrent channels | Connection pooling in DBAccess | Not applicable (JSON) |
| **Mixed Async/Sync** | High | Legacy code patterns | Full async with Fastify | Sync throughout |
| **High Restart Counts** | High | FFmpeg process instability | Robust session management | Throttler + error handling |
| **Cold Start Timeout** | Medium | 10s timeout too short | Configurable session timeouts | Immediate spawn approach |
| **No Scheduled Backups** | Medium | Feature missing | `db/backup/` module | Not available |
| **Limited Subtitles** | Low | Basic implementation | `SubtitleStreamPicker` | Basic support |
| **Debug Logging** | Low | Dev code in production | Clean logging infrastructure | Simple console.log |

### 5.2 Recommended Adoptions

```mermaid
flowchart LR
    subgraph "From Tunarr"
        T1[Session Manager Pattern]
        T2[Scheduled Backup System]
        T3[Subtitle Stream Picker]
        T4[Advanced Scheduling Tools]
        T5[Stream Throttler]
        T6[Audio Language Selection]
        T7[OpenAPI Generation]
    end
    
    subgraph "From dizqueTV"
        D1[Error Screen Generation]
        D2[Offline Screen with Audio]
        D3[Watermark Overlay System]
        D4[Auto Deinterlacing]
        D5[Throttler Logic]
        D6[Channel Cache Pattern]
    end
    
    subgraph "EXStreamTV Integration"
        EX[Enhanced EXStreamTV]
    end
    
    T1 --> EX
    T2 --> EX
    T3 --> EX
    T4 --> EX
    T5 --> EX
    T6 --> EX
    T7 --> EX
    
    D1 --> EX
    D2 --> EX
    D3 --> EX
    D4 --> EX
    D5 --> EX
    D6 --> EX
```

---

## 6. Adoption & Integration Plan

### Phase 1: Critical Stability Fixes (Priority: CRITICAL)

#### 1.1 Adopt Tunarr Session Manager Pattern

**Problem:** High restart counts and connection management issues

**Solution:** Port Tunarr's `SessionManager` concept

```python
# Proposed: exstreamtv/streaming/session_manager.py

class StreamSession:
    """Port of Tunarr's Session concept."""
    
    def __init__(self, channel_id: int, session_id: str):
        self.channel_id = channel_id
        self.session_id = session_id
        self.started_at = datetime.utcnow()
        self.connection_count = 0
        self.last_activity = datetime.utcnow()
        self._lock = asyncio.Lock()
        
    async def increment_connections(self):
        async with self._lock:
            self.connection_count += 1
            self.last_activity = datetime.utcnow()
            
    async def decrement_connections(self):
        async with self._lock:
            self.connection_count -= 1
            self.last_activity = datetime.utcnow()
            return self.connection_count == 0

class SessionManager:
    """Manages streaming sessions with connection tracking."""
    
    def __init__(self):
        self._sessions: dict[int, StreamSession] = {}
        self._cleanup_task: asyncio.Task | None = None
        
    async def get_or_create_session(self, channel_id: int) -> StreamSession:
        if channel_id not in self._sessions:
            session_id = str(uuid.uuid4())
            self._sessions[channel_id] = StreamSession(channel_id, session_id)
        return self._sessions[channel_id]
        
    async def cleanup_idle_sessions(self, idle_threshold_seconds: int = 300):
        """Clean up sessions with no active connections."""
        now = datetime.utcnow()
        to_remove = []
        for channel_id, session in self._sessions.items():
            if session.connection_count == 0:
                idle_time = (now - session.last_activity).total_seconds()
                if idle_time > idle_threshold_seconds:
                    to_remove.append(channel_id)
        for channel_id in to_remove:
            del self._sessions[channel_id]
```

#### 1.2 Port dizqueTV Throttler

**Problem:** Stream rate issues causing playback problems

**Solution:** Adapt dizqueTV's `throttler.js`

```python
# Proposed: exstreamtv/streaming/throttler.py

class StreamThrottler:
    """
    Port of dizqueTV throttler.js for stream rate limiting.
    Ensures MPEG-TS is delivered at proper rate for smooth playback.
    """
    
    def __init__(self, bitrate_kbps: int = 4000):
        self.bytes_per_second = (bitrate_kbps * 1000) // 8
        self.bytes_per_chunk = 188 * 7  # 7 TS packets
        self.chunk_interval = self.bytes_per_chunk / self.bytes_per_second
        
    async def throttle(
        self, 
        stream: AsyncIterator[bytes]
    ) -> AsyncIterator[bytes]:
        """Throttle stream to target bitrate."""
        last_yield = time.monotonic()
        
        async for chunk in stream:
            now = time.monotonic()
            expected_time = last_yield + (len(chunk) / self.bytes_per_second)
            
            if now < expected_time:
                await asyncio.sleep(expected_time - now)
                
            yield chunk
            last_yield = time.monotonic()
```

### Phase 2: Error Handling Improvements (Priority: HIGH)

#### 2.1 Adopt dizqueTV Error Screen System

**Problem:** No graceful error display during stream failures

**Solution:** Port dizqueTV's error/offline screen generation

```python
# Proposed: exstreamtv/streaming/error_screens.py

class ErrorScreenGenerator:
    """
    Port of dizqueTV's error screen generation.
    Generates MPEG-TS with error message or offline image.
    """
    
    def __init__(self, ffmpeg_path: str, resolution: tuple[int, int] = (1920, 1080)):
        self.ffmpeg_path = ffmpeg_path
        self.width, self.height = resolution
        
    async def generate_error_stream(
        self,
        title: str,
        subtitle: str,
        duration_seconds: int = 60,
        audio_type: str = "silent"  # silent, sine, whitenoise
    ) -> AsyncIterator[bytes]:
        """Generate error screen as MPEG-TS stream."""
        
        # Build FFmpeg command for error screen
        # Based on dizqueTV ffmpeg.js spawnError
        cmd = [
            self.ffmpeg_path,
            "-f", "lavfi",
            "-i", f"color=c=black:s={self.width}x{self.height}:d={duration_seconds}",
            "-vf", f"drawtext=text='{title}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        ]
        
        # Add audio based on type
        if audio_type == "silent":
            cmd.extend(["-f", "lavfi", "-i", f"anullsrc=duration={duration_seconds}"])
        elif audio_type == "sine":
            cmd.extend(["-f", "lavfi", "-i", f"sine=f=440:d={duration_seconds}"])
            
        cmd.extend([
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            "-f", "mpegts", "pipe:1"
        ])
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        async for chunk in self._read_stream(process.stdout):
            yield chunk
            
    async def generate_offline_stream(
        self,
        image_path: str,
        soundtrack_path: Optional[str] = None,
        duration_seconds: int = 3600
    ) -> AsyncIterator[bytes]:
        """Generate offline screen with optional soundtrack."""
        # Port of dizqueTV spawnOffline
        pass
```

### Phase 3: Advanced Scheduling (Priority: MEDIUM)

#### 3.1 Adopt Tunarr Scheduling Tools

**Problem:** Limited scheduling options compared to Tunarr

**Solution:** Port Tunarr's scheduling services

```python
# Proposed: exstreamtv/scheduling/time_slots.py

from dataclasses import dataclass
from typing import List, Optional
from datetime import time, timedelta

@dataclass
class TimeSlot:
    """Port of Tunarr TimeSlotImpl."""
    start_time: time
    duration: timedelta
    programs: List[int]  # Program/collection IDs
    order: str = "shuffle"  # shuffle, ordered, random
    flex: bool = False  # Allow flexible duration
    
@dataclass
class RandomSlot:
    """Port of Tunarr RandomSlotImpl."""
    programs: List[int]
    weight: float = 1.0
    cooldown_minutes: int = 0
    
class TimeSlotScheduler:
    """
    Port of Tunarr TimeSlotSchedulerService.
    Creates schedule based on time-of-day slots.
    """
    
    def __init__(self, slots: List[TimeSlot]):
        self.slots = sorted(slots, key=lambda s: s.start_time)
        
    def get_program_for_time(self, dt: datetime) -> Optional[int]:
        """Get the program that should play at given time."""
        current_time = dt.time()
        
        for i, slot in enumerate(self.slots):
            next_slot = self.slots[(i + 1) % len(self.slots)]
            
            if self._time_in_slot(current_time, slot.start_time, next_slot.start_time):
                return self._pick_program(slot)
                
        return None
        
    def _pick_program(self, slot: TimeSlot) -> int:
        """Pick program based on slot order."""
        if slot.order == "random":
            return random.choice(slot.programs)
        elif slot.order == "shuffle":
            # Track position in shuffled list
            pass
        else:  # ordered
            # Track sequential position
            pass

class BalanceScheduler:
    """
    Port of Tunarr Balance scheduling.
    Distributes content based on weights.
    """
    
    def __init__(self, programs: List[tuple[int, float]]):
        """
        Args:
            programs: List of (program_id, weight) tuples
        """
        self.programs = programs
        self.total_weight = sum(w for _, w in programs)
        
    def get_next_program(self) -> int:
        """Select next program based on weighted distribution."""
        r = random.uniform(0, self.total_weight)
        cumulative = 0
        
        for program_id, weight in self.programs:
            cumulative += weight
            if r <= cumulative:
                return program_id
                
        return self.programs[-1][0]
```

### Phase 4: Subtitle & Audio Improvements (Priority: MEDIUM)

#### 4.1 Adopt Tunarr Subtitle System

```python
# Proposed: exstreamtv/ffmpeg/subtitle_picker.py

@dataclass
class SubtitlePreference:
    """Port of Tunarr subtitle preferences."""
    enabled: bool = True
    languages: List[str] = field(default_factory=lambda: ["eng"])
    prefer_text: bool = True  # Text over image-based
    burn_in: bool = False
    
class SubtitleStreamPicker:
    """
    Port of Tunarr SubtitleStreamPicker.
    Selects best subtitle stream based on preferences.
    """
    
    def __init__(self, preferences: SubtitlePreference):
        self.preferences = preferences
        
    def pick_stream(
        self,
        streams: List[dict]  # FFprobe stream info
    ) -> Optional[int]:
        """Select best subtitle stream index."""
        if not self.preferences.enabled:
            return None
            
        subtitle_streams = [
            s for s in streams 
            if s.get("codec_type") == "subtitle"
        ]
        
        # Score each stream
        scored = []
        for stream in subtitle_streams:
            score = self._score_stream(stream)
            scored.append((score, stream["index"]))
            
        if scored:
            scored.sort(reverse=True)
            return scored[0][1]
            
        return None
        
    def _score_stream(self, stream: dict) -> int:
        score = 0
        lang = stream.get("tags", {}).get("language", "und")
        
        # Language match
        if lang in self.preferences.languages:
            score += 100 * (len(self.preferences.languages) - 
                          self.preferences.languages.index(lang))
            
        # Text vs image preference
        codec = stream.get("codec_name", "")
        is_text = codec in ["subrip", "srt", "ass", "ssa", "webvtt"]
        if self.preferences.prefer_text and is_text:
            score += 50
        elif not self.preferences.prefer_text and not is_text:
            score += 50
            
        return score
```

#### 4.2 Audio Language Selection

```python
# Proposed: exstreamtv/ffmpeg/audio_picker.py

@dataclass
class AudioPreference:
    """Audio stream preferences per channel."""
    languages: List[str] = field(default_factory=lambda: ["eng"])
    prefer_surround: bool = False
    prefer_commentary: bool = False
    
class AudioStreamPicker:
    """Select best audio stream based on preferences."""
    
    def pick_stream(
        self,
        streams: List[dict],
        preferences: AudioPreference
    ) -> int:
        """Select best audio stream index."""
        audio_streams = [
            s for s in streams
            if s.get("codec_type") == "audio"
        ]
        
        if not audio_streams:
            return 0  # Default
            
        scored = []
        for stream in audio_streams:
            score = self._score_stream(stream, preferences)
            scored.append((score, stream["index"]))
            
        scored.sort(reverse=True)
        return scored[0][1]
```

### Phase 5: Database & Backup System (Priority: MEDIUM)

#### 5.1 Adopt Tunarr Backup System

```python
# Proposed: exstreamtv/database/backup.py

import shutil
from pathlib import Path
from datetime import datetime
import asyncio

class DatabaseBackupManager:
    """
    Port of Tunarr db/backup system.
    Scheduled, configurable database backups.
    """
    
    def __init__(
        self,
        db_path: str,
        backup_dir: str,
        max_backups: int = 10,
        backup_interval_hours: int = 24
    ):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.backup_interval = backup_interval_hours * 3600
        self._backup_task: asyncio.Task | None = None
        
    async def start_scheduled_backups(self):
        """Start background backup task."""
        self._backup_task = asyncio.create_task(self._backup_loop())
        
    async def _backup_loop(self):
        while True:
            try:
                await self.create_backup()
                await self._cleanup_old_backups()
            except Exception as e:
                logger.error(f"Backup failed: {e}")
            await asyncio.sleep(self.backup_interval)
            
    async def create_backup(self) -> Path:
        """Create a database backup."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"exstreamtv_backup_{timestamp}.db"
        backup_path = self.backup_dir / backup_name
        
        # Use SQLite backup API for consistency
        await asyncio.to_thread(
            shutil.copy2,
            self.db_path,
            backup_path
        )
        
        logger.info(f"Created backup: {backup_path}")
        return backup_path
        
    async def _cleanup_old_backups(self):
        """Remove old backups beyond max_backups."""
        backups = sorted(
            self.backup_dir.glob("exstreamtv_backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        for old_backup in backups[self.max_backups:]:
            old_backup.unlink()
            logger.info(f"Removed old backup: {old_backup}")
```

### Phase 6: Connection Pool Optimization (Priority: HIGH)

```python
# Proposed changes to: exstreamtv/database/connection.py

from sqlalchemy.pool import QueuePool

def create_async_engine(database_url: str, channel_count: int = 50):
    """
    Create engine with pool sized for channel count.
    
    Based on Tunarr DBAccess patterns.
    """
    # Calculate pool size based on expected concurrent operations
    # Each channel needs ~2 connections (stream + position updates)
    pool_size = max(20, channel_count * 2)
    max_overflow = pool_size  # Allow 2x for bursts
    
    return create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=30,
        pool_recycle=3600,  # Recycle connections hourly
        pool_pre_ping=True,  # Validate connections
    )
```

---

## 7. Implementation Priority Matrix

```mermaid
quadrantChart
    title Implementation Priority vs Effort
    x-axis Low Effort --> High Effort
    y-axis Low Priority --> High Priority
    quadrant-1 "Quick Wins"
    quadrant-2 "Major Projects"
    quadrant-3 "Fill In"
    quadrant-4 "Plan Carefully"
    
    "Session Manager": [0.6, 0.95]
    "Throttler": [0.3, 0.9]
    "Error Screens": [0.4, 0.85]
    "DB Pool Fix": [0.2, 0.9]
    "Backup System": [0.3, 0.7]
    "Time Slots": [0.6, 0.6]
    "Random Slots": [0.5, 0.55]
    "Balance Scheduler": [0.4, 0.5]
    "Subtitle Picker": [0.5, 0.6]
    "Audio Picker": [0.4, 0.5]
    "OpenAPI Gen": [0.7, 0.4]
    "Meilisearch": [0.8, 0.3]
```

### Recommended Implementation Order

1. **Week 1-2:** DB Pool Fix, Throttler, Debug Code Cleanup
2. **Week 3-4:** Session Manager, Error Screen Generator
3. **Week 5-6:** Backup System, Offline Screen Support
4. **Week 7-8:** Advanced Scheduling (TimeSlots, RandomSlots)
5. **Week 9-10:** Subtitle/Audio Pickers
6. **Month 3:** Balance Scheduler, OpenAPI Generation

---

## 8. Conclusion

### Key Recommendations

1. **Adopt from Tunarr:**
   - Session management pattern for connection tracking
   - Scheduled backup system
   - Advanced scheduling tools (TimeSlots, RandomSlots, Balance)
   - Subtitle and audio stream selection
   - OpenAPI specification generation

2. **Adopt from dizqueTV:**
   - Stream throttler for smooth playback
   - Error/offline screen generation
   - Watermark overlay system
   - Auto-deinterlacing logic

3. **Keep EXStreamTV Unique Features:**
   - YouTube/Archive.org/IPTV support
   - AI-powered channel creation
   - AI metadata enhancement
   - Python/FastAPI stack (superior for AI integration)

4. **Immediate Priorities:**
   - Fix database connection pool sizing
   - Remove debug logging code
   - Implement stream throttling
   - Add session management

This hybrid approach will create a more robust EXStreamTV while retaining its unique competitive advantages (AI features, diverse media sources, Python ecosystem).
