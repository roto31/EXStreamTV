# Changelog

All notable changes to EXStreamTV will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [2.6.0] - 2026-01-31

### Added - Tunarr/dizqueTV Integration

This major release integrates proven patterns from Tunarr and dizqueTV projects,
providing enhanced stability, zero-downtime streaming, and intelligent self-healing.

#### Phase 1: Critical Stability Fixes

**DatabaseConnectionManager** (`database/connection.py`):
- Dynamic pool sizing based on channel count: `(channels * 2.5) + 10 base`
- Pool event monitoring for connection lifecycle tracking
- Health checks with latency measurement
- Automatic pool resizing based on load
- `ConnectionMetrics` dataclass for pool statistics

**SessionManager** (`streaming/session_manager.py`) - Tunarr port:
- `StreamSession` dataclass for client connection tracking
- Centralized session lifecycle management
- Idle session cleanup with configurable timeout
- Per-channel session limits
- Error and restart tracking per session

**StreamThrottler** (`streaming/throttler.py`) - dizqueTV port:
- Rate-limits MPEG-TS delivery to target bitrate
- Multiple modes: realtime, burst, adaptive, disabled
- Keepalive packet support during stalls
- Prevents client buffer overruns

#### Phase 2: Error Handling System

**ErrorScreenGenerator** (`streaming/error_screens.py`) - dizqueTV port:
- Visual modes: text, static, test_pattern, slate, custom_image
- Audio modes: silent, sine_wave, white_noise, beep
- FFmpeg command builder for MPEG-TS error streams
- Graceful fallback during stream failures

#### Phase 3: Advanced Scheduling

**TimeSlotScheduler** (`scheduling/time_slots.py`) - Tunarr port:
- Time-of-day based programming slots
- Order modes: ordered, shuffle, random
- Padding modes: none, filler, loop, next
- Flex mode for slot extension

**BalanceScheduler** (`scheduling/balance.py`) - Tunarr port:
- Weight-based content distribution
- Cooldown periods to avoid repetition
- Consecutive play limits
- Distribution tracking and reporting

#### Phase 4: Media Pipeline Improvements

**SubtitleStreamPicker** (`ffmpeg/subtitle_picker.py`) - Tunarr port:
- Language preference matching
- Text vs image subtitle type preference
- SDH/CC detection
- FFmpeg argument generation for burn-in

**AudioStreamPicker** (`ffmpeg/audio_picker.py`) - Tunarr port:
- Language preference matching
- Surround vs stereo preference
- Commentary track handling
- Downmix configuration

#### Phase 5: Database Infrastructure

**DatabaseBackupManager** (`database/backup.py`) - Tunarr port:
- Scheduled automatic backups
- Backup rotation (keep N most recent)
- Gzip compression support
- Pre-restore safety backup
- Manual backup/restore API

#### Phase 6: Enhanced AI Integration

**UnifiedLogCollector** (`ai_agent/unified_log_collector.py`):
- Multi-source log aggregation (app, FFmpeg, Plex, Jellyfin)
- Real-time streaming to AI subscribers
- Ring buffer for context windows
- Log correlation by channel/session
- FFmpeg stderr parsing

**FFmpegAIMonitor** (`ai_agent/ffmpeg_monitor.py`):
- Real-time stderr parsing with progress metrics
- Error classification (12 types) and severity levels
- Per-channel health tracking
- Failure prediction based on trends

**PatternDetector** (`ai_agent/pattern_detector.py`):
- Known pattern matching for common issues
- Root cause analysis
- Failure prediction with confidence scoring
- Learning from outcomes

**AutoResolver** (`ai_agent/auto_resolver.py`):
- Resolution strategies per issue type
- Risk-based approval thresholds
- Zero-downtime execution with fallback streams
- Human escalation for complex issues

#### Phase 7: Configuration and Integration

**New Configuration Classes** (`config.py`):
- `AIAutoHealConfig` - Granular AI feature toggles
- `DatabaseBackupConfig` - Backup settings
- `SessionManagerConfig` - Session limits
- `StreamThrottlerConfig` - Throttling settings

**Application Integration** (`main.py`):
- Initializes all new managers on startup
- Connects components (auto resolver ↔ channel manager)
- Graceful shutdown of all components

**Channel Manager Integration** (`streaming/channel_manager.py`):
- Throttler integration for rate limiting
- Error screen fallback during auto-restart
- AI monitoring integration hooks

### Files Created (12 new files)

| File | Description |
|------|-------------|
| `streaming/session_manager.py` | Tunarr SessionManager port |
| `streaming/throttler.py` | dizqueTV StreamThrottler port |
| `streaming/error_screens.py` | dizqueTV error screen generator |
| `scheduling/time_slots.py` | Tunarr TimeSlotScheduler |
| `scheduling/balance.py` | Tunarr BalanceScheduler |
| `ffmpeg/subtitle_picker.py` | Tunarr SubtitleStreamPicker |
| `ffmpeg/audio_picker.py` | Tunarr AudioStreamPicker |
| `database/backup.py` | DatabaseBackupManager |
| `ai_agent/unified_log_collector.py` | Unified log collection |
| `ai_agent/ffmpeg_monitor.py` | FFmpeg AI monitor |
| `ai_agent/pattern_detector.py` | Pattern detection |
| `ai_agent/auto_resolver.py` | Auto resolution |

### Files Modified (8 files)

| File | Description |
|------|-------------|
| `database/connection.py` | Added DatabaseConnectionManager |
| `config.py` | Added new config classes |
| `main.py` | Initialize new components |
| `streaming/channel_manager.py` | Component integrations |
| `streaming/__init__.py` | New exports |
| `scheduling/__init__.py` | New exports |
| `database/__init__.py` | New exports |
| `ffmpeg/__init__.py` | New exports |

### Component Version Updates

| Component | Version | Last Modified |
|-----------|---------|---------------|
| backend_core | 2.6.0 | 2026-01-31 |
| streaming | 2.6.0 | 2026-01-31 |
| database | 2.6.0 | 2026-01-31 |
| ai_agent | 2.6.0 | 2026-01-31 |
| scheduling | 2.6.0 | 2026-01-31 |
| ffmpeg | 2.6.0 | 2026-01-31 |

---

## [2.5.0] - 2026-01-17

### Added - Block Schedule Database Integration

This release bridges the gap between AI-generated block schedules and the
ErsatzTV-style database block scheduling system. AI channel plans now
properly persist to the database Block, BlockGroup, and BlockItem models.

#### New Components

**BlockScheduleExecutor** (`exstreamtv/ai_agent/block_executor.py`):
- Converts AI `ScheduleBlock` configs to database `Block` entities
- Creates `BlockGroup` to contain all blocks for a channel
- Creates `BlockItem` entities linking blocks to collections
- Handles day-of-week bitmask conversion
- Maps playout modes to playback orders

**CollectionExecutor** (`exstreamtv/ai_agent/collection_executor.py`):
- Persists `CollectionConfig` objects from build plans to database
- Creates smart collections with search queries
- Returns name-to-ID mapping for block linking
- Reuses existing collections when names match

#### Enhanced execute_plan Endpoint

The `/api/ai/channel/plan/{id}/execute` endpoint now:

1. Creates the channel
2. Creates collections from the build plan (via CollectionExecutor)
3. Creates block schedule with BlockGroup, Block, and BlockItem entities
4. Creates ProgramSchedule with settings from plan
5. Creates ProgramScheduleItems linking to blocks
6. Creates and activates the playout

**New Response Fields**:
```json
{
  "success": true,
  "channel_id": 1,
  "schedule_id": 1,
  "playout_id": 1,
  "block_group_id": 1,
  "blocks_created": 5,
  "collections_created": 2,
  "schedule_items_created": 5
}
```

#### Data Flow

```
BuildPlan.schedule.blocks (AI-generated)
    |
    v
BlockScheduleExecutor.execute()
    |
    +-- Create BlockGroup (container)
    |
    +-- For each ScheduleBlock:
    |       |
    |       +-- Create Block (start_time, duration, days_of_week bitmask)
    |       |
    |       +-- Create BlockItem (links to collection)
    |
    v
Database: BlockGroup -> Block -> BlockItem -> Collection
```

#### Day-of-Week Bitmask

Blocks use a bitmask for day scheduling (matching ErsatzTV format):
- Sunday: 1
- Monday: 2
- Tuesday: 4
- Wednesday: 8
- Thursday: 16
- Friday: 32
- Saturday: 64
- All days: 127

### Database Schema Changes

**New Enum** (`exstreamtv/database/models/media.py`):
```python
class CollectionTypeEnum(str, Enum):
    STATIC = "static"   # Manual collection with fixed items
    SMART = "smart"     # Dynamic collection based on search query
    MANUAL = "manual"   # User-curated collection
```

**New Playlist Fields** (`exstreamtv/database/models/playlist.py`):
- `collection_type`: String field ("static", "smart", "manual") - defaults to "static"
- `search_query`: Text field for smart collection query strings

**Migration**: `002_add_collection_smart_fields.py`
- Adds `collection_type` column with index
- Adds `search_query` column

Run migration:
```bash
alembic upgrade head
```

### Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `exstreamtv/ai_agent/block_executor.py` | CREATE | BlockScheduleExecutor class |
| `exstreamtv/ai_agent/collection_executor.py` | CREATE | CollectionExecutor class |
| `exstreamtv/api/ai_channel.py` | MODIFY | Enhanced execute_plan with executors |
| `exstreamtv/ai_agent/__init__.py` | MODIFY | Export new classes |
| `exstreamtv/database/models/media.py` | MODIFY | Add CollectionTypeEnum |
| `exstreamtv/database/models/playlist.py` | MODIFY | Add collection_type and search_query fields |
| `exstreamtv/database/models/__init__.py` | MODIFY | Export CollectionTypeEnum |
| `exstreamtv/database/migrations/versions/002_*.py` | CREATE | Migration for new fields |
| `pyproject.toml` | MODIFY | Version bump to 2.5.0 |

### New Exports

```python
# AI Agent exports
from exstreamtv.ai_agent import (
    BlockScheduleExecutor,
    BlockExecutionResult,
    BlockInfo,
    CollectionExecutor,
    CollectionExecutionResult,
    CollectionInfo,
)

# Database model exports
from exstreamtv.database.models import (
    CollectionTypeEnum,
)
```

---

## [2.4.0] - 2026-01-17

### Added - AI Channel Creator API Endpoints (Phase 12 Continued)

This release adds the complete REST API for the enhanced AI Channel Creator,
enabling programmatic access to persona selection, intent analysis, source
ranking, and build plan generation.

#### New API Endpoints

**Persona Management**:
- `GET /api/ai/channel/personas` - List all 6 available personas
- `GET /api/ai/channel/personas/{id}` - Get specific persona details
- `GET /api/ai/channel/personas/{id}/welcome` - Get persona's welcome message

**Intent Analysis**:
- `POST /api/ai/channel/analyze` - Analyze natural language request
  - Extracts purpose, genres, era, scheduling preferences
  - Suggests best persona for the request
  - Returns clarification questions if needed

**Source Selection**:
- `POST /api/ai/channel/sources` - Get ranked media sources
  - Filter by genres, content types, era, year range
  - Returns rankings with scores and match quality
  - Recommends optimal source combinations

**Build Plan Management**:
- `POST /api/ai/channel/plan` - Generate complete build plan
  - Accepts natural language request
  - Specifies persona and source preferences
  - Returns full plan with warnings and estimates
- `GET /api/ai/channel/plan/{id}` - Get existing plan
- `PUT /api/ai/channel/plan/{id}` - Modify plan
- `POST /api/ai/channel/plan/{id}/approve` - Approve plan for execution
- `POST /api/ai/channel/plan/{id}/execute` - Execute approved plan
- `DELETE /api/ai/channel/plan/{id}` - Delete/cancel plan

**Enhanced Sessions**:
- `POST /api/ai/channel/start-with-persona` - Start session with specific persona
  - Returns persona-specific welcome message
  - Includes persona metadata for UI

#### Request/Response Models Added

```python
# Persona
PersonaInfoResponse  # Full persona details with icon/color

# Intent Analysis
AnalyzeIntentRequest   # Natural language request
AnalyzeIntentResponse  # Parsed intent with suggestions

# Sources
GetSourcesRequest      # Filter criteria
SourceRankingResponse  # Individual source ranking
GetSourcesResponse     # Complete source rankings

# Build Plans
GeneratePlanRequest    # Request with persona and preferences
BuildPlanResponse      # Complete plan details
ModifyPlanRequest      # Modifications to apply
ApprovePlanRequest     # Plan approval

# Sessions
StartSessionWithPersonaRequest   # Session with persona
StartSessionWithPersonaResponse  # Session + persona info
```

#### Enhanced UI - Persona Selector and Build Plan Preview

- `exstreamtv/templates/ai_channel.html` - Enhanced with new features (Modified: 2026-01-17)
  - **Persona Selector Grid**: Visual persona selection before starting session
    - Shows all 6 personas with icons, colors, and specialties
    - Click to select and start conversation with chosen expert
  - **Dynamic Header**: Updates to show selected persona's name and title
  - **Change Persona Button**: Switch personas mid-conversation (starts new session)
  - **Enhanced Preview Panel**: 
    - Improved styling with section icons
    - Source badges with primary indicator
    - Better visual hierarchy
  - **New CSS Styles**:
    - `.persona-selector`, `.persona-grid`, `.persona-card`
    - `.plan-section`, `.plan-warning`
    - `.source-badge`, `.btn-ghost`

#### MethodSelector - Creation Method Selection

New module `exstreamtv/ai_agent/method_selector.py` for choosing the optimal channel creation approach:

- **CreationMethod enum**: DIRECT_API, SCRIPTED_BUILD, YAML_IMPORT, M3U_IMPORT, TEMPLATE_BASED, HYBRID
- **MethodComplexity enum**: SIMPLE, MODERATE, COMPLEX, ADVANCED
- **MethodRecommendation**: Scored recommendation with requirements and steps
- **MethodSelectionResult**: Complete selection with alternatives and fallback

**Features**:
- Evaluates all creation methods against intent and sources
- Scores each method based on complexity, requirements, and fit
- Provides detailed step-by-step instructions for each method
- Suggests Archive.org templates when applicable
- Falls back to simpler methods when complex ones fail

#### DecoIntegrator - Channel Decoration

New module `exstreamtv/ai_agent/deco_integrator.py` for channel decoration elements:

- **DecoType enum**: WATERMARK, BUMPER, STATION_ID, INTERSTITIAL, LOWER_THIRD
- **WatermarkConfig**: Position, opacity, style, size settings
- **BumperConfig**: Pre/post program transitions with video/audio paths
- **StationIdConfig**: Periodic station identification clips
- **InterstitialConfig**: Promos, PSAs, educational content

**Theme Presets**:
- `classic_network` - Traditional broadcast style
- `cable_channel` - Cable TV with prominent branding
- `streaming` - Modern minimal decoration
- `retro_tv` - Vintage TV experience
- `movie_channel` - Movie channel with minimal interruption
- `kids_channel` - Child-friendly with educational content
- `sports_channel` - Sports network style
- `documentary` - Documentary channel

**Archive.org Collections**:
- Era-specific bumpers (1970s, 1980s, 1990s)
- Network/cable/public station IDs
- PSAs, promos, educational interstitials

### Files Modified
| File | Description |
|------|-------------|
| `exstreamtv/api/ai_channel.py` | Added 12 new endpoints, 10 new models |
| `exstreamtv/templates/ai_channel.html` | Added persona selector, enhanced preview |
| `exstreamtv/ai_agent/method_selector.py` | **NEW** - Method selection logic |
| `exstreamtv/ai_agent/deco_integrator.py` | **NEW** - Decoration configuration |
| `exstreamtv/ai_agent/__init__.py` | Added new exports |
| `pyproject.toml` | Version bump to 2.4.0 |

### API Usage Examples

**Analyze Intent**:
```bash
curl -X POST http://localhost:8000/api/ai/channel/analyze \
  -H "Content-Type: application/json" \
  -d '{"request": "Create a classic 80s sports channel with NFL games"}'
```

**Generate Build Plan**:
```bash
curl -X POST http://localhost:8000/api/ai/channel/plan \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Classic sports channel with NFL and NBA from the 80s and 90s",
    "persona_id": "sports_expert",
    "preferred_sources": ["plex", "youtube"]
  }'
```

**Approve and Execute**:
```bash
# Approve
curl -X POST http://localhost:8000/api/ai/channel/plan/{plan_id}/approve

# Execute
curl -X POST http://localhost:8000/api/ai/channel/plan/{plan_id}/execute
```

### Complete API Endpoint Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ai/channel/personas` | List all personas |
| GET | `/api/ai/channel/personas/{id}` | Get persona details |
| GET | `/api/ai/channel/personas/{id}/welcome` | Get welcome message |
| POST | `/api/ai/channel/analyze` | Analyze intent |
| POST | `/api/ai/channel/sources` | Get ranked sources |
| POST | `/api/ai/channel/plan` | Generate plan |
| GET | `/api/ai/channel/plan/{id}` | Get plan |
| PUT | `/api/ai/channel/plan/{id}` | Modify plan |
| POST | `/api/ai/channel/plan/{id}/approve` | Approve plan |
| POST | `/api/ai/channel/plan/{id}/execute` | Execute plan |
| DELETE | `/api/ai/channel/plan/{id}` | Delete plan |
| POST | `/api/ai/channel/start-with-persona` | Start session with persona |

---

## [2.3.0] - 2026-01-17

### Added - AI Channel Creator Infrastructure (Phase 12 Continued)

This release adds the core infrastructure for the Universal AI Channel Creator,
providing the foundation for intelligent, persona-driven channel building.

#### Persona Management System (NEW)
- `exstreamtv/ai_agent/persona_manager.py` - Central persona management (Created: 2026-01-17)
  - `PersonaType` enum for all 6 persona types
  - `PersonaInfo` dataclass with metadata, icons, and colors for UI
  - `PersonaContext` for session-based persona state
  - `PersonaManager` class with:
    - `get_all_personas()` - List all available personas
    - `get_persona_info()` - Get details about a persona
    - `create_context()` / `get_context()` - Session management
    - `switch_persona()` - Change personas mid-session
    - `build_prompt()` - Build persona-specific prompts
    - `suggest_persona()` - Auto-suggest persona based on request
    - `get_persona_for_content_type()` - Match persona to content

#### Intent Analysis System (NEW)
- `exstreamtv/ai_agent/intent_analyzer.py` - Natural language intent parsing (Created: 2026-01-17)
  - `ChannelPurpose` enum (entertainment, sports, movies, kids, documentary, tech, etc.)
  - `PlayoutPreference` enum (continuous, scheduled, shuffle, loop, flood)
  - `ContentEra` enum (classic, golden_age, modern_classic, contemporary)
  - `AnalyzedIntent` comprehensive dataclass containing:
    - Purpose and confidence score
    - Content preferences (genres, era, year range, keywords)
    - Scheduling preferences (dayparts, days, holiday awareness)
    - Source hints (Plex, Archive.org, YouTube preferences)
    - Filler preferences (commercials, bumpers, style)
    - Mentioned entities (shows, movies, genres, years)
    - Clarification flags and questions
  - `IntentAnalyzer` class with keyword extraction and scoring

#### Source Selection System (NEW)
- `exstreamtv/ai_agent/source_selector.py` - Media source ranking (Created: 2026-01-17)
  - `SourceType` enum (plex, jellyfin, emby, local, archive_org, youtube, m3u)
  - `ContentMatch` enum (excellent, good, fair, poor, none)
  - `SourceRanking` dataclass with scores, matching details, warnings
  - `SourceSelectionResult` with primary/secondary sources and recommendations
  - `SourceSelector` class with:
    - Async source querying
    - Genre and era affinity scoring
    - Archive.org collection mapping
    - YouTube content type matching
    - Recommended source combination generation

#### Build Plan Generator (NEW)
- `exstreamtv/ai_agent/build_plan_generator.py` - Complete build plan generation (Created: 2026-01-17)
  - `BuildStatus` enum (draft, ready, approved, building, complete, failed)
  - Configuration dataclasses:
    - `ChannelConfig` - Channel settings
    - `CollectionConfig` - Smart collection setup
    - `ScheduleBlock` / `ScheduleConfig` - Schedule structure
    - `FillerConfig` - Commercial/bumper settings
    - `DecoConfig` - Watermark/station ID settings
    - `ModuleUsage` - Which EXStreamTV modules to use
  - `BuildPlan` comprehensive dataclass with:
    - All configurations
    - Source selection results
    - Intent analysis
    - Warnings and notes
    - Content estimates
    - Ready/approval status
  - `BuildPlanGenerator` class with:
    - `generate()` - Create complete build plan from intent
    - `modify_plan()` - Modify existing plans
    - Daypart templates for different channel types
    - Archive.org collection mapping

### Files Created
| File | Lines | Description |
|------|-------|-------------|
| `exstreamtv/ai_agent/persona_manager.py` | ~380 | Persona management system |
| `exstreamtv/ai_agent/intent_analyzer.py` | ~520 | Intent analysis from natural language |
| `exstreamtv/ai_agent/source_selector.py` | ~420 | Source ranking and selection |
| `exstreamtv/ai_agent/build_plan_generator.py` | ~500 | Build plan generation |

### Files Modified
| File | Description |
|------|-------------|
| `exstreamtv/ai_agent/__init__.py` | Updated to v2.3.0, added all new exports |
| `pyproject.toml` | Version bump to 2.3.0 |

### Architecture Overview

```
User Request
    │
    ▼
┌─────────────────┐
│ IntentAnalyzer  │──▶ AnalyzedIntent
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ PersonaManager  │──▶ Select appropriate persona
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ SourceSelector  │──▶ Rank available sources
└─────────────────┘
    │
    ▼
┌──────────────────────┐
│ BuildPlanGenerator   │──▶ Complete BuildPlan
└──────────────────────┘
    │
    ▼
┌─────────────────┐
│ User Approval   │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Execute Build   │──▶ Channel Created
└─────────────────┘
```

### Usage Example

```python
from exstreamtv.ai_agent import (
    PersonaManager,
    PersonaType,
    IntentAnalyzer,
    SourceSelector,
    BuildPlanGenerator,
)

# Analyze user request
analyzer = IntentAnalyzer()
intent = analyzer.analyze("Create a classic sports channel with NFL games from the 80s")

# Get recommended persona
persona_mgr = PersonaManager()
persona = persona_mgr.suggest_persona(intent.raw_request)
# Returns: PersonaType.SPORTS_EXPERT

# Select sources
selector = SourceSelector()
sources = await selector.select_sources(
    genres=intent.content.genres,
    era=intent.content.era.value,
)

# Generate build plan
generator = BuildPlanGenerator()
plan = generator.generate(intent, sources, persona.value)

# Review plan
print(plan.to_dict())
# {
#     "plan_id": "...",
#     "status": "ready",
#     "channel": {"name": "Classic Sports Classics", ...},
#     "collections": [...],
#     "schedule": {...},
#     "warnings": [...],
# }

# Approve and build
if plan.is_ready():
    plan.approve()
    # Execute build...
```

---

## [2.2.0] - 2026-01-17

### Added - Complete AI Persona Suite (Phase 12 Complete)

#### Three Additional Personas Added

This release completes the AI Channel Creator persona suite, adding three more specialized
personas for comprehensive channel creation capabilities.

#### Movie Critics Persona (NEW)
- `exstreamtv/ai_agent/prompts/movie_critic.py` - Siskel & Ebert style film critics (Created: 2026-01-17)
  - **Characters**: Vincent Marlowe & Clara Fontaine - legendary film critics who debate and collaborate
  - **Style**: Dual perspective with Vincent (traditionalist) vs Clara (adventurous) dynamics
  - **Expertise**: Film history, directors, genres, international cinema, film movements
  - **Special Features**:
    - `FILM_GENRES` - Genre database with classic examples and Archive.org availability
    - `CLASSIC_DIRECTORS` - Director database (Hitchcock, Kubrick, Wilder, Kurosawa, etc.)
    - `FILM_MOVEMENTS` - French New Wave, Italian Neorealism, German Expressionism, etc.
    - `ARCHIVE_ORG_FILM_COLLECTIONS` - Film noir, silent films, public domain features
    - Double feature and marathon programming logic
    - Thematic pairing recommendations

#### Kids Programming Expert Persona (NEW)
- `exstreamtv/ai_agent/prompts/kids_expert.py` - Children's media specialist (Created: 2026-01-17)
  - **Character**: Professor Patricia "Pepper" Chen - PhD in Children's Media Studies
  - **Specialization**: Disney, Pixar, educational programming, age-appropriate content
  - **Expertise**: All Disney eras, PBS Kids, Nickelodeon, Cartoon Network, classic cartoons
  - **Special Features**:
    - `DISNEY_CONTENT` - All Disney eras from Golden Age to Revival
    - `PIXAR_FILMS` - Complete Pixar filmography with metadata
    - `CLASSIC_CARTOONS` - Looney Tunes, Hanna-Barbera, Fleischer, Disney shorts
    - `EDUCATIONAL_SHOWS` - Sesame Street, Mister Rogers, Magic School Bus
    - `HOLIDAY_SPECIALS` - Christmas, Halloween, Thanksgiving classics
    - `YOUTUBE_KIDS_CHANNELS` - Safe, appropriate YouTube content
    - Age-band targeting (preschool, elementary, tween)
    - Content safety and rating awareness

#### PBS Programming Expert Persona (NEW)
- `exstreamtv/ai_agent/prompts/pbs_expert.py` - Public television historian (Created: 2026-01-17)
  - **Character**: Dr. Eleanor Marsh - 30-year PBS veteran, VP of National Programming
  - **Philosophy**: Mission-driven, educational, culturally enriching content
  - **Expertise**: Documentaries, British imports, cultural programming, educational TV
  - **Special Features**:
    - `PBS_DOCUMENTARY_SERIES` - Frontline, NOVA, American Experience, Nature, POV
    - `KEN_BURNS_DOCUMENTARIES` - Complete Ken Burns filmography with metadata
    - `BRITISH_IMPORTS` - Masterpiece Theatre mysteries and dramas
    - `CULTURAL_PROGRAMMING` - Great Performances, Austin City Limits, American Masters
    - `PBS_KIDS_CLASSICS` - Sesame Street, Mister Rogers, Reading Rainbow
    - `PUBLIC_AFFAIRS` - PBS NewsHour, Washington Week, Firing Line
    - `ARCHIVE_ORG_EDUCATIONAL` - Prelinger, AV Geeks, Computer Chronicles
    - PBS-style scheduling (thoughtful pacing, longer-form content)

### Complete Persona Registry (6 Total)

| ID | Character Name | Title | Specialties |
|----|---------------|-------|-------------|
| `tv_executive` | Max Sterling | TV Programming Executive | Classic TV, scheduling, dayparts |
| `sports_expert` | Howard "The Stat" Kowalski | Sports Savant | Sports, classic games, YouTube, Archive.org |
| `tech_expert` | Steve "Woz" Nakamura | Tech Savant | Apple, computing, keynotes, retro tech |
| `movie_critic` | Vincent Marlowe & Clara Fontaine | Movie Critics | Film history, directors, genres, marathons |
| `kids_expert` | Professor Pepper Chen | Kids Expert | Disney, Pixar, educational, animation |
| `pbs_expert` | Dr. Eleanor Marsh | PBS Expert | Documentary, PBS, British drama, educational |

### Files Created
| File | Lines | Description |
|------|-------|-------------|
| `exstreamtv/ai_agent/prompts/movie_critic.py` | ~450 | Movie Critics persona with film database |
| `exstreamtv/ai_agent/prompts/kids_expert.py` | ~420 | Kids Expert persona with Disney/educational data |
| `exstreamtv/ai_agent/prompts/pbs_expert.py` | ~430 | PBS Expert persona with documentary data |

### Files Modified
| File | Description |
|------|-------------|
| `exstreamtv/ai_agent/prompts/__init__.py` | Updated to v2.2.0, added 3 new personas to registry |
| `pyproject.toml` | Version bump to 2.2.0 |

### Usage Example

```python
from exstreamtv.ai_agent.prompts import get_persona, list_personas

# List all 6 available personas
personas = list_personas()
# Returns: tv_executive, sports_expert, tech_expert, movie_critic, kids_expert, pbs_expert

# Get the movie critic persona
critics = get_persona("movie_critic")
welcome = critics["get_welcome"]()  # Get character intro (Vincent & Clara debating)

# Access persona-specific data
film_genres = critics["data"]["genres"]
directors = critics["data"]["directors"]

# Get PBS expert for documentary channel
pbs = get_persona("pbs_expert")
ken_burns = pbs["data"]["ken_burns"]  # Ken Burns filmography
```

---

## [2.1.0] - 2026-01-17

### Added - AI Channel Creator Personas (Phase 12)

#### New Persona System
- `exstreamtv/ai_agent/prompts/__init__.py` - Enhanced with persona registry and dynamic selection (Modified: 2026-01-17)
  - `PERSONAS` registry for all available personas
  - `get_persona(persona_id)` function for retrieving persona by ID
  - `list_personas()` function for listing all available personas
  - Unified export of all persona modules

#### Sports Savant Persona (NEW)
- `exstreamtv/ai_agent/prompts/sports_expert.py` - Schwab-style sports historian (Created: 2026-01-17)
  - **Character**: Howard "The Stat" Kowalski - legendary sports statistician
  - **Inspiration**: Howie Schwab from ESPN's "Stump the Schwab" (2004-2006)
  - **Expertise**: NFL, NBA, MLB, NHL, NCAA, Olympics, Boxing, Soccer
  - **Sources**: YouTube official sports channels, Archive.org vintage broadcasts
  - **Special Features**:
    - `YOUTUBE_SPORTS_CHANNELS` - Known sports channel registry (NFL Throwback, NBA, MLB Vault)
    - `ARCHIVE_ORG_SPORTS_COLLECTIONS` - Vintage sports broadcast locations
    - `SPORTS_DOCUMENTARY_SERIES` - 30 for 30, NFL Films, A Football Life metadata
    - `SPORTS_MOVIES` - Sports movie database by sport category
    - `build_sports_channel_prompt()` - Sports-specific channel creation prompts
    - `build_sports_schedule_prompt()` - Game-length-aware schedule generation
    - `get_sports_welcome_message()` - Character introduction message

#### Tech Savant Persona (NEW)
- `exstreamtv/ai_agent/prompts/tech_expert.py` - Apple specialist and tech historian (Created: 2026-01-17)
  - **Character**: Steve "Woz" Nakamura - legendary tech historian
  - **Specialization**: Apple Inc. products, keynotes, commercials, and culture
  - **Expertise**: Personal computing history, Silicon Valley, consumer electronics
  - **Sources**: YouTube (Apple, retro tech channels), Archive.org (Computer Chronicles)
  - **Special Features**:
    - `APPLE_KEYNOTES` - Complete Apple keynote archive metadata (1984-present)
    - `APPLE_COMMERCIALS` - Campaign database (1984, Think Different, Get a Mac, etc.)
    - `YOUTUBE_TECH_CHANNELS` - Official, retro tech, and reviewer channel registry
    - `ARCHIVE_ORG_TECH_COLLECTIONS` - Computer Chronicles, Prelinger, BBS Documentary
    - `TECH_DOCUMENTARIES` - Tech documentary database (Apple, industry, gaming)
    - `build_tech_channel_prompt()` - Tech-specific channel creation prompts
    - `build_tech_schedule_prompt()` - Keynote-length-aware schedule generation
    - `get_tech_welcome_message()` - Character introduction message

### Persona Registry

| ID | Character Name | Title | Specialties |
|----|---------------|-------|-------------|
| `tv_executive` | Max Sterling | TV Programming Executive | Classic TV, scheduling, dayparts |
| `sports_expert` | Howard "The Stat" Kowalski | Sports Savant | Sports, classic games, YouTube, Archive.org |
| `tech_expert` | Steve "Woz" Nakamura | Tech Savant | Apple, computing, keynotes, retro tech |

### Files Created
| File | Type | Description |
|------|------|-------------|
| `exstreamtv/ai_agent/prompts/sports_expert.py` | Created | Sports Savant persona module |
| `exstreamtv/ai_agent/prompts/tech_expert.py` | Created | Tech Savant persona module |

### Files Modified
| File | Type | Description |
|------|------|-------------|
| `exstreamtv/ai_agent/prompts/__init__.py` | Enhanced | Persona registry and exports |
| `pyproject.toml` | Modified | Version bump to 2.1.0 |

### Usage Example

```python
from exstreamtv.ai_agent.prompts import get_persona, list_personas

# List all available personas
personas = list_personas()
# [
#   {"id": "tv_executive", "name": "Max Sterling", ...},
#   {"id": "sports_expert", "name": "Howard 'The Stat' Kowalski", ...},
#   {"id": "tech_expert", "name": "Steve 'Woz' Nakamura", ...},
# ]

# Get a specific persona
sports = get_persona("sports_expert")
welcome = sports["get_welcome"]()  # Get character intro
prompt = sports["build_prompt"](user_message, history, media)
```

---

## [2.0.1] - 2026-01-17

### Added - Media Filtering & UI Improvements

#### Media Library Filters
- `exstreamtv/api/media.py` - Comprehensive media filtering system (Created: 2026-01-17)
  - New filter parameters: `media_type`, `year`, `year_min`, `year_max`, `duration_min`, `duration_max`, `content_rating`, `genre`, `search`
  - Sorting support: `sort_by` (title, year, duration, added_date) and `sort_order` (asc, desc)
  - NULL-safe sorting with `nullslast()` for proper year/duration ordering
- `GET /api/media/filters` endpoint - Returns available filter options dynamically based on current media (Created: 2026-01-17)
  - Returns: years, year_ranges (decades), media_types, content_ratings, sources, duration_ranges

#### Media Response Enhancements
- Extended `media_to_response()` with additional fields (Modified: 2026-01-17):
  - `media_type`, `year`, `content_rating`, `genres`, `studio`
  - `show_title`, `season_number`, `episode_number`
  - `poster_path`, `art_url`, `added_date`, `originally_available`, `rating`

#### Server Management Scripts (Created: 2026-01-17)
- `start.sh` - Start the server (fails if already running)
- `restart.sh` - Stop existing server and start fresh  
- `stop.sh` - Stop the running server
- Features: Color-coded output, auto-creates config.yaml from example

#### UI Filter Panel (Created: 2026-01-17)
- `exstreamtv/templates/media.html` - Collapsible advanced filters panel
  - Filter dropdowns: Type, Year (with decade ranges), Duration, Content Rating
  - Genre text input with debounce
  - Sort controls with ascending/descending toggle
  - Active filter count badge
  - "Clear All Filters" button

#### Dynamic Episode Fetching (Created: 2026-01-17)
- `fetchMediaItem(id)` function - Fetches episode data from API when not in allMedia array
- Enables slide-out panel for TV show episodes loaded on-demand

### Fixed

#### Critical Bug Fixes (Fixed: 2026-01-17)
- **Missing `</div>` tag** - Filters panel div was unclosed, hiding entire content area when filters collapsed
- **Grid class not reset** - `renderTVShows()` changed grid class to 'shows-grid' but never reset to 'media-grid', causing full-width cards when switching libraries
- **View mode wrong variable** - `setViewMode()` was rendering empty `filteredMedia` instead of `allMedia`
- **Missing loading element** - Added `<div id="loading">` with spinner that was referenced in JS but missing from HTML
- **Slide-out not finding items** - `selectMedia()` only searched `allMedia`; TV show episodes now fetched via API

#### UI Fixes (Fixed: 2026-01-17)
- **Poster cropping in detail panel** - Changed `.detail-poster` from `aspect-ratio: 16/9` with `object-fit: cover` to `max-height: 400px` with `object-fit: contain` to show full artwork
- **Content area layout** - Added `.content-area` CSS with `flex: 1` for proper expansion in flex container
- **Loading state styles** - Added `.loading-state` and `.loading-spinner` CSS with spin animation

### Changed

#### Constants (Modified: 2026-01-17)
- `exstreamtv/constants.py` - Added missing EPG constants:
  - `EPG_MAX_PROGRAMMES_PER_CHANNEL = 100`
  - `EPG_QUERY_LIMIT = 500`
  - `EPG_TITLE_TRUNCATE_LENGTH = 100`
  - `MAX_EPG_ITEMS_PER_CHANNEL = 100`

#### Database Models (Fixed: 2026-01-17)
- `exstreamtv/database/models/media.py` - Fixed `MultiCollectionLink.collection_id` foreign key from `collections.id` to `playlists.id` (correct table reference)

### Files Modified
| File | Type | Date |
|------|------|------|
| `exstreamtv/api/media.py` | Enhanced | 2026-01-17 |
| `exstreamtv/templates/media.html` | Enhanced | 2026-01-17 |
| `exstreamtv/constants.py` | Enhanced | 2026-01-17 |
| `exstreamtv/database/models/media.py` | Fixed | 2026-01-17 |
| `start.sh` | Created | 2026-01-17 |
| `restart.sh` | Created | 2026-01-17 |
| `stop.sh` | Created | 2026-01-17 |

---

## [2.0.0] - 2026-01-14

### Added - ErsatzTV-Compatible API Integration

#### Blocks API
- `exstreamtv/api/blocks.py` - Time-based programming blocks
- Block groups for organizing related blocks
- Day-of-week scheduling with bitmask support
- Block items with collection references and playback order

#### Filler Presets API
- `exstreamtv/api/filler_presets.py` - Gap-filling content management
- Three filler modes: duration, count, and pad-to-boundary
- Weighted item selection
- Collection and individual media item support

#### Templates API
- `exstreamtv/api/templates.py` - Reusable schedule patterns
- Template groups for organization
- Time slot definitions with block or collection references
- Apply templates to channels with single endpoint

#### Deco API
- `exstreamtv/api/deco.py` - Decorative content (bumpers, station IDs)
- Five deco types: bumper, commercial, station_id, promo, credits
- Deco groups for channel branding organization
- Weighted selection for variety

#### Scripted Schedule API
- `exstreamtv/api/scripted.py` - Programmatic playout building
- 27 endpoints for complete schedule control
- Content addition: collections, marathons, playlists, search results
- Timing controls: pad-to-next, pad-until, wait-until
- Display controls: EPG grouping, watermark, graphics toggles

#### New Models
- `MultiCollection` and `MultiCollectionLink` for combining collections
- `PlayoutBuildSession` for persistent build state

#### API Enhancements
- Channel filler and deco configuration endpoints
- Channel programming guide endpoint
- Playout build session management (start, commit, cancel)
- Smart collection creation and refresh
- Multi-collection CRUD operations

#### WebUI
- Blocks management page with group support
- Filler presets page with mode-specific fields
- Templates page with enable/disable toggles
- Deco page with type badges and grouping
- Updated navigation with new menu items

#### Documentation
- Comprehensive API documentation covering all endpoints
- Written for accessibility at 12th grade reading level
- Quick reference tables for common operations

---

## [2.0.0] - 2026-01-14

### Added - Additional Integrations (Phase 11)

#### IPTV Source System
- `exstreamtv/integration/iptv_sources.py` - IPTV provider integration
- M3U/M3U8 playlist parsing with auto-refresh
- Xtream Codes API support
- Multi-source management with filtering
- Channel group and name pattern filters

#### HDHomeRun Tuner Input
- `exstreamtv/integration/hdhomerun_tuner.py` - Physical tuner support
- SSDP-based device discovery
- Channel lineup import
- Stream URL generation
- Tuner status monitoring

#### Notification Services
- `exstreamtv/integration/notifications.py` - Push notification system
- Discord webhook integration
- Telegram bot API support
- Pushover notifications
- Slack webhook support
- Multi-service routing with priority filtering

#### Home Assistant Integration
- `exstreamtv/integration/homeassistant.py` - Smart home support
- Media player entity
- Server status and stream count sensors
- Event firing for automations
- Entity state synchronization

#### Plugin System
- `exstreamtv/integration/plugins.py` - Extensibility framework
- Plugin discovery and lifecycle management
- Source, Provider, and Notification plugin types
- Hook system for events
- Manifest-based metadata

#### Cloud Storage
- `exstreamtv/integration/cloud_storage.py` - Cloud media streaming
- Google Drive with OAuth2
- Dropbox API integration
- S3/Backblaze B2 support
- Presigned URL generation for streaming

#### Integration API
- `exstreamtv/api/integrations.py` - API endpoints for all integrations
- Full CRUD for IPTV sources
- HDHomeRun device management
- Notification service configuration
- Home Assistant setup
- Cloud provider management
- Plugin control

### Milestone
- **v2.0.0 Release** - All 11 phases complete!
- Full feature parity with ErsatzTV
- Enhanced with StreamTV's AI agent and Apple Design UI

---

## [1.8.0] - 2026-01-14

### Added - Performance Optimization (Phase 10)

#### Caching Layer
- `exstreamtv/cache/` - Complete caching subsystem
- In-memory LRU cache with TTL and compression
- Optional Redis backend for distributed deployments
- Cache decorators (@cached, @invalidate_cache)
- Type-specific caching (EPG, M3U, metadata, FFprobe results)

#### Database Optimization
- `exstreamtv/database/optimization.py` - Query optimization utilities
- Performance indexes for frequently queried columns
- Optimized connection pooling with tuning options
- SQLite WAL mode for better concurrency
- Batch operations for bulk inserts/updates

#### FFmpeg Process Pooling
- `exstreamtv/ffmpeg/process_pool.py` - FFmpeg process manager
- Semaphore-based concurrency limiting
- Process health monitoring with CPU/memory tracking
- Graceful shutdown and error callbacks

#### Background Task System
- `exstreamtv/tasks/` - Async task queue system
- Priority-based task execution
- Task deduplication and retry with backoff
- Periodic task scheduler
- Task decorators (@background_task, @scheduled_task)

#### API Performance Middleware
- `exstreamtv/middleware/performance.py` - Performance middleware
- Gzip compression for API responses
- ETag support with 304 responses
- Request timing and slow query logging
- Token bucket rate limiting

#### Performance Monitoring API
- `exstreamtv/api/performance.py` - Performance endpoints
- Comprehensive statistics endpoint
- Cache, database, FFmpeg, and task stats
- Slow request tracking
- Performance health checks

---

## [1.6.0] - 2026-01-14

### Added - Documentation & Release (Phase 9)

#### User Guides
- `docs/guides/INSTALLATION.md` - Complete installation guide for all platforms
- `docs/guides/QUICK_START.md` - Getting started in under 10 minutes
- `docs/guides/HW_TRANSCODING.md` - Hardware transcoding setup and optimization
- `docs/guides/LOCAL_MEDIA.md` - Local media library configuration

#### API Documentation
- `docs/api/README.md` - Comprehensive REST API reference
- All endpoints documented with examples
- SDK examples (Python, JavaScript, curl)

#### Contributing
- `CONTRIBUTING.md` - Contributor guidelines
- Code standards and testing requirements
- Pull request process

---

## [1.5.0] - 2026-01-14

### Added - Testing Suite (Phase 8)

#### Test Infrastructure
- `pytest.ini` - Pytest configuration with markers
- `tests/conftest.py` - Shared fixtures and async setup

#### Unit Tests
- `tests/unit/test_config.py` - Configuration loading tests
- `tests/unit/test_database_models.py` - SQLAlchemy model tests
- `tests/unit/test_scanner.py` - File scanner tests
- `tests/unit/test_libraries.py` - Library abstraction tests

#### Integration Tests
- `tests/integration/test_api_channels.py` - Channel API tests
- `tests/integration/test_api_playlists.py` - Playlist API tests
- `tests/integration/test_api_dashboard.py` - Dashboard API tests

#### End-to-End Tests
- `tests/e2e/test_channel_workflow.py` - Full channel creation workflow
- `tests/e2e/test_health_workflow.py` - Health check and monitoring

#### Test Fixtures
- `tests/fixtures/factories.py` - Test data factories
- `tests/fixtures/mock_responses/` - Mock API responses (Plex, Jellyfin, TMDB)

---

## [1.4.0] - 2026-01-14

### Added - macOS App Enhancement (Phase 7)

#### Native macOS Menu Bar App
- `EXStreamTVApp/Package.swift` - Swift Package Manager configuration
- `EXStreamTVApp/Sources/EXStreamTVApp.swift` - SwiftUI app entry point
- `EXStreamTVApp/Sources/AppDelegate.swift` - App delegate with notifications

#### Services
- `Services/ServerManager.swift` - Python server lifecycle management
- `Services/ChannelManager.swift` - Channel status monitoring

#### Views
- `Views/MenuBarView.swift` - Menu bar interface with channel status
- `Views/SettingsView.swift` - Preferences (server, channels, notifications)
- `Views/DashboardWindowView.swift` - Floating dashboard window
- `Views/AboutView.swift` - About panel

#### Utilities
- `Utilities/Extensions.swift` - Swift extensions for formatting
- `Utilities/Logger.swift` - Unified logging

#### Resources
- `Info.plist` - App configuration
- `EXStreamTV.entitlements` - App sandbox and network permissions
- `Assets.xcassets` - App icons and assets

---

## [1.3.0] - 2026-01-14

### Added - WebUI Extensions (Phase 6)

#### Dashboard Enhancements
- `exstreamtv/api/dashboard.py` - Dashboard statistics API
- `exstreamtv/templates/dashboard.html` - Enhanced dashboard with live stats
- System resource monitoring (CPU, memory, disk)
- Active stream tracking

#### New WebUI Pages
- `templates/guide.html` - EPG/Program Guide with timeline view
- `templates/media_browser.html` - Media browser with filters
- `templates/schedule_builder.html` - Visual schedule builder
- `templates/system_monitor.html` - System resource monitoring
- `templates/channel_editor.html` - Channel configuration editor
- `templates/libraries.html` - Library management UI

#### Route Integration
- Added routes for all new pages in `main.py`
- Navigation links updated in base template

---

## [1.2.0] - 2026-01-14

### Added - Local Media Libraries (Phase 4)

#### Library Abstractions
- `exstreamtv/media/libraries/base.py` - BaseLibrary ABC with LibraryManager
- `exstreamtv/media/libraries/local.py` - Local folder library implementation
- `exstreamtv/media/libraries/plex.py` - Plex Media Server integration
- `exstreamtv/media/libraries/jellyfin.py` - Jellyfin & Emby integration

#### Media Scanning
- `exstreamtv/media/scanner/base.py` - Scanner base class and data types
- `exstreamtv/media/scanner/ffprobe.py` - FFprobe media analysis
- `exstreamtv/media/scanner/file_scanner.py` - Concurrent file discovery

#### Metadata Providers
- `exstreamtv/media/providers/base.py` - Provider interface
- `exstreamtv/media/providers/tmdb.py` - TMDB movies and TV
- `exstreamtv/media/providers/tvdb.py` - TVDB TV series
- `exstreamtv/media/providers/nfo.py` - NFO file parser

#### Collections
- `exstreamtv/media/collections.py` - Show/season/movie collection organizer

#### API Routes
- `exstreamtv/api/libraries.py` - Library CRUD and scan endpoints
- `exstreamtv/api/media.py` - Media item management

#### Database Models
- `exstreamtv/database/models/library.py` - Library source models
- `exstreamtv/database/models/media.py` - MediaItem, MediaVersion, MediaFile

---

## [1.0.9] - 2026-01-14

### Added - ErsatzTV Playout Engine (Phase 5)

#### Playout Builder
- `exstreamtv/playout/builder.py` - Main playout construction
- Build modes: continue, refresh, reset
- Enumerator management and state persistence

#### Collection Enumerators
- `ChronologicalEnumerator` - Ordered playback
- `ShuffledEnumerator` - Shuffled with state persistence
- `RandomEnumerator` - Random with repeat avoidance
- `RotatingShuffledEnumerator` - Group-based rotation

#### Schedule Modes
- `ONE` - Play one item per schedule slot
- `MULTIPLE` - Play N items per slot
- `DURATION` - Play for specified duration
- `FLOOD` - Fill until target time

#### Filler System
- `FillerManager` - Filler content selection
- Pre-roll, mid-roll, post-roll modes
- Tail filler for gap filling
- Pad to minute boundary option

#### State Management
- `PlayoutState` - Current playout tracking
- `PlayoutItem` - Individual playout entries
- `PlayoutAnchor` - Position persistence

---

## [1.0.8] - 2026-01-14

### Added - ErsatzTV FFmpeg Pipeline Features (Phase 3)

#### State Management
- `exstreamtv/ffmpeg/state/frame_state.py` - Frame tracking (size, format, location)
- `exstreamtv/ffmpeg/state/ffmpeg_state.py` - Pipeline configuration

#### Video Filters (10 filters)
- `ScaleFilter` - Resolution scaling with aspect ratio handling
- `PadFilter` - Letterbox/pillarbox padding
- `CropFilter` - Video cropping
- `TonemapFilter` - HDR to SDR tonemapping
- `DeinterlaceFilter` - Yadif deinterlacing
- `PixelFormatFilter` - Pixel format conversion
- `HardwareUploadFilter` - GPU upload
- `HardwareDownloadFilter` - GPU download
- `RealtimeFilter` - Live streaming pace
- `WatermarkFilter` - Overlay watermarks

#### Audio Filters (3 filters)
- `AudioNormalizeFilter` - Loudness normalization (LUFS)
- `AudioResampleFilter` - Sample rate/channel conversion
- `AudioPadFilter` - Silence padding

#### Video Encoders (14 encoders)
- Software: `libx264`, `libx265`, `copy`
- VideoToolbox (macOS): `h264_videotoolbox`, `hevc_videotoolbox`
- NVENC (NVIDIA): `h264_nvenc`, `hevc_nvenc`
- QSV (Intel): `h264_qsv`, `hevc_qsv`
- VAAPI (Linux): `h264_vaapi`, `hevc_vaapi`
- AMF (AMD): `h264_amf`, `hevc_amf`

#### Audio Encoders (4 encoders)
- `aac`, `ac3`, `pcm_s16le`, `copy`

---

## [1.0.7] - 2026-01-14

### Fixed - Import Path Updates
- Updated all `streamtv` imports to `exstreamtv` (11 files)
- Updated user-facing strings to EXStreamTV branding
- Updated HTML template titles from StreamTV to EXStreamTV

---

## [1.0.6] - 2026-01-14

### Added - Complete Module Port from StreamTV
- **HDHomeRun Module**: SSDP server, HDHomeRun API emulation for Plex/Jellyfin/Emby
- **API Routes**: 30+ FastAPI routers (channels, playlists, schedules, auth, IPTV, etc.)
- **Transcoding**: FFmpeg builder, hardware detection
- **Supporting Modules**:
  - `importers/` - M3U, Plex, YouTube importers
  - `integration/` - External service integrations
  - `metadata/` - Media metadata providers
  - `middleware/` - Request middleware
  - `scheduling/` - Schedule management
  - `services/` - Background services
  - `utils/` - Utility functions
  - `validation/` - Input validation

### Metrics
- 115+ Python modules
- 36 HTML templates
- Complete WebUI with Apple Design System

---

## [1.0.5] - 2026-01-14

### Added - WebUI Templates (Ported from StreamTV)
- 36 HTML templates with Apple Design System styling
- Complete WebUI: Dashboard, Channels, Playlists, Schedules, Playouts
- Settings pages: FFmpeg, HDHomeRun, Plex, Security, Resolutions, Watermarks
- Authentication pages: YouTube, Archive.org, OAuth setup
- Media management: Collections, Import, Player
- AI integration: Ollama chat, Log analysis
- Static assets: `apple-design-system.css`, `apple-animations.js`

---

## [1.0.4] - 2026-01-14

### Added - AI Agent Module (Ported from StreamTV)
- `exstreamtv/ai_agent/log_analyzer.py` - Real-time log parsing (15+ error patterns)
- `exstreamtv/ai_agent/fix_suggester.py` - Ollama AI + rule-based fix suggestions
- `exstreamtv/ai_agent/fix_applier.py` - Safe fix application with rollback
- `exstreamtv/ai_agent/approval_manager.py` - Workflow for risky fix approvals
- `exstreamtv/ai_agent/learning.py` - Fix effectiveness tracking and learning

### AI Agent Features
- 15+ error pattern detection (FFmpeg, YouTube, Archive.org, network, auth)
- 5 risk levels (safe, low, medium, high, critical)
- 7 fix action types (retry, reload_cookies, switch_cdn, adjust_timeout, etc.)
- Predictive error prevention based on learned patterns
- Auto-approval for proven safe fixes (90%+ success rate over 7+ days)

---

## [1.0.3] - 2026-01-14

### Added - Streaming Module (Ported from StreamTV)
- Complete streaming infrastructure with all bug fixes preserved:
  - `exstreamtv/streaming/channel_manager.py` - ErsatzTV-style continuous streaming
  - `exstreamtv/streaming/mpegts_streamer.py` - FFmpeg MPEG-TS generation
  - `exstreamtv/streaming/error_handler.py` - Error classification and recovery
  - `exstreamtv/streaming/retry_manager.py` - Retry logic with backoff

### Bug Fixes Preserved
- **Bitstream filters**: `-bsf:v h264_mp4toannexb,dump_extra` for H.264 copy mode
- **Real-time flag**: `-re` for pre-recorded content (prevents buffer underruns)
- **Error tolerance**: `-fflags +genpts+discardcorrupt+igndts` for corrupt streams
- **VideoToolbox restrictions**: MPEG-4 codec software fallback on macOS
- **Extended timeouts**: 60s for Archive.org/Plex, 30s default
- **Reconnection**: Automatic reconnection for HTTP streams

### Streaming Features
- Smart codec detection (copy vs transcode)
- Multi-client broadcast to single stream
- Playout timeline tracking with resume
- 15 error types with recovery strategies

---

## [1.0.2] - 2026-01-14

### Added
- Complete database model suite (ErsatzTV-compatible):
  - Channel, ChannelWatermark, ChannelFFmpegProfile
  - Playlist, PlaylistGroup, PlaylistItem
  - MediaItem, MediaFile, MediaVersion
  - Playout, PlayoutItem, PlayoutAnchor, PlayoutHistory, PlayoutTemplate
  - ProgramSchedule, ProgramScheduleItem, Block, BlockGroup, BlockItem
  - FillerPreset, FillerPresetItem
  - Deco, DecoGroup
  - Template, TemplateGroup, TemplateItem
  - PlexLibrary, JellyfinLibrary, EmbyLibrary, LocalLibrary
  - FFmpegProfile, Resolution
- Main FastAPI application (`exstreamtv/main.py`)
- FFmpeg pipeline with hardware detection
- Alembic database migration configuration
- Migration scripts:
  - `scripts/migrate_from_streamtv.py`
  - `scripts/migrate_from_ersatztv.py`

### FFmpeg Module
- Hardware capability detection (VideoToolbox, NVENC, QSV, VAAPI, AMF)
- Pipeline builder with StreamTV bug fixes preserved
- Encoder auto-selection based on platform

---

## [1.0.1] - 2026-01-14

### Added
- Project directory structure created
- Core configuration system (`exstreamtv/config.py`)
- Database connection management (`exstreamtv/database/connection.py`)
- Database models package structure
- Requirements files (production and development)
- `pyproject.toml` with full Python packaging configuration
- `.gitignore` for Python/Xcode/macOS artifacts
- `config.example.yaml` with all configuration options
- Documentation structure (`docs/` directory)
- Build tracking system (`docs/BUILD_PROGRESS.md`)
- System architecture documentation

### Infrastructure
- Created `exstreamtv/` main package
- Created `tests/` directory structure
- Created `EXStreamTVApp/` for macOS menu bar app
- Created `containers/` for Docker/Kubernetes configs
- Created `distributions/` for platform installers
- Created `scripts/` for migration and utility scripts

---

## [1.0.0] - 2026-01-14

### Added
- Initial project creation
- Base project structure from merger plan
- README.md with project overview
- LICENSE (MIT)

### Origin
- Merged from StreamTV (Python/FastAPI) + ErsatzTV (C#/.NET)
- Retains StreamTV WebUI, AI agent, and architecture
- Ports ErsatzTV advanced features (scheduling, transcoding, libraries)

---

[Unreleased]: https://github.com/roto31/EXStreamTV/compare/v2.6.0...HEAD
[2.6.0]: https://github.com/roto31/EXStreamTV/compare/v2.5.0...v2.6.0
[2.5.0]: https://github.com/roto31/EXStreamTV/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/roto31/EXStreamTV/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/roto31/EXStreamTV/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/roto31/EXStreamTV/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/roto31/EXStreamTV/compare/v2.0.1...v2.1.0
[2.0.1]: https://github.com/roto31/EXStreamTV/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/roto31/EXStreamTV/compare/v1.8.0...v2.0.0
[1.8.0]: https://github.com/roto31/EXStreamTV/compare/v1.6.0...v1.8.0
[1.6.0]: https://github.com/roto31/EXStreamTV/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/roto31/EXStreamTV/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/roto31/EXStreamTV/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/roto31/EXStreamTV/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/roto31/EXStreamTV/compare/v1.0.9...v1.2.0
[1.0.9]: https://github.com/roto31/EXStreamTV/compare/v1.0.8...v1.0.9
[1.0.8]: https://github.com/roto31/EXStreamTV/compare/v1.0.7...v1.0.8
[1.0.7]: https://github.com/roto31/EXStreamTV/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/roto31/EXStreamTV/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/roto31/EXStreamTV/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/roto31/EXStreamTV/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/roto31/EXStreamTV/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/roto31/EXStreamTV/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/roto31/EXStreamTV/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/roto31/EXStreamTV/releases/tag/v1.0.0
