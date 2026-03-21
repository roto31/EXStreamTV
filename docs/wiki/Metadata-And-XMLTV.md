# Metadata & XMLTV

See [Platform Guide](PLATFORM_GUIDE.md#4-metadata--xmltv-pipeline) for enrichment, placeholder detection, drift, confidence gating, and XMLTV validation.

EPG export gate: SMT interval verification required. Single source: get_timeline.

## 2026-03 Remediation: EPG Generation Fixes

Three confirmed bugs in XMLTV/EPG generation were fixed during the 2026-03 audit:

| LL ID | Bug | Impact | Fix |
|---|---|---|---|
| LL-007 | Wrong XMLTV timestamp format (`%Y-%m-%d %H:%M:%S UTC`) | Plex silently drops programme entries → gaps in guide | Standardised to `%Y%m%d%H%M%S +0000` throughout |
| LL-008 | `start_time = None` not guarded before `.strftime()` | `AttributeError` kills EPG generation for affected channel — no error visible in Plex UI | Explicit `None` guard with `now` fallback before every `strftime()` call |
| LL-009 | `for idx in range(...)` inner loop shadows outer counter | Guide shows wrong "Now Playing" — off by variable number of items | Inner loop variables renamed to `_ci` |

The canonical XMLTV timestamp format for this codebase is:

```
%Y%m%d%H%M%S +0000
```

No dashes, no colons, literal `+0000` offset (not `%z` which may produce empty string on naive datetimes). See [`docs/LESSONS_LEARNED.md`](../LESSONS_LEARNED.md) entries LL-007 through LL-009.

**Last Revised:** 2026-03-20
