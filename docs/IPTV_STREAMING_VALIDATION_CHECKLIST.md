# IPTV Streaming Validation Checklist

Use this checklist to diagnose "Stream Unavailable" or 503 on `/iptv/channel/{id}.ts`.

## Environment (No Reverse Proxy)

- Server: Mac Studio
- LAN IP: 192.168.1.120
- URL: http://192.168.1.120:8411/iptv/channels.m3u

## 1. ChannelManager Startup

**Check startup logs** for one of:

- ✓ `Channel manager started - IPTV streams (/iptv/channel/*.ts) are available`
- ✗ `Channel manager initialization failed: ... - IPTV streams will return 503 until resolved`

If failed: Full traceback appears above the error. Common causes:
- `get_sync_session_factory` → DB path/permissions
- `ChannelManager` / `start` → Rare; check FFmpeg path if process_pool used

**Quick check:**
```bash
curl -s http://192.168.1.120:8411/api/health/detailed | python3 -c "import sys,json; d=json.load(sys.stdin); print('ChannelManager:', d.get('components',{}).get('channel_manager',{}).get('status','?'))"
```
Expect: `ChannelManager: ok`

## 2. Stream Endpoint (503 vs 200)

```bash
curl -sI http://192.168.1.120:8411/iptv/channel/1.ts
```

- **503** + header `X-EXStreamTV-ChannelManager: not-initialized` → ChannelManager init failed (see §1)
- **503** without header → Different service failure; check logs
- **404** → Channel 1 not found or disabled
- **200** → Stream OK; proceed to §3

## 3. Resolver Failure ("Stream Unavailable" Slate)

If ChannelManager is healthy but you see the "Stream Unavailable" **video slate**:

**Search logs** for:
- `resolve_for_streaming ch=X: resolver returned None`
- `resolve_for_streaming ch=X: contract violation`
- `PlexResolver: Missing Plex ...`

**Fixes:**
- Plex: Ensure `libraries.plex.url` and `libraries.plex.token` in config; token valid
- Empty timeline: Channel needs active playout with items or schedule file

## 4. Playlist URL Integrity

```bash
curl -s http://192.168.1.120:8411/iptv/channels.m3u | grep -E "^http"
```

Stream URLs must use `192.168.1.120`, not `127.0.0.1`. With direct connection (no proxy), this should be correct automatically.

## 5. FFmpeg Check

```bash
curl -s http://192.168.1.120:8411/api/health/detailed | python3 -c "import sys,json; d=json.load(sys.stdin); print('FFmpeg:', d.get('components',{}).get('ffmpeg',{}))"
```

Expect: `{"status": "ok", ...}`

## 6. Diagnostic Script

```bash
python3 scripts/iptv_diagnostic.py http://192.168.1.120:8411
```

Runs all checks above automatically.

**Last Revised:** 2026-03-20
