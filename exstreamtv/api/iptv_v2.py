"""IPTV streaming endpoints v2 - M3U playlist and XMLTV EPG with proper format compliance.

Uses stable channel IDs (exstream-{channel.id}) in M3U tvg-id and XMLTV for EPG mapping.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..config import config
from ..constants import EXSTREAM_CHANNEL_ID_PREFIX
from ..database.models_v2 import Channel
from ..database.session import get_db
from .epg_generator_v2 import EPGGeneratorV2

logger = logging.getLogger(__name__)

router = APIRouter(tags=["IPTV V2"])

epg_generator = EPGGeneratorV2()


@router.get("/iptv/channels.m3u")
async def get_channel_playlist_v2(
    mode: str = "mixed",
    access_token: str | None = None,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Get IPTV channel playlist (M3U format) - V2"""
    try:
        # Allow anonymous access for Plex DVR / IPTV clients
        if access_token is not None and config.security.api_key_required and config.security.access_token:
            if access_token != config.security.access_token:
                raise HTTPException(status_code=401, detail="Invalid access token")

        channels = db.query(Channel).filter(Channel.enabled).order_by(Channel.number).all()

        # Get base URL from request
        base_url = config.server.base_url
        if request:
            scheme = request.url.scheme
            host = request.url.hostname
            port = request.url.port

            # Replace localhost with actual IP
            if host in ["localhost", "127.0.0.1"]:
                import socket

                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    host = s.getsockname()[0]
                    s.close()
                except OSError:
                    pass

            if port and port not in [80, 443]:
                base_url = f"{scheme}://{host}:{port}"
            else:
                base_url = f"{scheme}://{host}"

        epg_url = f"{base_url.rstrip('/')}/iptv/xmltv.xml"
        m3u_content = f'#EXTM3U x-tvg-url="{epg_url}" url-tvg="{epg_url}"\n'

        for channel in channels:
            try:
                token_param = f"?access_token={access_token}" if access_token else ""

                if mode in {"hls", "mixed"}:
                    stream_url = f"{base_url}/iptv/channel/{channel.number}.m3u8{token_param}"
                else:
                    stream_url = f"{base_url}/iptv/channel/{channel.number}.ts{token_param}"

                # Get logo URL
                logo_url = _resolve_logo_url(channel, base_url)

                tvg_id = f"{EXSTREAM_CHANNEL_ID_PREFIX}.{channel.id}"
                m3u_content += f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{channel.name}"'
                if channel.group:
                    m3u_content += f' group-title="{channel.group}"'
                if logo_url:
                    m3u_content += f' tvg-logo="{logo_url}"'
                m3u_content += f",{channel.name}\n"
                m3u_content += f"{stream_url}\n"
            except Exception as e:
                logger.exception(f"Error processing channel {channel.number} for M3U: {e}")
                continue

        return Response(content=m3u_content, media_type="application/vnd.apple.mpegurl")

    except Exception as e:
        logger.error(f"Error generating M3U playlist: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/iptv/xmltv.xml")
async def get_epg_v2(
    access_token: str | None = None, request: Request = None, db: Session = Depends(get_db)
):
    """Get XMLTV EPG - V2"""
    try:
        # Allow anonymous access for Plex DVR / IPTV clients
        if access_token is not None and config.security.api_key_required and config.security.access_token:
            if access_token != config.security.access_token:
                raise HTTPException(status_code=401, detail="Invalid access token")

        channels = db.query(Channel).filter(Channel.enabled).order_by(Channel.number).all()

        if not epg_generator:
            raise HTTPException(status_code=500, detail="EPG generator not available")

        # Get base URL
        base_url = config.server.base_url
        if request:
            scheme = request.url.scheme
            host = request.url.hostname
            port = request.url.port

            if host in ["localhost", "127.0.0.1"]:
                import socket

                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    host = s.getsockname()[0]
                    s.close()
                except OSError:
                    pass

            if port and port not in [80, 443]:
                base_url = f"{scheme}://{host}:{port}"
            else:
                base_url = f"{scheme}://{host}"

        # Generate XMLTV EPG
        xmltv_content = epg_generator.generate_xmltv(
            channels=channels, start_time=datetime.utcnow(), duration_hours=24, base_url=base_url
        )
        _pc = xmltv_content.count("<programme ")
        _cc = xmltv_content.count('<channel id=')
        return Response(content=xmltv_content, media_type="application/xml")

    except Exception as e:
        logger.error(f"Error generating XMLTV EPG: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _resolve_logo_url(channel: Channel, base_url: str) -> str | None:
    """Resolve channel logo URL"""
    if channel.icon_path:
        if channel.icon_path.startswith("http"):
            return channel.icon_path
        if channel.icon_path.startswith("/"):
            return f"{base_url}{channel.icon_path}"
        return f"{base_url}/{channel.icon_path}"
    return f"{base_url}/static/channel_icons/channel_{channel.number}.png"
