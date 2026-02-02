# AI Agent Component Changelog

All notable changes to the AI Agent component will be documented in this file.

## [2.6.0] - 2026-01-31
### Added - Enhanced AI Self-Healing System
- **UnifiedLogCollector** (`unified_log_collector.py`) - Real-time log aggregation
  - Multi-source log collection (application, FFmpeg, Plex, Jellyfin, etc.)
  - Real-time streaming to AI subscribers
  - Ring buffer for context windows
  - Log correlation by channel/session
  - FFmpeg stderr parsing with progress extraction
  - `LogEvent` and `FFmpegLogLine` dataclasses
- **FFmpegAIMonitor** (`ffmpeg_monitor.py`) - Intelligent FFmpeg monitoring
  - Real-time stderr parsing with progress metrics (frame, fps, bitrate, speed)
  - Error classification by type (12 error types) and severity
  - `ChannelHealthMetrics` for per-channel health tracking
  - Performance anomaly detection
  - Failure prediction based on declining trends
  - `AIAnalysis` for root cause diagnosis
- **PatternDetector** (`pattern_detector.py`) - ML-based pattern detection
  - Known pattern matching (db_pool_exhaustion, ffmpeg_degradation, network_instability, etc.)
  - `Pattern`, `PatternAnalysis`, `RootCauseAnalysis` dataclasses
  - Failure prediction with confidence scoring
  - Learning from outcomes for improved accuracy
- **AutoResolver** (`auto_resolver.py`) - Autonomous issue resolution
  - Resolution strategies per issue type (restart, refresh, expand, fallback, reduce, escalate)
  - Risk-based approval thresholds
  - Zero-downtime execution with fallback streams
  - Rollback capability for failed fixes
  - Learning integration for strategy improvement
  - Human escalation for complex issues

## [2.5.0] - 2026-01-17
### Added
- **BlockScheduleExecutor** (`block_executor.py`) - Converts AI ScheduleBlock configs to database Block entities
- **CollectionExecutor** (`collection_executor.py`) - Persists CollectionConfig objects to database
- Day-of-week bitmask conversion
- Playout mode to playback order mapping

## [2.4.0] - 2026-01-17
### Added
- **MethodSelector** (`method_selector.py`) - Channel creation method selection
  - CreationMethod enum: DIRECT_API, SCRIPTED_BUILD, YAML_IMPORT, M3U_IMPORT, TEMPLATE_BASED, HYBRID
  - Method scoring and recommendation system
- **DecoIntegrator** (`deco_integrator.py`) - Channel decoration elements
  - DecoType enum: WATERMARK, BUMPER, STATION_ID, INTERSTITIAL, LOWER_THIRD
  - Theme presets: classic_network, cable_channel, streaming, retro_tv, movie_channel, kids_channel, sports_channel, documentary

## [2.3.0] - 2026-01-17
### Added
- **PersonaManager** (`persona_manager.py`) - Central persona management
  - PersonaType enum for all 6 personas
  - PersonaInfo dataclass with metadata, icons, colors
  - Session-based persona state management
- **IntentAnalyzer** (`intent_analyzer.py`) - Natural language intent parsing
  - ChannelPurpose, PlayoutPreference, ContentEra enums
  - Comprehensive AnalyzedIntent dataclass
- **SourceSelector** (`source_selector.py`) - Media source ranking
  - SourceType enum for all source types
  - Genre and era affinity scoring
- **BuildPlanGenerator** (`build_plan_generator.py`) - Complete build plan generation
  - Configuration dataclasses for channel, collection, schedule, filler, deco
  - Daypart templates

## [2.2.0] - 2026-01-17
### Added
- **Movie Critics Persona** (`prompts/movie_critic.py`) - Siskel & Ebert style film critics
- **Kids Programming Expert** (`prompts/kids_expert.py`) - Children's media specialist
- **PBS Programming Expert** (`prompts/pbs_expert.py`) - Public television historian

## [2.1.0] - 2026-01-17
### Added
- **Sports Savant Persona** (`prompts/sports_expert.py`) - Schwab-style sports historian
- **Tech Savant Persona** (`prompts/tech_expert.py`) - Apple specialist and tech historian
- Persona registry with `get_persona()` and `list_personas()` functions

## [1.0.4] - 2026-01-14
### Added
- Initial port from StreamTV
- `log_analyzer.py` - Real-time log parsing (15+ error patterns)
- `fix_suggester.py` - Ollama AI + rule-based fix suggestions
- `fix_applier.py` - Safe fix application with rollback
- `approval_manager.py` - Workflow for risky fix approvals
- `learning.py` - Fix effectiveness tracking and learning
