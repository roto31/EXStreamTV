# Reverse Proxy Setup for EXStreamTV

When EXStreamTV runs behind a reverse proxy (Nginx, Caddy, Traefik), configure both the proxy and EXStreamTV so playlists and streams work correctly.

## Required Headers

The proxy **must** forward:

| Header | Purpose |
|--------|---------|
| `X-Forwarded-Proto` | Scheme (http or https) |
| `X-Forwarded-Host` | Public host (and optionally port, e.g. `192.168.1.120:8411`) |
| `X-Forwarded-Port` | Public port (if not in Host) |

Without these, playlist stream URLs may use `127.0.0.1` and fail when clients (Plex, VLC) try to connect.

## EXStreamTV Config

In `config.yaml` (or `exstreamtv.yml`):

```yaml
server:
  host: "0.0.0.0"
  port: 8411
  trust_proxy: true          # Enable ProxyHeadersMiddleware
  public_url: "http://192.168.1.120:8411"  # Optional: override when proxy doesn't forward correctly
```

- **trust_proxy: true** – Tells uvicorn to trust X-Forwarded-* headers from the proxy.
- **public_url** – Use when the proxy doesn't forward headers or when you need a fixed public URL (e.g. for Remote Access).

## Nginx

```nginx
location / {
    proxy_pass http://127.0.0.1:8411;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
    proxy_buffering off;
}
```

## Caddy

```caddyfile
exstream.yourdomain.com {
    reverse_proxy 127.0.0.1:8411
}
```

Caddy forwards `X-Forwarded-*` by default.

## Traefik

```yaml
http:
  routers:
    exstream:
      rule: "Host(`exstream.yourdomain.com`)"
      service: exstream
  services:
    exstream:
      loadBalancer:
        servers:
          - url: "http://127.0.0.1:8411"
```

Traefik forwards headers by default. Ensure `forwardedHeaders.trustedIPs` includes your proxy IP if needed.

## Validation

1. **Playlist URL**
   ```bash
   curl -s "http://192.168.1.120:8411/iptv/channels.m3u" | head -20
   ```
   Stream URLs should use `192.168.1.120` (or your public host), not `127.0.0.1`.

2. **Stream**
   ```bash
   curl -sI "http://192.168.1.120:8411/iptv/channel/1.ts"
   ```
   Expect 200 (stream) or 503 (ChannelManager not initialized – check server logs).

**Last Revised:** 2026-03-01
