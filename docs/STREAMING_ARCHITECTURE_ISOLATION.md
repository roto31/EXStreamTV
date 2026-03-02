# Streaming Architecture Isolation and Consolidation

## Overview

Structural hardening of the streaming subsystem with:
- Resolver isolation layer (no cross-source misrouting)
- Streaming safety contract enforcement
- Unified stream lifecycle (IPTV, HDHomeRun, web preview)
- Single resolution service boundary

---

## Part 1 — Resolver Isolation Layer

### 1.1 StreamSource DTO

```python
@dataclass
class StreamSource:
    url: str
    headers: dict[str, str]
    seek_offset: float
    probe_required: bool
    allow_retry: bool
    classification: SourceClassification
    source_type: SourceType
    title: str = ""
    canonical_duration: float = 1800.0
```

No raw strings passed to FFmpeg without validation.

### 1.2 SourceClassification

```python
class SourceClassification(str, Enum):
    PLEX = "plex"
    FILE = "file"
    URL = "url"
    YOUTUBE = "youtube"
    ARCHIVE = "archive"
    SLATE = "slate"
```

### 1.3 ResolverRegistry

- Explicit map: SourceType -> BaseResolver
- `get(source_type: SourceType) -> BaseResolver` raises if missing
- No default resolver
- Configuration error at timeline build if source_type unknown

### 1.4 Resolver Interface (Extended)

Resolvers accept DTO only (CanonicalTimelineItem or media_item dict).
Return StreamSource (or ResolverError for unrecoverable).
Never access DB, never mutate timeline.

### 1.5 Hard Rule

```
resolver = registry.get(item.source_type)
```

Never: `if rating_key: use Plex` or `if url: use URL`.
Implicit inference prohibited.

---

## Part 2 — Streaming Safety Contract

### 2.1 Contract Requirements

StreamSource valid only if:
- url non-empty
- scheme in (http, https, file, rtsp, pipe)
- required headers present for source type
- not HTML content-type
- not error message

### 2.2 StreamingContractEnforcer

```python
def validate(source: StreamSource) -> ValidationResult
```

- Valid -> Ok(source)
- Invalid -> ContractViolation(reason); log once; stream loop advances; no restart

### 2.3 IPTV Protection

- Never emit HTML
- Never close on resolver failure
- Always emit valid TS
- On violation -> SlateResolver

### 2.4 Restart Classification

**Restart allowed:** FFmpeg crash, process death, state corruption.
**Never restart:** Resolver failure, Plex config missing, probe failure, single item failure.

---

## Part 3 — Architecture Consolidation

### 3.1 Single Entry Point

All endpoints call `ChannelManager.get_stream(channel_id)` (via `get_channel_stream().get_stream()`).

### 3.2 Stream Loop Pattern

```
position = resolve_position()
resolver = registry.get(position.source_type)
source = await resolver.resolve(position.item)
validated = contract.validate(source)
if not validated:
    advance timeline; continue
launch FFmpeg; classify exit; handle
```

### 3.3 Legacy Removal

- Index-based advancement (last_item_index) — clock authority only
- Dual EPG fallback paths — clock-derived only
- Implicit resolver routing — registry.get only

---

## Part 4 — StreamResolutionService

```python
class StreamResolutionService:
    async def resolve_position(channel_id) -> StreamPosition | None
    async def resolve_source(item: CanonicalTimelineItem) -> StreamSource | None
```

ChannelManager calls only this service.
ORM boundary: service may use DB for authority/timeline; resolvers receive DTO only.

---

## Part 5 — Regression Test Matrix

| Category | Scenarios | Expected |
|----------|-----------|----------|
| Plex | Valid config, missing token, invalid rating_key, server down | Valid works; invalid skips; no restart |
| File | Exists, missing, unreadable | Valid works; missing skips |
| URL | Valid HTTP, 404, timeout | Valid works; invalid skips |
| YouTube | Valid cookies, missing, private | Valid works; invalid skips |
| IPTV | VLC, ipTV, UHF | Continuous TS; no HTML |
| HDHomeRun | Disconnect, reconnect, multi-client | No advancement on disconnect |
| Clock | 24h drift, EPG vs playback | No drift |

---

## File Layout

```
exstreamtv/streaming/
  contract.py           # StreamSource, SourceClassification, ValidationResult, StreamingContractEnforcer
  resolver_registry.py  # ResolverRegistry
  resolution_service.py # StreamResolutionService
  resolvers/
    base.py             # BaseResolver (extended)
    slate.py            # SlateResolver (new)
```

**Last Revised:** 2026-03-01
