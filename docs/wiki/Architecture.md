# Architecture

See [Platform Guide](PLATFORM_GUIDE.md#1-platform-overview) for full overview, components, and diagrams.

High-level: Clients (Plex, IPTV, Web) connect via REST, M3U/EPG, or HDHomeRun. SessionManager → ChannelManager → ProcessPoolManager → FFmpeg → StreamThrottler → Live MPEG-TS. EPG: get_timeline → SMT verify → export.

**Last Revised:** 2026-03-20
