"""
YouTube URL Resolver using yt-dlp.

Resolves YouTube video URLs to streamable CDN URLs with format selection
and expiration tracking.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from exstreamtv.streaming.resolvers.base import (
    BaseResolver,
    ResolvedURL,
    ResolverError,
    SourceType,
)

logger = logging.getLogger(__name__)


class YouTubeResolver(BaseResolver):
    """
    YouTube URL resolver using yt-dlp.
    
    Features:
    - Video ID extraction from various URL formats
    - Format selection (prefers h264 for compatibility)
    - Cookie support for authenticated content
    - Expiration tracking (~6 hours for YouTube URLs)
    - Error handling for bot detection and rate limits
    """
    
    source_type = SourceType.YOUTUBE
    
    # YouTube URLs typically expire after 6 hours
    DEFAULT_EXPIRATION_HOURS = 6
    
    # Regex patterns for YouTube video IDs
    VIDEO_ID_PATTERNS = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    
    def __init__(
        self,
        cookies_file: Optional[str] = None,
        preferred_quality: str = "720",
        prefer_h264: bool = True,
    ):
        """
        Initialize YouTube resolver.
        
        Args:
            cookies_file: Path to YouTube cookies file (Netscape format)
            preferred_quality: Preferred video quality (360, 480, 720, 1080)
            prefer_h264: Prefer h264 codec for better compatibility
        """
        super().__init__()
        self.cookies_file = cookies_file
        self.preferred_quality = preferred_quality
        self.prefer_h264 = prefer_h264
        self._yt_dlp_available = None
    
    def _check_yt_dlp(self) -> bool:
        """Check if yt-dlp is available."""
        if self._yt_dlp_available is not None:
            return self._yt_dlp_available
        
        try:
            import yt_dlp
            self._yt_dlp_available = True
            logger.debug("yt-dlp is available")
        except ImportError:
            self._yt_dlp_available = False
            logger.warning("yt-dlp not installed - YouTube resolution will fail")
        
        return self._yt_dlp_available
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract video ID from a YouTube URL.
        
        Supports:
        - youtube.com/watch?v=VIDEO_ID
        - youtu.be/VIDEO_ID
        - youtube.com/embed/VIDEO_ID
        - youtube.com/v/VIDEO_ID
        - youtube.com/shorts/VIDEO_ID
        """
        for pattern in self.VIDEO_ID_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Check if it's already a video ID
        if re.match(r"^[a-zA-Z0-9_-]{11}$", url):
            return url
        
        return None
    
    async def can_handle(self, media_item: Any) -> bool:
        """Check if this resolver can handle the media item."""
        url = self._get_url(media_item)
        if not url:
            return False
        
        url_lower = url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return True
        
        # Check source attribute
        source = getattr(media_item, "source", None)
        if source and "youtube" in str(source).lower():
            return True
        
        return False
    
    def _get_url(self, media_item: Any) -> Optional[str]:
        """Extract URL from media item."""
        if isinstance(media_item, str):
            return media_item
        if hasattr(media_item, "url"):
            return media_item.url
        if hasattr(media_item, "path"):
            return media_item.path
        if isinstance(media_item, dict):
            return media_item.get("url") or media_item.get("path")
        return None
    
    def _get_format_selector(self) -> str:
        """
        Build yt-dlp format selector string.
        
        Prefers:
        1. h264 video + aac audio at preferred quality
        2. Best available h264 + aac combination
        3. Best available format
        """
        if self.prefer_h264:
            # Prefer h264 for better FFmpeg compatibility
            selectors = [
                f"bestvideo[height<={self.preferred_quality}][vcodec^=avc]+bestaudio[acodec^=mp4a]/",
                f"bestvideo[height<={self.preferred_quality}][vcodec^=avc]+bestaudio/",
                f"best[height<={self.preferred_quality}][vcodec^=avc]/",
                "bestvideo[vcodec^=avc]+bestaudio/",
                "best[vcodec^=avc]/",
                "bestvideo+bestaudio/best",
            ]
            return "".join(selectors)
        else:
            return f"bestvideo[height<={self.preferred_quality}]+bestaudio/best[height<={self.preferred_quality}]/best"
    
    async def resolve(
        self,
        media_item: Any,
        force_refresh: bool = False,
    ) -> ResolvedURL:
        """
        Resolve YouTube URL to streamable CDN URL.
        
        Args:
            media_item: Media item with YouTube URL
            force_refresh: Skip cache and force fresh resolution
            
        Returns:
            ResolvedURL with CDN stream URL
            
        Raises:
            ResolverError: If resolution fails
        """
        # Check cache first
        if not force_refresh:
            cached = self.get_cached(media_item)
            if cached and cached.is_valid:
                logger.debug(f"Using cached YouTube URL for {self.get_cache_key(media_item)}")
                return cached.resolved_url
        
        if not self._check_yt_dlp():
            raise ResolverError(
                "yt-dlp is not installed. Install with: pip install yt-dlp",
                source_type=SourceType.YOUTUBE,
                is_retryable=False,
            )
        
        url = self._get_url(media_item)
        if not url:
            raise ResolverError(
                "No URL found in media item",
                source_type=SourceType.YOUTUBE,
                is_retryable=False,
            )
        
        video_id = self._extract_video_id(url)
        if not video_id:
            raise ResolverError(
                f"Could not extract video ID from URL: {url}",
                source_type=SourceType.YOUTUBE,
                is_retryable=False,
            )
        
        # Run yt-dlp in thread pool to avoid blocking
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None,
                self._extract_info,
                f"https://www.youtube.com/watch?v={video_id}",
            )
        except Exception as e:
            error_msg = str(e).lower()
            
            # Classify errors
            if "private video" in error_msg or "video is private" in error_msg:
                raise ResolverError(
                    f"Video is private: {video_id}",
                    source_type=SourceType.YOUTUBE,
                    is_retryable=False,
                    original_error=e,
                )
            elif "video unavailable" in error_msg:
                raise ResolverError(
                    f"Video unavailable: {video_id}",
                    source_type=SourceType.YOUTUBE,
                    is_retryable=False,
                    original_error=e,
                )
            elif "sign in" in error_msg or "confirm your age" in error_msg:
                raise ResolverError(
                    f"Authentication required for video: {video_id}",
                    source_type=SourceType.YOUTUBE,
                    is_retryable=True,
                    original_error=e,
                )
            elif "too many requests" in error_msg or "rate limit" in error_msg:
                raise ResolverError(
                    f"Rate limited by YouTube: {video_id}",
                    source_type=SourceType.YOUTUBE,
                    is_retryable=True,
                    original_error=e,
                )
            else:
                raise ResolverError(
                    f"Failed to extract YouTube info: {e}",
                    source_type=SourceType.YOUTUBE,
                    is_retryable=True,
                    original_error=e,
                )
        
        if not info:
            raise ResolverError(
                f"No info extracted for video: {video_id}",
                source_type=SourceType.YOUTUBE,
                is_retryable=True,
            )
        
        # Get stream URL
        stream_url = info.get("url")
        if not stream_url:
            # Check for format-specific URL
            formats = info.get("formats", [])
            if formats:
                # Get best format
                best_format = formats[-1]
                stream_url = best_format.get("url")
        
        if not stream_url:
            raise ResolverError(
                f"No stream URL found for video: {video_id}",
                source_type=SourceType.YOUTUBE,
                is_retryable=True,
            )
        
        # Calculate expiration (YouTube URLs expire in ~6 hours)
        expires_at = datetime.utcnow() + timedelta(hours=self.DEFAULT_EXPIRATION_HOURS)
        
        # Build codec info
        codec_info = {
            "video_codec": info.get("vcodec", "unknown"),
            "audio_codec": info.get("acodec", "unknown"),
            "width": info.get("width", 0),
            "height": info.get("height", 0),
            "fps": info.get("fps", 30),
        }
        
        # Build headers for CDN request
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.youtube.com/",
            "Origin": "https://www.youtube.com",
        }
        
        resolved = ResolvedURL(
            url=stream_url,
            source_type=SourceType.YOUTUBE,
            expires_at=expires_at,
            media_id=getattr(media_item, "id", None),
            codec_info=codec_info,
            headers=headers,
            metadata={
                "video_id": video_id,
                "title": info.get("title"),
                "duration": info.get("duration"),
                "channel": info.get("channel"),
                "view_count": info.get("view_count"),
            },
        )
        
        # Cache the result
        self.cache_url(media_item, resolved)
        
        logger.info(
            f"Resolved YouTube video {video_id}: "
            f"{codec_info['width']}x{codec_info['height']} "
            f"(expires in {self.DEFAULT_EXPIRATION_HOURS}h)"
        )
        
        return resolved
    
    def _extract_info(self, url: str) -> dict[str, Any]:
        """
        Extract video info using yt-dlp (blocking, run in executor).
        """
        import yt_dlp
        
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "format": self._get_format_selector(),
            "skip_download": True,
        }
        
        # Add cookies if available
        if self.cookies_file and Path(self.cookies_file).exists():
            ydl_opts["cookiefile"] = self.cookies_file
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    
    def get_cache_key(self, media_item: Any) -> str:
        """Generate cache key using video ID."""
        url = self._get_url(media_item)
        if url:
            video_id = self._extract_video_id(url)
            if video_id:
                return f"youtube:{video_id}"
        
        return super().get_cache_key(media_item)
