# Scheduling Module — Safety Rules

Full rules: .cursor/rules/exstreamtv-safety.mdc

## Datetime

- All datetime calls: datetime.now(tz=timezone.utc) — never datetime.utcnow()
- _generate_sequence_playlist: current_time = datetime.now(tz=timezone.utc)
- DB-sourced datetimes: normalise with _ensure_utc() before arithmetic

## Scheduler loops (playout/scheduler.py, scheduling/engine.py)

Every while current_time < end loop MUST have this pattern:

    else:
        schedule_index = (schedule_index + 1) % total
        if schedule_index == start_index:
            break   # full wrap with no output — abort
        continue

_generate_sequence_playlist: if cycle_duration.total_seconds() == 0 then break immediately.

## parse_duration (scheduling/parser.py)

- Handle bare integer strings: if duration_str.isdigit(): return int(duration_str) or None
- No mn-olympics- prefix in find_schedule_file candidate list (dead project-specific debt)

## engine_v2.py

- This file imports from database.models_v2 and IS wired into main.py as a fallback
  (main.py lines 385-392 load iptv_v2 which imports engine_v2 when primary iptv fails)
- All datetime.utcnow() calls have been replaced with _utcnow() helper
- Verify _utcnow() returns datetime.now(tz=timezone.utc) on every edit
