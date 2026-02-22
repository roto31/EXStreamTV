# ErsatzTV / Tunarr / dizqueTV Feature Parity

This document lists major features from ErsatzTV, Tunarr, and dizqueTV and how EXStreamTV covers them (best methods adopted, deferred, or out of scope).

## EPG and channel lineup

| Feature | ErsatzTV | Tunarr | dizqueTV | EXStreamTV |
|--------|----------|--------|----------|------------|
| Single canonical XMLTV URL | ✓ | ✓ | ✓ | ✓ Adopted. One URL for Plex and IPTV clients. |
| Stable channel IDs (e.g. exstream-{id}) | ✓ | ✓ | ✓ | ✓ Adopted. Same IDs in M3U and XMLTV for Plex DVR mapping. |
| Programme start/stop from playout timeline | ✓ | ✓ | ✓ | ✓ Adopted. EPG reflects what is actually streamed. |
| EPG cache with short TTL | ✓ | ✓ | — | ✓ Adopted. EPG cache TTL 1–5 min so guide reloads see updates. |
| Channel list and lineup in same universe as XMLTV | ✓ | ✓ | ✓ | ✓ Same channel IDs in M3U and XMLTV. |
| Filler/slate as separate programmes in XMLTV | ✓ | ✓ | ✓ | Deferred. Will add when filler/slate content is modelled. |
| Optional XMLTV extensions (episode-num, icon) | — | — | — | ✓ Where data exists; format stays standard. |
| Description length limit (e.g. 500 chars) | — | — | — | ✓ 500-char cap for compatibility. |

## Plex integration

| Feature | ErsatzTV | Tunarr | dizqueTV | EXStreamTV |
|--------|----------|--------|----------|------------|
| Add EXStreamTV as tuner in Plex (M3U + XMLTV URL) | ✓ | ✓ | ✓ | ✓ Documented in PLEX_SETUP.md. |
| Plex DVR guide reload (POST reloadGuide) | ✓ | ✓ | ✓ | ✓ Direct HTTP in plex_api_client; manual and optional after-EPG. |
| Throttle guide reload (e.g. 60s) | — | — | — | ✓ 60s throttle unless force=True. |
| Reload guide after EPG publish (optional) | — | — | — | ✓ Config option; throttled. |
| Python-PlexAPI for server/libraries/metadata | — | — | — | ✓ Optional layer in services/plex_library_service. |
| Health check (server reachable, token valid) | — | — | — | ✓ test_connection in PlexAPIClient; settings test endpoint. |

## Playout and scheduling

| Feature | ErsatzTV | Tunarr | dizqueTV | EXStreamTV |
|--------|----------|--------|----------|------------|
| One authoritative timeline per channel | ✓ | ✓ | ✓ | ✓ playout_start_time, current_item_start_time, elapsed_seconds_in_item. |
| EPG programme boundaries match stream | ✓ | ✓ | ✓ | In scope; EPG derived from same timeline. |
| Advanced library filtering / flex scheduling | ✓ | ✓ | ✓ | Deferred. EXStreamTV uses playouts/schedules; parity later. |
| Recurring programmes / multi-channel lineups | ✓ | ✓ | ✓ | Partially (schedules/playouts); full parity deferred. |

## HDHomeRun / M3U

| Feature | ErsatzTV | Tunarr | dizqueTV | EXStreamTV |
|--------|----------|--------|----------|------------|
| HDHomeRun-style discovery | ✓ | — | ✓ | ✓ HDHomeRun integration. |
| M3U + XMLTV for IPTV apps | ✓ | ✓ | ✓ | ✓ One XMLTV URL works for Plex and IPTV. |
| Consistent channel order/IDs across M3U and XMLTV | ✓ | ✓ | ✓ | ✓ Stable exstream-{id}. |

## Transcoding and direct-play

| Feature | ErsatzTV | Tunarr | dizqueTV | EXStreamTV |
|--------|----------|--------|----------|------------|
| Document Plex transcode vs direct-play for live tuner | — | — | — | In scope (section 7 of plan). |
| EXStreamTV transcoding strategy (per-channel, on-demand) | — | — | ✓ | In scope; design and implement. |
| Expose direct-play-friendly or multiple variants to Plex | — | — | — | Future work. |

## Gaps and follow-up

- **Filler/slate as programmes**: When filler or slate segments exist, model them as separate short programmes in XMLTV (e.g. "Filler" / "Commercial break").
- **Advanced flex scheduling**: ErsatzTV/Tunarr-style library filters and flex rules; document as future work.
- **Transcoding for Plex**: Implement and document EXStreamTV’s strategy (no transcode vs optional vs per-channel).
- **Channel mapping hint in UI**: If Plex API exposes DVR lineups, show which Plex channel number maps to which EXStreamTV channel.

## References

- Tunarr: https://github.com/chrisbenincasa/tunarr  
- ErsatzTV: https://github.com/ErsatzTV/ErsatzTV  
- dizqueTV: https://github.com/vexorian/dizquetv  
- EXStreamTV EPG and Plex integration plan (sections 2–8)
