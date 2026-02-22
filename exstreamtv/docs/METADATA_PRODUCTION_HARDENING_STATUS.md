# Production Metadata Hardening Status

> **User-facing overview:** For metadata pipeline and XMLTV validation, see [PLATFORM_GUIDE.md](../../docs/PLATFORM_GUIDE.md).

**Date:** 2026-02  
**Objective:** Move from "observable" to "self-correcting and production-hardened" per Metadata Observability Report.

---

## SECTION 1 — Correlation Enforcement Added

**File:** `exstreamtv/monitoring/metadata_metrics.py`, `exstreamtv/tasks/health_tasks.py`

- **Per-channel rolling counters:**
  - `_channel_placeholder_count`: dict[channel_id, count] — reset each EPG cycle
  - `inc_placeholder_title_generated(channel_id=None)` — optional channel_id for per-channel tracking
  - `get_channel_placeholder_count(channel_id)`

- **Correlation logic:**
  - `evaluate_metadata_stream_correlation()` — called from `channel_health_task` (existing cadence)
  - If `channel_stream_failure_count > 3` AND `channel_placeholder_count >= 5` → emit structured warning: "Channel {id} likely failing due to metadata mismatch"
  - Uses `get_metrics_collector().stream_failure_total` (existing)
  - O(channels), no blocking, no background loops

---

## SECTION 2 — XMLTV/Lineup Validation Added

**File:** `exstreamtv/monitoring/metadata_metrics.py`, `exstreamtv/api/iptv.py`

- **New counter:** `xmltv_lineup_mismatch_total`
- **Validation:** `validate_xmltv_lineup(channels)` — called at EPG cycle start
  - Cross-check: lineup GuideNumber (channel.number), XMLTV channel id (exstream-{id})
  - No duplicate GuideNumber
  - No duplicate tvg-id
  - No empty display name
- Single structured warning per cycle on mismatch
- No Plex API calls

---

## SECTION 3 — Placeholder Self-Healing Logic

**File:** `exstreamtv/metadata/extractor.py`, `exstreamtv/api/title_resolver.py`, `exstreamtv/api/iptv.py`

- **`parse_filename_for_title(path)`:** Smarter filename parsing
  - SxxExx regex → "Show S01E05"
  - Year extraction (19xx, 20xx) → "Movie (2020)"
  - No external API, no LLM

- **Title resolution order:**
  1. Custom title, media title
  2. `parse_filename_for_title()` if path available
  3. Filename stem (placeholder)
  4. `channel.name` as last resort

- Applied in: TitleResolver, iptv legacy path, TimelineBuilder path
- No blocking EPG generation

---

## SECTION 4 — Episode-Num Standard Enforcement

**File:** `exstreamtv/api/iptv.py`

- XMLTV episode-num uses `xmltv_ns` format: `season.episode.0`
- Zero-based season and episode: `max(0, season-1)`, `max(0, episode-1)`
- No negative values
- Trailing `.0` for part (required by spec)
- On invalid parse: increment `xmltv_validation_error_total`

---

## SECTION 5 — Metadata Escalation Logic

**File:** `exstreamtv/monitoring/metadata_metrics.py`

- In `check_early_warning()`:
  - If `metadata_lookup_failure_total / (success + failure) > 0.3`:
  - Emit: "Metadata enrichment degraded — possible API outage"
- Observability only — no stop streaming, restart, or circuit breaker

---

## SECTION 6 — Performance Confirmation

| Constraint              | Status |
|-------------------------|--------|
| No new heavy objects    | OK — `_channel_placeholder_count` dict, O(channels) |
| No dict accumulation    | OK — reset each EPG cycle |
| No per-programme logging| OK — single structured warning per cycle |
| No blocking calls       | OK — all inc_* O(1), no I/O |
| No background threads   | OK |
| No memory growth        | OK — bounded structures |
| O(1) per programme      | OK |

---

## SECTION 7 — Production Metadata Hardening Status

| Requirement                    | Status |
|--------------------------------|--------|
| Correlation in-process         | Yes — `evaluate_metadata_stream_correlation` |
| XMLTV/lineup validation        | Yes — `validate_xmltv_lineup` |
| Placeholder self-healing       | Yes — `parse_filename_for_title`, smarter order |
| Episode-num xmltv_ns           | Yes — `season.episode.0` |
| Hard fail empty titles         | Yes — `"{channel.name} — {start_time}"` |
| Metadata failure escalation    | Yes — >0.3 ratio warning |
| No streaming endpoint changes  | Yes |
| No restart path changes       | Yes |
| No CircuitBreaker changes     | Yes |
| No health_tasks cadence change| Yes — reuse existing |
| No ProcessPoolManager change   | Yes |
| No log flooding               | Yes — single warning per cycle |
