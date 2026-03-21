# API Module — Safety Rules

Full rules: .cursor/rules/exstreamtv-safety.mdc

## XMLTV / EPG generation (iptv.py is the highest-risk file in the codebase — 119KB)

- ALL XMLTV programme start/stop timestamps: %Y%m%d%H%M%S +0000 ONLY
- BANNED formats: "%Y-%m-%d %H:%M:%S UTC" and "%Y-%m-%dT%H:%M:%SZ"
- Guard EVERY start_time and end_time_prog for None before calling .strftime()
- Use _ci not idx for inner loops to avoid shadowing current_item_index
- Variable start_time = None must have a fallback before any arithmetic or strftime

## Channel number lookups

- ALL channel_number path params: cast to int() before DB comparison
- Wrap in try/except and raise HTTPException(400) on ValueError

## HTTP headers

- Timestamp headers use ISO 8601: %Y-%m-%dT%H:%M:%SZ (different from XMLTV format)

## Confirm on every edit to iptv.py

    [ ] Every strftime call uses %Y%m%d%H%M%S +0000 (search and count them)
    [ ] Every start_time and end_time variable guarded for None
    [ ] No loop variable named idx where current_item_index is also in scope
