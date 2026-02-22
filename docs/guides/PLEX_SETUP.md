# Plex DVR Setup with EXStreamTV

This guide explains how to use EXStreamTV as a tuner and program guide source for Plex DVR, so you can watch and record EXStreamTV channels in Plex.

## Overview

- **Single XMLTV URL**: One canonical EPG URL for both Plex DVR and IPTV apps.
- **Stable channel IDs**: Channels use IDs like `exstream-1`, `exstream-2` in both the M3U and XMLTV. This keeps Plex DVR channel mapping correct when you reload the guide.
- **EPG reflects playout**: Programme start/stop times in the guide are derived from the same timeline as the stream (ErsatzTV-style).

## Prerequisites

- EXStreamTV running and reachable from the machine running Plex Media Server (same LAN or via public URL).
- At least one enabled channel with a schedule/playout.

## Step 1: Get your EXStreamTV URLs

Use the **base URL** that Plex can reach (e.g. `http://192.168.1.100:8411` or your public URL). Avoid `localhost` if Plex runs on a different machine.

| Purpose | URL |
|--------|-----|
| **M3U playlist** | `{base_url}/iptv/channels.m3u` |
| **XMLTV (EPG)** | `{base_url}/iptv/xmltv.xml` |

If you use access token authentication, append `?access_token=YOUR_TOKEN` to both URLs.

Example:
- M3U: `http://192.168.1.100:8411/iptv/channels.m3u`
- XMLTV: `http://192.168.1.100:8411/iptv/xmltv.xml`

## Step 2: Add tuner in Plex

1. In Plex: **Settings → Live TV & DVR → Set up Plex DVR** (or **Add tuner**).
2. Choose **Custom** / **M3U** (or the option that lets you enter an M3U URL).
3. Enter the **M3U URL** from Step 1.
4. When asked for the **program guide (XMLTV)**, enter the **XMLTV URL** from Step 1.
5. Complete the tuner setup. Plex will fetch the channel list and guide from EXStreamTV.

## Step 3: Map channels (if needed)

Plex will list channels using EXStreamTV’s stable IDs (`exstream-1`, etc.). Map or enable the channels you want in Plex’s DVR channel lineup as usual.

## Step 4: Reload the guide after changes

When you change channels, schedules, or playouts in EXStreamTV:

1. **Manual reload**: In Plex go to **Settings → Live TV & DVR**, find your EXStreamTV tuner, and use **Reload Guide** (or equivalent).  
   You can also call EXStreamTV’s API:  
   `POST /api/settings/plex/reload-guide`  
   This forces an immediate reload (ignores throttle).

2. **Optional: Reload after EPG publish**  
   In EXStreamTV settings you can enable **Reload guide after EPG**. When enabled, each time the EPG is generated (e.g. when someone or something requests `/iptv/xmltv.xml`), EXStreamTV will ask Plex to reload the guide. Requests are **throttled to once per 60 seconds** so Plex is not hammered. Use this if you want the guide to refresh shortly after schedule/playout changes without manually clicking Reload in Plex.

## Cache and when the guide updates

- EXStreamTV may cache the EPG for a short time (e.g. 1–5 minutes, depending on configuration). After you change schedules or playouts, the new data will appear in the XMLTV feed after the cache expires or is invalidated.
- If **Reload guide after EPG** is enabled, the 60-second throttle applies: at most one reload request is sent to Plex per 60 seconds, even if the EPG is requested multiple times.

## Troubleshooting

- **Plex can’t reach EXStreamTV**  
  Use an IP or hostname that Plex can resolve (e.g. LAN IP). Don’t use `localhost` if Plex is on another machine.

- **Channels or guide missing**  
  Confirm `{base_url}/iptv/channels.m3u` and `{base_url}/iptv/xmltv.xml` return valid data in a browser or with `curl`. Check that at least one channel is enabled and has a schedule.

- **Wrong programme times**  
  EXStreamTV builds the EPG from the same playout timeline as the stream. If you still see mismatches, check channel playout and schedule configuration.

- **Authentication**  
  If access token is required, use the same token in both M3U and XMLTV URLs when configuring Plex.

## References

- EXStreamTV IPTV endpoints: `/iptv/channels.m3u`, `/iptv/xmltv.xml`
- Plex DVR guide reload (EXStreamTV API): `POST /api/settings/plex/reload-guide`
- Plan: EPG and Plex Integration (best practices from ErsatzTV, Tunarr, dizqueTV)
