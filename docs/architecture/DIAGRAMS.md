# EXStreamTV Architecture Diagrams

All diagrams use Mermaid. Referenced from Platform Guide, EPG Alignment, Observability, Invariants, Lessons Learned.

**Last Revised:** 2026-04-01

---

## 1. System Architecture Overview

```mermaid
flowchart TB
    subgraph Clients [Client Layer]
        Plex[Plex DVR]
        IPTV[IPTV Players]
        WebUI[Web Interface]
    end
    subgraph App [Application Layer]
        REST[REST API]
        EPG[M3U/EPG]
        HDHR[HDHomeRun Emulator]
    end
    subgraph Stream [Streaming Layer]
        Session[SessionManager]
        ChMgr[ChannelManager]
        Pool[ProcessPoolManager]
        Throttle[StreamThrottler]
    end
    subgraph Media [Media Layer]
        FFmpeg[FFmpeg Pipeline]
        Sched[Playout Engine]
    end
    subgraph Data [Data Layer]
        DB[(Database)]
        Lib[Plex/Jellyfin/Local]
    end
    Clients --> App
    App --> Session
    Session --> ChMgr
    ChMgr --> Pool
    Pool --> FFmpeg
    ChMgr --> Throttle
    Throttle --> Clients
    ChMgr --> Sched
    Sched --> Lib
    Sched --> DB
```

---

## 2. Zero-Drift Clock Authority Flow

```mermaid
flowchart LR
    Mono[time.monotonic]
    Anchor[anchor_wall_epoch]
    Delta[delta = mono - anchor_mono]
    Now[now_epoch = anchor + delta]
    Offset[current_offset = elapsed % total]
    Mono --> Delta
    Anchor --> Delta
    Delta --> Now
    Now --> Offset
```

---

## 3. XMLTV Generation Pipeline

```mermaid
flowchart TD
    Auth[BroadcastScheduleAuthority.get_timeline]
    Clock[ChannelClock]
    Build[build_programmes_from_clock]
    Verify[interval_verifier]
    Gate{SMT VERIFIED?}
    Export[XMLTV export]
    Fallback[Fallback 24h]
    Auth --> Clock
    Clock --> Build
    Build --> Verify
    Verify --> Gate
    Gate -->|Yes| Export
    Gate -->|No| Fallback
```

---

## 4. Validation Pipeline Order

```mermaid
flowchart LR
    Norm[normalize]
    Repair[repair]
    Sym[symbolic]
    Sim[simulation]
    Fuzz[fuzz]
    SMT[SMT z3]
    Export[export]
    Norm --> Repair --> Sym --> Sim --> Fuzz --> SMT --> Export
```

---

## 5. BroadcastScheduleAuthority Internal Flow

```mermaid
flowchart TD
    subgraph Auth [BroadcastScheduleAuthority]
        GetTL[get_timeline]
        Cache[_timelines cache]
        VerHash[_timeline_version_hash]
        Inval[invalidate_timeline]
        GetTL --> Cache
        VerHash -->|mismatch| Inval
        Inval --> Cache
    end
    Load[load_timeline_async]
    BuildYAML[build_from_yaml]
    BuildPlayout[build_from_playout]
    Load --> BuildYAML
    Load --> BuildPlayout
    BuildYAML --> Cache
    BuildPlayout --> Cache
```

---

## 6. Watchdog Monitoring Loop

```mermaid
flowchart TD
    Sleep[sleep adaptive_interval]
    Strategy[determine_adaptive_strategy]
    Channels[query enabled channels]
    Check[ensure_clock + get_timeline]
    Fetch[fetch XMLTV]
    Compare[compare EPG vs playback]
    Mismatch{mismatch?}
    Heal[invalidate_timeline + rebuild]
    Sleep --> Strategy
    Strategy --> Channels
    Channels --> Check
    Check --> Fetch
    Fetch --> Compare
    Compare --> Mismatch
    Mismatch -->|Yes| Heal
    Mismatch -->|No| Sleep
    Heal --> Sleep
```

---

## 7. Adaptive Self-Tuning Feedback Loop

```mermaid
flowchart LR
    Health[health_score]
    Risk[predictive_risk]
    Strat[determine_adaptive_strategy]
    Interval[watchdog_interval]
    Scope[rebuild_scope]
    Preempt[preemptive_rebuild]
    Health --> Strat
    Risk --> Strat
    Strat --> Interval
    Strat --> Scope
    Strat --> Preempt
```

---

## 8. Metrics Exporter to Prometheus Flow

```mermaid
flowchart TD
    MC[MetricsCollector]
    Scrape[GET /metrics]
    Prom[Prometheus scrape]
    MC --> Scrape
    Scrape --> Prom
```

---

## 9. Dashboard Health Score Predictive Analyzer

```mermaid
flowchart LR
    Health[health_score]
    Pred[predictive_task]
    Risk[risk_score]
    API[system_integrity API]
    Dash[Dashboard]
    Health --> API
    Pred --> Risk
    Risk --> API
    API --> Dash
```

---

## 10. ChannelManager Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Disabled
    Disabled --> Starting: enable
    Starting --> Running: stream ready
    Running --> Stopping: disable
    Stopping --> Disabled: cleanup
    Running --> Restarting: restart request
    Restarting --> Running: stream ready
```

---

## 11. Stream Pre-flight Validation Path

```mermaid
flowchart TD
    Req[Stream request]
    Resolve[resolution_service.resolve]
    Auth[get_authority]
    Clock[ensure_clock]
    TL[get_timeline]
    Resolve --> Auth
    Auth --> Clock
    Auth --> TL
    Req --> Resolve
```

---

## 12. Fallback Safety Gate Logic

```mermaid
flowchart TD
    Clock[clock_xml from _build_epg_via_clock]
    Valid{Valid?}
    Rebuild[rebuild + retry]
    SMT{SMT VERIFIED?}
    Export[return XMLTV]
    Fallback[return fallback 24h]
    Clock --> Valid
    Valid -->|No| Rebuild
    Rebuild --> Valid
    Valid -->|Yes| SMT
    SMT -->|Yes| Export
    SMT -->|No| Fallback
    Clock -->|None| Fallback
```

---

## 13. Temporal Simulation and Fuzz Layer

```mermaid
flowchart TD
    Intervals[intervals]
    Sim[run_temporal_simulation]
    Fuzz[run_epoch_fuzz]
    Step[step t in W]
    Sample[sample random t]
    Check{count == 1?}
    Intervals --> Sim
    Intervals --> Fuzz
    Sim --> Step
    Fuzz --> Sample
    Step --> Check
    Sample --> Check
    Check -->|No| FAILED
    Check -->|Yes| VERIFIED
```

---

## 14. SMT Verifier Integration Path

```mermaid
flowchart TD
    Progs[ClockProgramme per channel]
    Epoch[convert to epoch]
    Z3[z3.Solver]
    Constrain[add constraints]
    Check[solver.check]
    Result{SAT?}
    Progs --> Epoch
    Epoch --> Z3
    Z3 --> Constrain
    Constrain --> Check
    Check --> Result
    Result -->|UNSAT| FAILED
    Result -->|SAT| VERIFIED
```

---

## 15. Stream resolution safety contract

Validates resolved sources before FFmpeg (`resolution_service`, `StreamingContractEnforcer`, `StreamSource`).

```mermaid
flowchart TD
    Req[Stream request]
    RS[resolution_service.resolve]
    CE[StreamingContractEnforcer]
    SS[StreamSource DTO]
    FF[FFmpeg pipeline]
    Slate[Reject / slate fallback]
    Req --> RS
    RS --> CE
    CE -->|valid| SS
    CE -->|invalid| Slate
    SS --> FF
```

---

## 16. FFmpeg Command Builder Safety Layer (2026-03 remediation — LL-002 to LL-016)

All FFmpeg command builders import flags from a single constants module. No flag string is
hardcoded in individual builder files. This eliminates the class of bugs where two builders
used different loudnorm targets, different fflags, or omitted required bitstream filters.

```mermaid
flowchart TD
    C[ffmpeg/constants.py]
    C --> |FFLAGS_STREAMING| B1
    C --> |LOUDNORM_FILTER| B1
    C --> |BSF_H264_ANNEXB| B1
    C --> |PIX_FMT| B1
    C --> |FFLAGS_STREAMING| B2
    C --> |LOUDNORM_FILTER| B2
    C --> |PIX_FMT| B2
    subgraph Builders
        B1[ffmpeg_builder.py]
        B2[pipeline.py]
    end
    B1 --> FF[FFmpeg process]
    B2 --> FF
    FF --> MPEGTS[MPEG-TS output]
    note1["❌ -flags +low_delay (drops B-frames)"]
    note2["❌ +fastseek (masks missing +igndts)"]
    note3["✅ +igndts +genpts +discardcorrupt"]
    note4["✅ h264_mp4toannexb on COPY path"]
    C -.-> note1
    C -.-> note2
    FF -.-> note3
    FF -.-> note4
```

---

## 17. Async Lock Collect-Then-Act Pattern (2026-03 remediation — LL-013)

The process watchdog previously held its lock during 5-second kill operations, deadlocking
all callers. The fix: collect work items inside the lock (fast), execute outside it (slow).
This pattern applies to any async lock guarding I/O-heavy operations.

```mermaid
sequenceDiagram
    participant Check as check_all()
    participant Lock as asyncio.Lock
    participant Kill as _kill_process()

    Check->>Lock: acquire
    Note over Lock: Collect timed-out PIDs only (fast)
    Check->>Lock: release
    loop for each timed-out process
        Check->>Kill: await _kill_process() [OUTSIDE LOCK]
        Note over Kill: wait_for(timeout=5s) — can block
    end
    Note over Check: Other coroutines can acquire lock<br/>during kill operations
```

---

## 18. Six-layer AI / coding safety enforcement (2026-03 — post-merge `main`)

Redundant guardrails keep Cursor and human contributors aligned with audited patterns
(`docs/LESSONS_LEARNED.md`). Layers overlap so context drift or model switches still leave
multiple active reminders.

```mermaid
flowchart TB
    subgraph L1 [Layer 1 — Cursor rules]
        R1[exstreamtv-safety.mdc<br/>RULE 01–18 alwaysApply]
        R2[exstreamtv-critical.mdc<br/>8 rules alwaysApply]
    end
    subgraph L2 [Layer 2 — Repo root]
        AG[AGENTS.md<br/>non-negotiable checklist]
    end
    subgraph L3 [Layer 3 — Path-local]
        A1[exstreamtv/ffmpeg/AGENTS.md]
        A2[exstreamtv/api/AGENTS.md]
        A3[exstreamtv/scheduling/AGENTS.md]
        A4[exstreamtv/streaming/AGENTS.md]
        A5[exstreamtv/transcoding/AGENTS.md]
    end
    subgraph L4 [Layer 4 — Constants]
        C[ffmpeg/constants.py<br/>single FFmpeg truth]
    end
    subgraph L5 [Layer 5 — Skill]
        SK[.cursor/skills/exstreamtv-expert<br/>Safety Patterns]
    end
    subgraph L6 [Layer 6 — Optional]
        GL["~/.cursor/skills/exstreamtv-expert<br/>global install"]
    end
    R1 --> Code[Python edits in exstreamtv/ + tests/]
    R2 --> Code
    AG --> Code
    A1 --> Code
    A2 --> Code
    A3 --> Code
    A4 --> Code
    A5 --> Code
    C --> Code
    SK --> Code
    GL -.-> SK
```

**Merge note (2026-03-21):** Branch `2026-02-21-ufnw` was merged into `default` `main` so GitHub,
local clones, and wiki sources all reflect the same remediation + hardening + tooling tree.

---

## 19. Schedule history (memento) API

Capture and revert channel schedule snapshots stored in **`schedule_history`** (Alembic **006**).

```mermaid
flowchart TD
    A[Client] -->|POST /api/schedule-history/capture| B[schedule_snapshot_service]
    B --> C[(schedule_history)]
    B --> D[JSON snapshot + metadata]
    D --> C
    A -->|POST /api/schedule-history/id/revert| E[revert_snapshot]
    C --> E
    E --> F[channels / schedules restored]
```

See [System Design — Schedule history](SYSTEM_DESIGN.md#schedule-history-exstreamtvdatabasemodelsschedule_historypy-migration-006).
