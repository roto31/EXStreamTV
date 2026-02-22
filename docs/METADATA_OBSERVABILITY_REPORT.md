# EXStreamTV Metadata Observability Report

**Date:** 2026-02-01  
**Status:** Metadata pipeline fully observable

---

## SECTION 1 — Metadata Metrics Added


| Counter                                     | Description                                                     | Increment Location                    |
| ------------------------------------------- | --------------------------------------------------------------- | ------------------------------------- |
| `metadata_lookup_success_total`             | External metadata (TVDB/TMDB) returned data                     | metadata/enricher.py                  |
| `metadata_lookup_failure_total`             | TVDB/TMDB enrichment raised exception                           | metadata/enricher.py                  |
| `episode_metadata_missing_total`            | Series has series_title but no episode_number after enrich      | metadata/enricher.py                  |
| `movie_metadata_missing_total`              | Movie (no series) has no year after enrich                      | metadata/enricher.py                  |
| `placeholder_title_generated_total`         | Title from filename/channel fallback or "Item {id}" replacement | title_resolver, iptv, xmltv_generator |
| `xmltv_programme_missing_episode_num_total` | Episodic programme without episode-num in XMLTV                 | api/iptv.py                           |
| `xmltv_programme_missing_desc_total`        | Programme without description in XMLTV                          | api/iptv.py                           |
| `xmltv_programme_missing_year_total`        | Movie programme without year/date in XMLTV                      | api/iptv.py                           |
| `xmltv_validation_error_total`              | XMLTVGenerator validation failed (overlap, empty title)         | api/iptv.py                           |


---

## SECTION 2 — XMLTV Instrumentation Points


| Point                              | File                   | Behavior                                                         |
| ---------------------------------- | ---------------------- | ---------------------------------------------------------------- |
| **EPG cycle start**                | api/iptv.py            | `reset_epg_cycle_stats()`                                        |
| **Per-programme**                  | api/iptv.py            | `record_epg_programme()`, `inc_xmltv_programme_missing_`*        |
| **EPG cycle end**                  | api/iptv.py            | `check_early_warning()`                                          |
| **Placeholder in TimelineBuilder** | api/iptv.py            | `inc_placeholder_title_generated()` when is_item_placeholder     |
| **Placeholder in XMLTVGenerator**  | api/xmltv_generator.py | `inc_placeholder_title_generated()` when is_item_placeholder     |
| **Title fallback (filename)**      | api/title_resolver.py  | `inc_placeholder_title_generated()` when returning filename stem |
| **TimelineBuilder failure**        | api/iptv.py            | `inc_xmltv_validation_error()` on exception                      |


---

## SECTION 3 — Placeholder Detection Logic


| Condition                                   | Counted | Early Warning                                     |
| ------------------------------------------- | ------- | ------------------------------------------------- |
| Title from filename stem (Path.stem)        | Yes     | Via `placeholder_title_generated_total` threshold |
| Title = channel.name (final fallback)       | Yes     | Same                                              |
| is_item_placeholder("Item 123") replacement | Yes     | Same                                              |
| Empty title → channel.name                  | Yes     | Same                                              |
| Early-warning threshold                     | —       | `>10` placeholder count per EPG cycle             |


---

## SECTION 4 — Metadata Correlation Metrics


| Correlation                                   | Implementation                                                                                                                                                      |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **channel_id + stream success/failure**       | Existing `stream_success_total`, `stream_failure_total` by channel_id                                                                                               |
| **metadata_present + playback**               | `record_stream_metadata_correlation()` stub; correlation via external join of `placeholder_title_generated_total` (global) and `stream_failure_total` (per channel) |
| **Channels failing due to metadata mismatch** | Detect by: high `stream_failure_total` for channel AND high `placeholder_title_generated_total`; requires external dashboard                                        |
| **XMLTV vs lineup**                           | Not implemented (Plex display name vs XMLTV title); would require Plex API comparison                                                                               |


---

## SECTION 5 — Early Warning Safeguards


| Condition                      | Threshold             | Action                 |
| ------------------------------ | --------------------- | ---------------------- |
| Programmes missing episode-num | >5% of EPG programmes | Structured warning log |
| Programmes missing year        | >5% of EPG programmes | Structured warning log |
| Placeholder titles             | >10 per EPG cycle     | Structured warning log |
| Programmes missing desc        | >5%                   | Structured warning log |


**Log format:** `EPG metadata early warning: <message>` (single log per EPG generation, no per-item spam).

---

## SECTION 6 — Performance Impact Analysis


| Concern                         | Mitigation                                                         |
| ------------------------------- | ------------------------------------------------------------------ |
| Heavy metadata objects retained | Counters only (int); no dict/list of payloads                      |
| Large XMLTV duplication         | None; we append to xml_content as before                           |
| Blocking operations             | All inc_* are O(1), no I/O                                         |
| Log flooding                    | Early warning logs once per EPG cycle                              |
| Overhead                        | <5%: ~8 int increments per programme + 1 threshold check per cycle |


---

## SECTION 7 — Production Metadata Readiness


| Requirement                     | Status                                                                        |
| ------------------------------- | ----------------------------------------------------------------------------- |
| Metadata fully observable       | Yes — 9 counters, Prometheus export                                           |
| No blind EPG failures           | XMLTV validation errors counted; TimelineBuilder failure triggers legacy path |
| Placeholder titles detectable   | Yes — `placeholder_title_generated_total` + early warning                     |
| Metadata lookup success/failure | Yes — TVDB/TMDB enrichment instrumented                                       |
| Episode/movie metadata gaps     | Yes — episode_metadata_missing, movie_metadata_missing                        |
| Early warning on thresholds     | Yes — structured warning, no per-item logging                                 |


