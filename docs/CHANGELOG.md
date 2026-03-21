# Documentation Component Changelog

All notable changes to the Documentation component will be documented in this file.

**Last Revised:** 2026-03-22

## [2.6.0] - 2026-03-22 (Confluence publishers, lessons LL-031–LL-035, wiki sync)

### Documentation / tooling
- **`docs/LESSONS_LEARNED.md`** — **LL-031–LL-035** (Confluence/MCP, uv, titles, attachment **415**, root **400** + reuse). Version **1.3**; **35** lessons.
- **`EXStreamTV.wiki/Lessons-Learned.md`** — synced from repo; wiki banner → canonical doc on `main`.
- **`scripts/publish_confluence_wiki_tree.py`**, **`publish_confluence_mirror.py`** — httpx headers for multipart; **`.env`**; username alias; root title lookup.
- **`docs/confluence/README.md`**, **`.env.example`**, Cursor **confluence** rule/skill, **`AGENTS.md`**.

### Confluence (ESTV)
- Republish: `uv run scripts/publish_confluence_wiki_tree.py` to update mirrored pages and attachments.

## [2.6.0] - 2026-03-21 (documentation, Mermaid, wiki sync)

### Changed
- `docs/architecture/DIAGRAMS.md` — Diagram 18 (six-layer AI/coding safety); diagram 16 note nodes wired to graph; **Last Revised** 2026-03-21
- `docs/README.md`, `docs/PLATFORM_GUIDE.md` — §11 documentation/wiki/merge alignment; diagram count **18**; dates refreshed
- `docs/wiki/*.md` — **Last Revised** 2026-03-21; Architecture / Production-Certification / AI-Agent updates for `exstreamtv-critical.mdc`, merge to `main`, diagram 18 cross-links
- `scripts/sync_docs_to_wiki.py` — Wiki source **Architecture-Diagrams** → `docs/architecture/DIAGRAMS.md`; `_Sidebar.md` entry under Reference
- `EXStreamTV.wiki/` — regenerated via `python scripts/sync_docs_to_wiki.py --wiki-dir EXStreamTV.wiki`

### Context
- Default branch **`main`** includes merged remediation work from `2026-02-21-ufnw` (GitHub, local clones, and wiki copies stay aligned).

## [2.6.0] - 2026-03-20 (full codebase remediation + audit)

### Code Fixes — 30 confirmed bugs across 18 files (see `docs/LESSONS_LEARNED.md`)

**Critical fixes:**
- `playout/scheduler.py` — infinite loop guard when `_schedule_item()` returns empty (LL-001)
- `streaming/channel_manager.py` — tz-aware datetime helpers (`_utcnow`, `_ensure_utc`), `run_in_executor` for DB writes, corrected `async for` body indentation (LL-002, LL-003, LL-026)
- `transcoding/ffmpeg_builder.py` — removed `-flags +low_delay`, `+fastseek→+igndts`, H.264 Annex-B BSF on COPY path, `int()` muxrate cast (LL-004, LL-005, LL-006, LL-016)
- `ffmpeg/pipeline.py` — `hwdownload` before CPU filters for HW decode, unified constants (LL-011, LL-012)
- `api/iptv.py` — XMLTV timestamp format, `None` guard before `strftime()`, loop variable shadowing fix (LL-007, LL-008, LL-009)
- `hdhomerun/api.py` — `int()` channel number cast with HTTP 400, structured HD flag logic (LL-010, LL-017)
- `streaming/process_watchdog.py` — kill outside lock (deadlock), tz-aware datetime (LL-013, LL-015)
- `streaming/throttler.py` — MPEG-TS trim aligned to `0x47` sync byte (LL-014)
- `ffmpeg/process_pool.py` — correct semaphore `try/except` acquire (LL-021)
- `scheduling/parser.py` — bare-integer duration parsing, removed `mn-olympics-` prefix (LL-018, LL-023)
- `scheduling/engine.py` and `engine_v2.py` — tz-aware datetime throughout (LL-020)
- `api/epg_generator_v2.py` — tz-aware datetime, correct XMLTV timestamp format (LL-007)

**New file:**
- `exstreamtv/ffmpeg/constants.py` — single source of truth for all FFmpeg flags (LL-011)

**Security:**
- `exstreamtv.db.backup.*` removed from git; `.gitignore` extended (LL-027)

### Documentation Added / Updated
- `docs/LESSONS_LEARNED.md` — v1.0: 30 confirmed issues (LL-001–LL-030) with root cause, symptom, fix, and prevention rule for each
- `docs/CHANGELOG.md` — this entry
- `docs/architecture/DIAGRAMS.md` — Diagrams 16 (FFmpeg constants safety layer) and 17 (async lock collect-then-act)
- `docs/wiki/Streaming-Internals.md` — updated with remediation notes
- `docs/wiki/Restart-Safety-Model.md` — updated with watchdog deadlock fix (LL-013)
- `docs/wiki/Metadata-And-XMLTV.md` — updated with XMLTV format fixes (LL-007, LL-008, LL-009)
- `docs/wiki/Architecture.md` — updated with FFmpeg constants reference
- `docs/wiki/Production-Certification.md` — updated with audit reference

### Cursor Tooling
- `.cursor/rules/exstreamtv-safety.mdc` — RULE 01–18, auto-applied to all Python files
- `.cursor/skills/exstreamtv-expert/SKILL.md` — Safety Patterns section with ErsatzTV port checklist

## [2.6.0] - 2026-03-20 (documentation sync)
### Changed
- `architecture/DIAGRAMS.md` — added diagram 15 (stream resolution safety contract); revised date
- `README.md`, `VERSION` — documentation metadata refresh
- `guides/PLEX_SETUP.md` — guide updates (committed with codebase sync)

## [2.6.0] - 2026-01-31
### Added - Tunarr/dizqueTV Integration Documentation
- **Architecture Documentation**
  - `architecture/TUNARR_DIZQUETV_INTEGRATION.md` - Complete integration architecture with Mermaid diagrams
  - Updated `architecture/SYSTEM_DESIGN.md` - Added new components and data flows
  
- **New User Guides**
  - `guides/STREAMING_STABILITY.md` - Session management, throttling, error screens
  - `guides/ADVANCED_SCHEDULING.md` - Time slot and balance scheduling
  
- **Updated Guides**
  - `guides/AI_SETUP.md` - Added AI self-healing system configuration
  
- **API Documentation Updates**
  - `api/README.md` - Added AI self-healing and database backup endpoints
  
- **Build Progress**
  - `BUILD_PROGRESS.md` - Added Phase 12 (AI Channel Creator) and Phase 13 (Tunarr/dizqueTV Integration)

### Architecture Diagrams Added
- Integration overview diagram
- Database connection management flow
- Session lifecycle state diagram
- Stream throttling flow
- Error screen generation flow
- Time slot scheduling flow
- Balance scheduling flow
- AI self-healing data flow
- Complete system data flow

## [2.5.0] - 2026-01-17
### Changed
- No changes to documentation in this release

## [1.6.0] - 2026-01-14
### Added
- **User Guides**
  - `guides/INSTALLATION.md` - Complete installation guide for all platforms
  - `guides/QUICK_START.md` - Getting started in under 10 minutes
  - `guides/HW_TRANSCODING.md` - Hardware transcoding setup and optimization
  - `guides/LOCAL_MEDIA.md` - Local media library configuration
  - `guides/AI_SETUP.md` - AI provider configuration
  - `guides/CHANNEL_CREATION_GUIDE.md` - Channel creation guide
  - `guides/MACOS_APP_GUIDE.md` - macOS app usage
  - `guides/NAVIGATION_GUIDE.md` - UI navigation guide
  - `guides/ONBOARDING.md` - User onboarding

- **API Documentation**
  - `api/README.md` - Comprehensive REST API reference
  - All endpoints documented with examples
  - SDK examples (Python, JavaScript, curl)

- **Architecture**
  - `architecture/SYSTEM_DESIGN.md` - System architecture documentation

- **Development**
  - `development/DISTRIBUTION.md` - Distribution and packaging guide
  - `BUILD_PROGRESS.md` - Build tracking system

## [1.0.1] - 2026-01-14
### Added
- Initial documentation structure
- System architecture documentation
