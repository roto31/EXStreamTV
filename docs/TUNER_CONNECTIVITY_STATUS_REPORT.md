# EXStreamTV Tuner Connectivity Status Report

**Report Date:** 2026-02-25  
**Issue:** "Error: Unable to connect to tuner" across all Plex Live TV channels  
**Scope:** Platform-wide tuner connectivity failure

---

## Executive Summary

**Root cause:** The EXStreamTV tuner service is **not running**. Plex cannot establish HTTP connections to the HDHomeRun emulation endpoints because nothing is listening on the expected port.

**Immediate fix:** Start the EXStreamTV server. No code rollback or configuration changes are required.

---

## 1. Current Operational State

| Component | Status | Details |
|-----------|--------|---------|
| **EXStreamTV HTTP server** | ❌ **STOPPED** | No process listening on port 8411 |
| **HDHomeRun API** | ❌ Unreachable | Depends on server being running |
| **SSDP discovery** | ❌ Stopped | Advertises tuner when server runs |
| **Plex tuner connection** | ❌ Failing | Cannot connect to tuner base URL |

### Verification

```bash
$ lsof -i :8411
# Output: Nothing on 8411

$ python3 -c "import socket; s=socket.socket(); s.settimeout(2); print('Port 8411:', 'OPEN' if s.connect_ex(('127.0.0.1',8411))==0 else 'CLOSED')"
Port 8411: CLOSED
```

---

## 2. Timeline from Logs

| Timestamp | Event |
|-----------|-------|
| 2026-02-24 22:57:56 | Server started, pre-warming disabled, SSDP started |
| 2026-02-24 22:58:58 | HDHomeRun stream request for channel 100 from 192.168.1.125 (Plex) ✅ |
| 2026-02-24 22:59:11 | HDHomeRun stream request for channel 101 from 192.168.1.125 ✅ |
| 2026-02-24 23:00:11 | HDHomeRun stream request for channel 100 from 127.0.0.1 ✅ |
| 2026-02-24 23:01:09 | **Shutting down EXStreamTV** |
| 2026-02-24 23:01:31 | EXStreamTV shutdown complete |
| Current | Server not restarted → Plex gets "Unable to connect to tuner" |

**Conclusion:** Streaming worked immediately before shutdown. The server was stopped and not restarted.

---

## 3. Recent Code Changes (Tuner-Relevant)

The following tuner-related changes were made in recent sessions. **None of these prevent the server from starting or accepting connections** when the server is running:

### Configuration

| File | Change | Impact |
|------|--------|--------|
| `config.yaml` | `use_process_pool: false` | Bypasses FFmpeg process pool; avoids spawn timeouts |
| `config.yaml` | `prewarm_enabled: false` | Channels start on first tune; reduces startup load |
| `config.yaml` | `max_processes: 45`, `spawns_per_second: 15` | Pool tuning (unused when pool disabled) |
| `exstreamtv/config.py` | `prewarm_enabled`, `use_process_pool` | New config fields |
| `exstreamtv/main.py` | Channel manager uses `pool_for_channels` (None when pool disabled) | Direct FFmpeg per channel |

### HDHomeRun / Tuner Code

- **`exstreamtv/hdhomerun/api.py`**: No recent changes to discovery, lineup, or stream endpoints
- **`exstreamtv/hdhomerun/ssdp_server.py`**: SSDP discovery; starts with server lifespan
- **Base URL logic** (`_get_base_url_for_client`): Uses request host or `_get_server_ip()` for local clients; public URL for remote

**None of these changes affect tuner reachability when the server is running.** The server must be started for Plex to connect.

---

## 4. Configuration Verification

### config.yaml (Current)

```yaml
server:
  host: 0.0.0.0    # Binds all interfaces
  port: 8411       # Tuner HTTP port

hdhomerun:
  enabled: true
  device_id: E5E17001
  device_auth: exstreamtv
  tuner_count: 4

plex:
  enabled: true
  url: http://192.168.1.120:32400
```

### Plex → Tuner Flow

1. **Discovery:** Plex discovers tuner via SSDP (UDP 1900) from EXStreamTV host
2. **Lineup:** Plex requests `http://<tuner_host>:8411/hdhomerun/lineup.json`
3. **Stream:** Plex requests `http://<tuner_host>:8411/hdhomerun/auto/v{channel}` for playback

**Critical:** Plex must be able to reach `<tuner_host>:8411`. If EXStreamTV runs on the same host as Plex (192.168.1.120), that host must have EXStreamTV listening. If EXStreamTV runs on a different host, Plex must be able to reach that host on port 8411.

Logs show Plex at `192.168.1.125` connecting successfully before shutdown, so the tuner host was reachable when the server was up.

---

## 5. Network Connectivity

- **Plex server:** 192.168.1.120 (from config)
- **Plex client (observed):** 192.168.1.125
- **EXStreamTV host:** Must be reachable from Plex on port 8411

**If EXStreamTV runs on the same machine as Plex (192.168.1.120):** Start EXStreamTV on that machine. Plex will connect to `127.0.0.1:8411` or `192.168.1.120:8411`.

**If EXStreamTV runs on a different machine:** Ensure firewall allows TCP 8411 from the Plex server IP.

---

## 6. Error Logs

No tuner connection errors appear in EXStreamTV logs because the server is not running. Plex-side errors ("Unable to connect to tuner") indicate TCP connection failures to the tuner URL.

---

## 7. Rollback Assessment

**Rollback not required.** The failure is due to the server being stopped, not recent code changes. The last successful streams (22:58–23:01) occurred with the current codebase.

---

## 8. Recommended Actions

### Immediate (Restore Service)

1. **Start EXStreamTV:**

   ```bash
   cd /Users/roto1231/Documents/XCode\ Projects/EXStreamTV
   python3 -m exstreamtv
   ```

2. **Verify tuner is reachable:**

   ```bash
   curl -s "http://127.0.0.1:8411/hdhomerun/lineup.json" | head -c 500
   curl -s "http://127.0.0.1:8411/hdhomerun/status.json"
   ```

3. **In Plex:** Remove and re-add the HDHomeRun tuner if it was added while the server was down, or simply try tuning a channel.

### Ongoing (Optional)

- Run EXStreamTV as a service (e.g. launchd on macOS) so it restarts automatically
- Confirm which host runs EXStreamTV vs Plex so base URL and firewall rules are correct

---

## 9. Modules / Parameters to Monitor

| Area | Parameters | Purpose |
|------|------------|---------|
| `exstreamtv/main.py` | lifespan | Server startup and HDHomeRun/SSDP init |
| `exstreamtv/hdhomerun/api.py` | `_get_base_url_for_client` | URL Plex uses for stream requests |
| `config.yaml` | `server.host`, `server.port`, `server.base_url`, `server.public_url` | Tuner reachability |
| `config.yaml` | `hdhomerun.enabled` | Must be true for tuner endpoints |

---

## 10. Conclusion

**Root cause:** EXStreamTV is not running. No code or configuration defect identified.

**Fix:** Start EXStreamTV. Channels should resume streaming once the server is up and reachable by Plex.

**Last Revised:** 2026-03-01
