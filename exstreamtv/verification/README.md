# EPG Interval Verification

**Purpose:** Formal SMT-based verification of EPG timeline interval invariants.

**Architecture:** Runs before XMLTV export. Pipeline: normalize → repair → symbolic → simulation → fuzz → SMT → export gate.

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

**Interfaces:** `run_full_verification_pipeline(intervals, now_epoch, window_hours)` → `VERIFIED` | `FAILED`.

**Invariants:** s_i < e_i; e_i ≤ s_{i+1}; uniqueness; coverage of [s0,en].

**Failure modes:** SMT timeout (100ms); z3 unavailable → fail closed.

**Dependencies:** z3-solver, exstreamtv.scheduling.clock, exstreamtv.monitoring.metrics.

**Created:** 2026-03-01
