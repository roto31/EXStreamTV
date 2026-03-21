# EXStreamTV — Agent Instructions

This file is read unconditionally by AI coding agents operating in this repository.

---

## Safety Rules (Non-Negotiable)

A full codebase audit (2026-03-20) confirmed 30 bugs across 18 files.
Complete findings: docs/LESSONS_LEARNED.md
Full enforcement rules: .cursor/rules/exstreamtv-safety.mdc (alwaysApply: true)
Short critical rules:   .cursor/rules/exstreamtv-critical.mdc (alwaysApply: true)

Before writing or editing ANY Python in this project, follow these rules:

- datetime: always datetime.now(tz=timezone.utc) — never datetime.utcnow()
- FFmpeg flags: always import from exstreamtv/ffmpeg/constants.py — never hardcode
- H.264 COPY to MPEG-TS: always add -bsf:v h264_mp4toannexb after -c:v copy
- async def + DB: never call sync SQLAlchemy directly — use run_in_executor
- async lock: never await blocking I/O inside async with lock — collect then act outside
- XMLTV timestamps: always %Y%m%d%H%M%S +0000 — no dashes, no UTC suffix
- scheduler while loops: always guard else: advance index; break on full wrap
- MPEG-TS buffer trim: always align trim point to nearest 0x47 sync byte
- channel number: always cast FastAPI path param to int before DB query
- YAML: always yaml.safe_load() — never yaml.load()
- muxrate: always int(video_bitrate) + int(audio_bitrate) — explicit cast
- caches: always include TTL timestamp on module-level credential caches

Subdirectory-specific rules are in:
- exstreamtv/ffmpeg/AGENTS.md       (FFmpeg flags and hardware accel)
- exstreamtv/api/AGENTS.md          (XMLTV format and EPG None guards)
- exstreamtv/scheduling/AGENTS.md   (datetime and scheduler loop rules)
- exstreamtv/streaming/AGENTS.md    (async lock, sync DB, MPEG-TS rules)
- exstreamtv/transcoding/AGENTS.md  (ErsatzTV port checklist)

Confluence / GitHub wiki mirror (REST vs MCP, uv, titles, attachment uploads): `.cursor/rules/exstreamtv-confluence.mdc` · lessons **LL-031–LL-034** in `docs/LESSONS_LEARNED.md` · skill `.cursor/skills/exstreamtv-confluence-publish/SKILL.md`
