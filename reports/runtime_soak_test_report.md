# Runtime Soak Test Report

**Generated**: 2026-03-01T20:55:45.356679+00:00
**Overall**: FAILED

## Summary

| Metric | Value |
|--------|-------|
| Test duration | 60s |
| Channels tested | ['100', '101', '102', '103'] |
| Concurrent stream count | 4 |
| XMLTV request count | 5 |
| Rebuild count | 0 |
| Resolver failure count | 0 |
| Restart loop count | 0 |
| Race condition status | PASSED |
| Cancellation safety | PASSED |
| Orphan ffmpeg processes | 5 |

## Errors

- HDHomeRun: stream closed early

## Risk Matrix (Post-Soak)

| Risk Area | Status | Evidence |
|-----------|--------|----------|
| Orphan ffmpeg | RESOLVED | count=5 (no increase) |
| Duration Collapse | UNRESOLVED | No zero duration in logs |
| Mass Rebuild Storm | RESOLVED | rebuild_count=0 |
| Clock Invalidation | RESOLVED | PASSED |
| XMLTV Failure | RESOLVED | requests=5 |
| Resolver Contract Violation | RESOLVED | No Plex metadata errors |
| Race Conditions | RESOLVED | PASSED |
| IPTV Streaming Failure | UNRESOLVED | streams=4 |
| Plex Streaming Failure | RESOLVED | No Plex stream errors |
| HDHomeRun Failure | UNRESOLVED | Stream session completed |
| Restart Loops | RESOLVED | restart_loop_count=0 |
