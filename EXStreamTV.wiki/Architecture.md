# Architecture

See [Platform Guide](Platform-Guide#1-platform-overview) for full overview, components, and diagrams.

High-level: Clients (Plex, IPTV, Web) connect via REST, M3U/EPG, or HDHomeRun. SessionManager → ChannelManager → ProcessPoolManager → FFmpeg → StreamThrottler → Live MPEG-TS.

**EPG pipeline:** BroadcastScheduleAuthority.get_timeline → build_programmes_from_clock → normalize → repair → symbolic → simulation → fuzz → SMT verifier → XMLTV export (only if VERIFIED).

Full Mermaid diagrams: repo [docs/architecture/DIAGRAMS.md](https://github.com/roto31/EXStreamTV/blob/main/docs/architecture/DIAGRAMS.md) (15 Mermaid diagrams).

**Last Revised:** 2026-03-20
