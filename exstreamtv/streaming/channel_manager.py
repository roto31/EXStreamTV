"""
Channel Manager for continuous background streaming (ErsatzTV-style).

Ported from StreamTV with playout timeline tracking and resume capability.

Enhanced with Tunarr/dizqueTV integrations:
- Session tracking for connection management
- Stream throttling for buffer control
- Error screen fallback for graceful failures
- FFmpeg monitoring integration
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Optional imports for new components (graceful fallback if not available)
try:
    from exstreamtv.streaming.session_manager import (
        get_session_manager,
        SessionErrorType,
    )
    HAS_SESSION_MANAGER = True
except ImportError:
    HAS_SESSION_MANAGER = False
    logger.debug("Session manager not available")

try:
    from exstreamtv.streaming.throttler import (
        StreamThrottler,
        ThrottleConfig,
        ThrottleMode,
    )
    HAS_THROTTLER = True
except ImportError:
    HAS_THROTTLER = False
    logger.debug("Stream throttler not available")

try:
    from exstreamtv.streaming.error_screens import (
        get_error_screen_generator,
        ErrorScreenMessage,
        ErrorScreenConfig,
    )
    HAS_ERROR_SCREENS = True
except ImportError:
    HAS_ERROR_SCREENS = False
    logger.debug("Error screen generator not available")

try:
    from exstreamtv.ai_agent.ffmpeg_monitor import get_ffmpeg_monitor
    HAS_FFMPEG_MONITOR = True
except ImportError:
    HAS_FFMPEG_MONITOR = False
    logger.debug("FFmpeg monitor not available")

try:
    from exstreamtv.ai_agent.unified_log_collector import get_log_collector, LogSource
    HAS_LOG_COLLECTOR = True
except ImportError:
    HAS_LOG_COLLECTOR = False
    logger.debug("Log collector not available")


class ChannelStream:
    """
    Manages a continuous stream for a single channel (ErsatzTV-style).
    
    Features:
    - Continuous background streaming
    - Multiple client connections to same stream
    - Playout timeline tracking with resume
    - Seamless transitions between items
    """

    # Buffer configuration
    BUFFER_SIZE = 2 * 1024 * 1024  # 2MB buffer
    CHUNK_SIZE = 64 * 1024  # 64KB read chunks
    QUEUE_MAX_SIZE = 50  # Max items in broadcast queue

    def __init__(
        self,
        channel_id: int,
        channel_number: int,
        channel_name: str,
        db_session_factory: Callable[[], Session],
    ):
        """
        Initialize channel stream.
        
        Args:
            channel_id: Database ID of the channel.
            channel_number: Channel number for display.
            channel_name: Channel name for logging.
            db_session_factory: Factory function to create database sessions.
        """
        self.channel_id = channel_id
        self.channel_number = channel_number
        self.channel_name = channel_name
        self.db_session_factory = db_session_factory
        
        # Stream state
        self._broadcast_queue: asyncio.Queue = asyncio.Queue(maxsize=self.QUEUE_MAX_SIZE)
        self._stream_task: asyncio.Task | None = None
        self._client_queues: list[asyncio.Queue] = []
        self._is_running = False
        self._lock = asyncio.Lock()
        self._client_count = 0
        
        # Playout timeline tracking (ErsatzTV-style)
        self._playout_start_time: datetime | None = None
        self._schedule_items: list[dict] = []
        self._current_item_index = 0
        self._current_item_start_time: datetime | None = None
        self._timeline_lock = asyncio.Lock()
        self._seek_offset: float = 0.0  # Seek offset within current item (seconds)
        
        # Auto-recovery state
        self._restart_count = 0
        self._max_restarts = 5
        self._restart_backoff_base = 1.0
        self._last_restart_time: datetime | None = None
        self._consecutive_failures = 0
        
        # Health tracking
        self._last_output_time: datetime | None = None
        self._bytes_streamed = 0
        
        # New components from Tunarr/dizqueTV integration
        self._throttler: Optional[Any] = None
        self._use_throttling = False
        self._use_error_screens = HAS_ERROR_SCREENS
        self._use_ffmpeg_monitoring = HAS_FFMPEG_MONITOR
        
        # Initialize throttler if available
        if HAS_THROTTLER:
            try:
                from exstreamtv.config import get_config
                config = get_config()
                if hasattr(config, 'stream_throttler') and config.stream_throttler.enabled:
                    self._throttler = StreamThrottler(
                        config=ThrottleConfig(
                            target_bitrate_bps=config.stream_throttler.target_bitrate_bps,
                            mode=ThrottleMode(config.stream_throttler.mode),
                        ),
                        channel_id=channel_id,
                    )
                    self._use_throttling = True
                    logger.debug(f"Channel {channel_number}: Throttler initialized")
            except Exception as e:
                logger.debug(f"Channel {channel_number}: Throttler init failed: {e}")

    async def start(self) -> None:
        """Start the continuous stream in the background."""
        if self._is_running:
            return

        async with self._lock:
            if self._is_running:
                return

            # Initialize playout timeline
            async with self._timeline_lock:
                if not self._playout_start_time:
                    await self._load_or_initialize_position()

            self._is_running = True
            
            logger.info(
                f"Starting continuous stream for channel {self.channel_number} "
                f"({self.channel_name})"
            )
            
            self._stream_task = asyncio.create_task(self._run_continuous_stream())

    async def _load_or_initialize_position(self) -> None:
        """
        Load saved anchor time or initialize for continuous streaming.
        
        ErsatzTV-style approach: Use an anchor time to calculate the current
        position based on elapsed wall-clock time. This ensures:
        1. All viewers see the same content at the same time
        2. Restarting the server continues from the correct time-based position
        3. The EPG matches what's actually playing
        """
        from exstreamtv.database.models import ChannelPlaybackPosition, Playout, PlayoutItem, MediaItem
        from sqlalchemy import select, func
        
        db = self.db_session_factory()
        try:
            # First, get the playout and calculate total duration
            playout_stmt = select(Playout).where(
                Playout.channel_id == self.channel_id,
                Playout.is_active == True
            )
            playout_result = db.execute(playout_stmt)
            playout = playout_result.scalar_one_or_none()
            
            total_duration = 0
            item_count = 0
            
            if playout:
                # Calculate total schedule duration
                items_stmt = select(PlayoutItem, MediaItem).outerjoin(
                    MediaItem, PlayoutItem.media_item_id == MediaItem.id
                ).where(
                    PlayoutItem.playout_id == playout.id
                ).order_by(PlayoutItem.start_time)
                
                items_result = db.execute(items_stmt)
                items = items_result.all()
                item_count = len(items)
                
                for playout_item, media_item in items:
                    if media_item and media_item.duration:
                        total_duration += media_item.duration
                    elif playout_item.duration:
                        total_duration += int(playout_item.duration.total_seconds())
                    else:
                        total_duration += 1800  # Default 30 min
            
            # Load or create anchor time
            stmt = select(ChannelPlaybackPosition).where(
                ChannelPlaybackPosition.channel_id == self.channel_id
            )
            result = db.execute(stmt)
            position = result.scalar_one_or_none()
            
            now = datetime.utcnow()
            
            if position and position.playout_start_time:
                # Use saved anchor time (ErsatzTV-style)
                self._playout_start_time = position.playout_start_time
                
                # Calculate current position based on elapsed time
                if total_duration > 0:
                    elapsed = (now - self._playout_start_time).total_seconds()
                    cycle_position = elapsed % total_duration
                    
                    # Find which item corresponds to this cycle position
                    current_time = 0
                    calculated_index = 0
                    for idx, (playout_item, media_item) in enumerate(items):
                        if media_item and media_item.duration:
                            item_duration = media_item.duration
                        elif playout_item.duration:
                            item_duration = int(playout_item.duration.total_seconds())
                        else:
                            item_duration = 1800
                        
                        if current_time + item_duration > cycle_position:
                            calculated_index = idx
                            # Calculate seek offset within this item
                            raw_seek_offset = cycle_position - current_time
                            # Clamp seek offset to ensure it's within the item's duration
                            # Leave at least 10 seconds of content to play
                            max_seek = max(0, item_duration - 10) if item_duration > 10 else 0
                            self._seek_offset = min(raw_seek_offset, max_seek)
                            if raw_seek_offset > max_seek:
                                logger.debug(
                                    f"Channel {self.channel_number}: Clamped seek offset from "
                                    f"{raw_seek_offset:.0f}s to {self._seek_offset:.0f}s (duration: {item_duration}s)"
                                )
                            break
                        current_time += item_duration
                        calculated_index = idx + 1
                    
                    if calculated_index >= item_count:
                        calculated_index = 0
                        self._seek_offset = 0
                    
                    self._current_item_index = calculated_index
                    
                    # #region agent log
                    import json as _json, time as _time; open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log","a").write(_json.dumps({"hypothesisId":"H2","location":"channel_manager.py:_load_or_initialize_position","message":"ErsatzTV-style position calculation","data":{"channel_id":self.channel_id,"channel_number":self.channel_number,"anchor_time":str(self._playout_start_time),"elapsed_seconds":elapsed,"cycle_position":cycle_position,"total_duration":total_duration,"calculated_index":calculated_index,"item_count":item_count,"seek_offset":self._seek_offset},"timestamp":_time.time(),"sessionId":"debug-session"})+"\n")
                    # #endregion
                    
                    logger.info(
                        f"Resuming channel {self.channel_number} at calculated index "
                        f"{self._current_item_index} (elapsed: {elapsed:.0f}s, seek: {self._seek_offset:.0f}s, anchor: {self._playout_start_time})"
                    )
                else:
                    self._current_item_index = position.current_index or 0
                    logger.info(
                        f"Resuming channel {self.channel_number} at index "
                        f"{self._current_item_index} (no duration info)"
                    )
            else:
                # No anchor - initialize new continuous stream
                self._playout_start_time = now
                self._current_item_index = 0
                
                # Save the anchor time
                if position:
                    position.playout_start_time = now
                    position.current_index = 0
                    position.last_item_index = 0
                else:
                    from exstreamtv.database.models import ChannelPlaybackPosition as CPP
                    position = CPP(
                        channel_id=self.channel_id,
                        channel_number=str(self.channel_number),
                        current_index=0,
                        last_item_index=0,
                        playout_start_time=now,
                        last_played_at=now
                    )
                    db.add(position)
                db.commit()
                
                # #region agent log
                import json as _json, time as _time; open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log","a").write(_json.dumps({"hypothesisId":"H2","location":"channel_manager.py:_load_or_initialize_position","message":"New anchor created","data":{"channel_id":self.channel_id,"channel_number":self.channel_number,"anchor_time":str(self._playout_start_time)},"timestamp":_time.time(),"sessionId":"debug-session"})+"\n")
                # #endregion
                
                logger.info(
                    f"Starting channel {self.channel_number} from beginning with anchor: "
                    f"{self._playout_start_time}"
                )
        except Exception as e:
            logger.error(
                f"Error loading position for channel {self.channel_number}: {e}",
                exc_info=True
            )
            self._playout_start_time = datetime.utcnow()
            self._current_item_index = 0
        finally:
            db.close()

    async def stop(self) -> None:
        """Stop the continuous stream."""
        if not self._is_running:
            return

        async with self._lock:
            self._is_running = False
            
            if self._stream_task:
                self._stream_task.cancel()
                try:
                    await asyncio.wait_for(self._stream_task, timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Stream task for channel {self.channel_number} "
                        "did not cancel within timeout"
                    )
                except asyncio.CancelledError:
                    pass

            # Save position for resume
            await self._save_position()

            # Clear client queues
            self._client_queues.clear()
            
            logger.info(
                f"Stopped continuous stream for channel {self.channel_number} "
                "(position saved for resume)"
            )

    async def _save_position(self) -> None:
        """Save current playback position for resume."""
        from exstreamtv.database.models import ChannelPlaybackPosition
        from sqlalchemy import select
        
        # #region agent log
        import json as _json, time as _time; open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log","a").write(_json.dumps({"hypothesisId":"H1","location":"channel_manager.py:_save_position:entry","message":"Saving position to DB","data":{"channel_id":self.channel_id,"channel_number":self.channel_number,"current_item_index":self._current_item_index},"timestamp":_time.time(),"sessionId":"debug-session"})+"\n")
        # #endregion
        
        try:
            db = self.db_session_factory()
            try:
                stmt = select(ChannelPlaybackPosition).where(
                    ChannelPlaybackPosition.channel_id == self.channel_id
                )
                result = db.execute(stmt)
                position = result.scalar_one_or_none()
                
                if position:
                    # Update existing position
                    # CRITICAL: Update BOTH current_index and last_item_index
                    # current_index is used by channel_manager for resume
                    # last_item_index is used by EPG for guide display
                    position.current_index = self._current_item_index
                    position.last_item_index = self._current_item_index
                    position.last_played_at = datetime.utcnow()
                else:
                    # Create new position record
                    position = ChannelPlaybackPosition(
                        channel_id=self.channel_id,
                        channel_number=str(self.channel_number),
                        current_index=self._current_item_index,
                        last_item_index=self._current_item_index,
                        last_played_at=datetime.utcnow()
                    )
                    db.add(position)
                
                db.commit()
                
                # #region agent log
                import json as _json, time as _time; open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log","a").write(_json.dumps({"hypothesisId":"H1","location":"channel_manager.py:_save_position:success","message":"Position saved successfully","data":{"channel_id":self.channel_id,"saved_index":self._current_item_index},"timestamp":_time.time(),"sessionId":"debug-session"})+"\n")
                # #endregion
                
                logger.debug(
                    f"Saved position for channel {self.channel_number}: "
                    f"index {self._current_item_index}"
                )
            except Exception as e:
                db.rollback()
                logger.error(
                    f"Error saving position for channel {self.channel_number}: {e}"
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(
                f"Error saving position on stop for channel {self.channel_number}: {e}"
            )

    async def _get_current_position(self) -> dict[str, Any]:
        """Get current playback position."""
        async with self._timeline_lock:
            return {
                "item_index": self._current_item_index,
                "playout_start_time": self._playout_start_time,
                "current_item_start_time": self._current_item_start_time,
            }

    # Null TS packet for keep-alive (188 bytes, sync byte 0x47, null PID 0x1FFF)
    # This is a valid MPEG-TS null packet that players will accept but ignore
    _NULL_TS_PACKET = bytes([0x47, 0x1F, 0xFF, 0x10] + [0xFF] * 184)
    
    async def get_stream(self) -> AsyncIterator[bytes]:
        """
        Get the current stream.
        
        Joins existing continuous stream at current position (ErsatzTV-style).
        
        Yields:
            MPEG-TS data chunks.
        """
        # Ensure stream is running
        if not self._is_running:
            await self.start()
        
        # Create client queue FIRST so we receive chunks as soon as they're broadcast
        client_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        async with self._lock:
            self._client_queues.append(client_queue)
            self._client_count += 1
            
        logger.info(
            f"Client joined channel {self.channel_number} ({self.channel_name}), "
            f"total clients: {self._client_count}, is_running: {self._is_running}"
        )
        
        # Track consecutive timeouts for keep-alive
        consecutive_timeouts = 0
        max_consecutive_timeouts = 10  # After 10 timeouts (5 min), give up

        try:
            while self._is_running:
                try:
                    # Get data from client queue with timeout
                    chunk = await asyncio.wait_for(
                        client_queue.get(),
                        timeout=30.0,
                    )
                    
                    if chunk is None:
                        # End of stream signal
                        break
                    
                    # Reset timeout counter on successful data
                    consecutive_timeouts = 0
                    yield chunk
                    
                except asyncio.TimeoutError:
                    consecutive_timeouts += 1
                    
                    # Check if stream is still running
                    if not self._is_running:
                        logger.debug(
                            f"Channel {self.channel_number}: Stream stopped, ending client connection"
                        )
                        break
                    
                    # Check if we've exceeded max timeouts
                    if consecutive_timeouts >= max_consecutive_timeouts:
                        logger.warning(
                            f"Channel {self.channel_number}: No data for {consecutive_timeouts * 30}s, "
                            f"ending client connection"
                        )
                        break
                    
                    # Send null TS packets as keep-alive to prevent client timeout
                    # This keeps the HTTP connection alive and signals "still streaming"
                    logger.debug(
                        f"Channel {self.channel_number}: No data for 30s (timeout {consecutive_timeouts}), "
                        f"sending keep-alive packets"
                    )
                    
                    # Send a few null packets as keep-alive (7 packets = ~1.3KB)
                    for _ in range(7):
                        yield self._NULL_TS_PACKET
                    
        except asyncio.CancelledError:
            logger.debug(f"Client disconnected from channel {self.channel_number}")
            raise
            
        finally:
            async with self._lock:
                if client_queue in self._client_queues:
                    self._client_queues.remove(client_queue)
                self._client_count -= 1
                
            logger.debug(
                f"Client left channel {self.channel_number}, "
                f"remaining clients: {self._client_count}"
            )

    async def _resolve_media_url(self, media_item: Any) -> str:
        """
        Resolve a media item to a streamable URL using MediaURLResolver.
        
        Args:
            media_item: The media item to resolve
            
        Returns:
            Streamable URL string
        """
        try:
            from exstreamtv.streaming.url_resolver import get_url_resolver
            
            resolver = get_url_resolver()
            resolved = await resolver.resolve(media_item)
            
            logger.debug(
                f"Resolved URL for media {getattr(media_item, 'id', 'unknown')}: "
                f"{resolved.source_type.value}"
            )
            
            return resolved.url
            
        except Exception as e:
            logger.warning(f"URL resolution failed, using fallback: {e}")
            # Fallback to direct URL/path
            if hasattr(media_item, "url") and media_item.url:
                return media_item.url
            if hasattr(media_item, "path") and media_item.path:
                return media_item.path
            raise

    async def _get_next_playout_item(self) -> Optional[dict[str, Any]]:
        """
        Get the next item to play from the schedule.
        
        Returns:
            Dictionary with media_url and metadata, or None if no items available.
        """
        from exstreamtv.database.models import Playout, PlayoutItem, MediaItem
        from sqlalchemy import select
        from datetime import datetime
        
        db = self.db_session_factory()
        try:
            # First, get the playout for this channel
            playout_stmt = select(Playout).where(
                Playout.channel_id == self.channel_id,
                Playout.is_active == True
            )
            playout_result = db.execute(playout_stmt)
            playout = playout_result.scalar_one_or_none()
            
            if not playout:
                logger.debug(f"No active playout for channel {self.channel_id}")
                return None
            
            # Get playout items for THIS channel's playout
            items_stmt = select(PlayoutItem, MediaItem).outerjoin(
                MediaItem, PlayoutItem.media_item_id == MediaItem.id
            ).where(
                PlayoutItem.playout_id == playout.id
            ).order_by(PlayoutItem.start_time)
            
            items_result = db.execute(items_stmt)
            items = items_result.all()
            
            if not items:
                logger.debug(f"No playout items for channel {self.channel_id}, playout {playout.id}")
                return None
            
            # Get item at current index (wrap around if needed)
            if self._current_item_index >= len(items):
                self._current_item_index = 0
            
            playout_item, media_item = items[self._current_item_index]
            
            # Handle case where media_item is None (source_url only items)
            if media_item:
                # Resolve stream URL using MediaURLResolver
                stream_url = await self._resolve_media_url(media_item)
                title = media_item.title
                duration = media_item.duration
                source = media_item.source
                media_id = media_item.id
                
                # Log the resolved URL for debugging
                logger.info(
                    f"Channel {self.channel_number} resolved URL for '{title}': "
                    f"{stream_url[:100]}..." if len(stream_url) > 100 else stream_url
                )
            else:
                # Use source_url directly from playout item
                stream_url = playout_item.source_url
                title = playout_item.title
                duration = int(playout_item.duration.total_seconds()) if playout_item.duration else 0
                source = "url"
                media_id = None
            
            # Get seek offset (only for first item after position calculation)
            seek_offset = self._seek_offset
            self._seek_offset = 0.0  # Reset after using
            
            # CRITICAL FIX: Validate seek offset doesn't exceed media duration
            # If seek offset >= duration, FFmpeg will produce no output (seeks past EOF)
            if duration and seek_offset > 0:
                max_seek = max(0, duration - 10)  # Leave at least 10 seconds of content
                if seek_offset >= duration:
                    logger.warning(
                        f"Channel {self.channel_number}: Seek offset {seek_offset:.0f}s exceeds "
                        f"duration {duration}s for '{title}'. Resetting to 0."
                    )
                    seek_offset = 0.0
                elif seek_offset > max_seek:
                    logger.debug(
                        f"Channel {self.channel_number}: Clamping seek offset from {seek_offset:.0f}s "
                        f"to {max_seek:.0f}s for '{title}' (duration: {duration}s)"
                    )
                    seek_offset = max_seek
            
            return {
                "media_id": media_id,
                "media_url": stream_url,
                "title": title,
                "duration": duration,
                "source": source,
                "position": self._current_item_index,
                "expires_at": None,
                "seek_offset": seek_offset,  # ErsatzTV-style: seek into item
            }
            
        except Exception as e:
            logger.error(f"Error getting next playout item: {e}")
            return None
        finally:
            db.close()

    async def _run_continuous_stream(self) -> None:
        """
        Run the continuous stream loop with auto-recovery.
        
        Continuously plays items from the schedule, broadcasting to all clients.
        Includes automatic restart on failures with exponential backoff.
        """
        from exstreamtv.streaming.mpegts_streamer import MPEGTSStreamer
        from exstreamtv.streaming.process_watchdog import get_ffmpeg_watchdog
        from exstreamtv.tasks.health_tasks import update_channel_metric
        
        logger.info(f"Continuous stream loop started for channel {self.channel_number}")
        
        streamer = MPEGTSStreamer()
        watchdog = get_ffmpeg_watchdog()
        
        while self._is_running:
            try:
                await self._stream_loop(streamer, watchdog)
                
            except asyncio.CancelledError:
                logger.info(
                    f"Continuous stream loop cancelled for channel {self.channel_number}"
                )
                raise
                
            except Exception as e:
                logger.error(
                    f"Error in continuous stream for channel {self.channel_number}: {e}",
                    exc_info=True,
                )
                self._consecutive_failures += 1
                
                # Check if we should auto-restart
                if self._restart_count < self._max_restarts:
                    await self._auto_restart()
                else:
                    logger.error(
                        f"Channel {self.channel_number} exceeded max restarts "
                        f"({self._max_restarts}), stopping"
                    )
                    break
        
        # Signal end of stream to all clients
        await self._broadcast_end()
    
    async def _stream_loop(self, streamer: Any, watchdog: Any) -> None:
        """Inner streaming loop."""
        from exstreamtv.tasks.health_tasks import update_channel_metric
        
        while self._is_running:
            # Get next playout item from schedule
            playout_item = await self._get_next_playout_item()
            
            if playout_item is None:
                # Try to get filler content
                filler_item = await self._get_filler_item()
                if filler_item:
                    playout_item = filler_item
                    logger.debug(f"Using filler for channel {self.channel_number}")
                else:
                    # No content available - show offline slate or wait
                    logger.debug(
                        f"No content for channel {self.channel_number}, waiting..."
                    )
                    await asyncio.sleep(5.0)
                    continue
            
            logger.info(
                f"Channel {self.channel_number} playing: {playout_item.get('title')}"
            )
            
            # Get seek offset from playout item (ErsatzTV-style)
            seek_offset = playout_item.get("seek_offset", 0.0)
            
            # #region agent log
            import json as _json, time as _time; open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log","a").write(_json.dumps({"hypothesisId":"H4","location":"channel_manager.py:_stream_loop:playing","message":"Now playing item","data":{"channel_number":self.channel_number,"current_item_index":self._current_item_index,"title":playout_item.get("title"),"seek_offset":seek_offset},"timestamp":_time.time(),"sessionId":"debug-session"})+"\n")
            # #endregion
            
            # Update current item tracking
            self._current_item_start_time = datetime.utcnow()
            
            # Reset failure counter on successful item start
            self._consecutive_failures = 0
            
            # Stream the item
            try:
                media_url = playout_item.get("media_url")
                if not media_url:
                    logger.warning(f"Channel {self.channel_number}: No media_url for item {playout_item.get('title')}")
                    self._current_item_index += 1
                    await asyncio.sleep(0.1)  # Small delay before next item
                    continue
                    
                async for chunk in streamer.stream(media_url, seek_offset=seek_offset):
                        # Update health metrics
                        self._last_output_time = datetime.utcnow()
                        self._bytes_streamed += len(chunk)
                        update_channel_metric(
                            self.channel_id,
                            "last_output_time",
                            self._last_output_time
                        )
                        
                        # Report to watchdog
                        watchdog.report_output(
                            str(self.channel_id),
                            bytes_count=len(chunk)
                        )
                        
                        await self._broadcast_chunk(chunk)
                        if not self._is_running:
                            break
            except Exception as e:
                logger.error(
                    f"Error streaming item on channel {self.channel_number}: {e}"
                )
                self._consecutive_failures += 1
                await asyncio.sleep(1.0)
            
            # Advance to next item
            self._current_item_index += 1
            
            # Save position after EVERY item to ensure resume works correctly
            # This ensures EPG matches actual playback position and restart resumes properly
            await self._save_position()
    
    async def _auto_restart(self) -> None:
        """Restart channel after failure with exponential backoff."""
        self._restart_count += 1
        delay = self._restart_backoff_base * (2 ** self._restart_count)
        delay = min(delay, 60.0)  # Cap at 60 seconds
        
        logger.info(
            f"Auto-restarting channel {self.channel_number} "
            f"(attempt {self._restart_count}/{self._max_restarts}) in {delay:.1f}s"
        )
        
        self._last_restart_time = datetime.utcnow()
        
        # Broadcast error screen during restart delay if available
        if self._use_error_screens:
            try:
                await self._broadcast_error_screen(
                    title="Restarting",
                    subtitle=f"Attempt {self._restart_count}/{self._max_restarts}",
                    duration=delay,
                )
            except Exception as e:
                logger.debug(f"Error screen failed: {e}")
        
        await asyncio.sleep(delay)
    
    async def _broadcast_error_screen(
        self,
        title: str = "Technical Difficulties",
        subtitle: str = "We'll be right back",
        duration: float = 10.0,
    ) -> None:
        """
        Broadcast error screen to all clients during failures.
        
        This provides a graceful user experience instead of broken streams.
        
        Args:
            title: Error screen title
            subtitle: Error screen subtitle
            duration: Duration in seconds
        """
        if not HAS_ERROR_SCREENS:
            return
        
        try:
            generator = get_error_screen_generator()
            message = ErrorScreenMessage(
                title=title,
                subtitle=subtitle,
                channel_name=self.channel_name,
                channel_number=self.channel_number,
            )
            
            logger.debug(
                f"Channel {self.channel_number}: Broadcasting error screen: {title}"
            )
            
            async for chunk in generator.generate_error_stream(
                message=message,
                duration=duration,
            ):
                await self._broadcast_chunk(chunk)
                
        except Exception as e:
            logger.warning(f"Error screen generation failed: {e}")
    
    async def _get_filler_item(self) -> Optional[dict[str, Any]]:
        """
        Get a filler item to play when no scheduled content is available.
        
        Queries FillerPresetItem joined with MediaItem to get actual
        media content for filler playback.
        
        Returns:
            Filler item dictionary or None
        """
        from exstreamtv.database.models import (
            Channel, FillerPreset, FillerPresetItem, MediaItem
        )
        from sqlalchemy import select
        import random
        
        db = self.db_session_factory()
        try:
            # Get channel's filler preset
            channel_stmt = select(Channel).where(Channel.id == self.channel_id)
            channel_result = db.execute(channel_stmt)
            channel = channel_result.scalar_one_or_none()
            
            if not channel or not channel.fallback_filler_id:
                return None
            
            # Get filler preset to check collection reference
            preset_stmt = select(FillerPreset).where(
                FillerPreset.id == channel.fallback_filler_id
            )
            preset_result = db.execute(preset_stmt)
            preset = preset_result.scalar_one_or_none()
            
            if not preset:
                return None
            
            # Get filler items from preset joined with media items
            filler_stmt = select(FillerPresetItem, MediaItem).outerjoin(
                MediaItem, FillerPresetItem.media_item_id == MediaItem.id
            ).where(
                FillerPresetItem.preset_id == channel.fallback_filler_id
            )
            
            filler_result = db.execute(filler_stmt)
            filler_rows = filler_result.all()
            
            if not filler_rows:
                # No preset items, try to get from collection if set
                if preset.collection_id:
                    from exstreamtv.database.models import PlaylistItem
                    
                    playlist_stmt = select(PlaylistItem, MediaItem).join(
                        MediaItem, PlaylistItem.media_item_id == MediaItem.id
                    ).where(
                        PlaylistItem.playlist_id == preset.collection_id
                    )
                    playlist_result = db.execute(playlist_stmt)
                    playlist_rows = playlist_result.all()
                    
                    if playlist_rows:
                        playlist_item, media = random.choice(playlist_rows)
                        return {
                            "media_id": media.id,
                            "media_url": media.url or (
                                media.files[0].path if media.files else None
                            ),
                            "title": f"[Filler] {media.title}",
                            "duration": media.duration,
                            "source": "filler",
                            "is_filler": True,
                        }
                return None
            
            # Pick a random filler item based on weight
            weighted_items = []
            for filler_item, media in filler_rows:
                if media:
                    weight = filler_item.weight or 1
                    weighted_items.extend([(filler_item, media)] * weight)
            
            if not weighted_items:
                return None
            
            filler_item, media = random.choice(weighted_items)
            
            # Get media URL from MediaItem
            media_url = media.url
            if not media_url and hasattr(media, 'files') and media.files:
                media_url = media.files[0].path
            
            return {
                "media_id": media.id,
                "media_url": media_url,
                "title": f"[Filler] {media.title}",
                "duration": media.duration,
                "source": "filler",
                "is_filler": True,
            }
            
        except Exception as e:
            logger.warning(f"Error getting filler item: {e}")
            return None
        finally:
            db.close()

    async def _broadcast_chunk(self, chunk: bytes) -> None:
        """Broadcast a chunk to all connected clients."""
        # Apply throttling if enabled
        if self._use_throttling and self._throttler:
            try:
                async for throttled_chunk in self._throttler.throttle(chunk):
                    await self._send_to_clients(throttled_chunk)
            except Exception as e:
                logger.debug(f"Throttling error: {e}")
                await self._send_to_clients(chunk)
        else:
            await self._send_to_clients(chunk)
    
    async def _send_to_clients(self, chunk: bytes) -> None:
        """Send chunk to all connected client queues."""
        async with self._lock:
            if self._client_queues:
                logger.debug(
                    f"Channel {self.channel_number}: Broadcasting {len(chunk)} bytes to {len(self._client_queues)} clients"
                )
            for queue in self._client_queues:
                try:
                    queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    # Client can't keep up - skip this chunk for them
                    logger.debug(f"Channel {self.channel_number}: Client queue full, skipping chunk")
                    pass
    
    async def _report_to_ai_systems(
        self,
        event_type: str,
        message: str,
        level: str = "info",
        **extra_data: Any,
    ) -> None:
        """
        Report events to AI monitoring systems.
        
        Args:
            event_type: Type of event (error, warning, info)
            message: Event message
            level: Log level
            **extra_data: Additional data to include
        """
        # Report to unified log collector
        if HAS_LOG_COLLECTOR:
            try:
                collector = get_log_collector()
                from exstreamtv.ai_agent.unified_log_collector import LogEvent, LogLevel
                
                event = LogEvent(
                    event_id=f"ch_{self.channel_id}_{datetime.utcnow().timestamp()}",
                    timestamp=datetime.utcnow(),
                    source=LogSource.APPLICATION,
                    level=LogLevel(level),
                    message=message,
                    channel_id=self.channel_id,
                    component="channel_manager",
                    parsed_data=extra_data,
                )
                await collector.emit(event)
            except Exception as e:
                logger.debug(f"Log collector report failed: {e}")
        
        # Report FFmpeg-specific events to FFmpeg monitor
        if event_type == "ffmpeg_error" and HAS_FFMPEG_MONITOR:
            try:
                monitor = get_ffmpeg_monitor()
                await monitor.parse_stderr_line(message, self.channel_id)
            except Exception as e:
                logger.debug(f"FFmpeg monitor report failed: {e}")

    async def _broadcast_end(self) -> None:
        """Signal end of stream to all clients."""
        async with self._lock:
            for queue in self._client_queues:
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass

    @property
    def is_running(self) -> bool:
        """Check if stream is running."""
        return self._is_running

    @property
    def client_count(self) -> int:
        """Get number of connected clients."""
        return self._client_count


class ChannelManager:
    """
    Manages all channel streams.
    
    Provides centralized control over channel lifecycle and client connections.
    """

    def __init__(self, db_session_factory: Callable[[], Session]):
        """
        Initialize channel manager.
        
        Args:
            db_session_factory: Factory function to create database sessions.
        """
        self.db_session_factory = db_session_factory
        self._channels: dict[int, ChannelStream] = {}
        self._lock = asyncio.Lock()
        self._is_running = False

    async def start(self) -> None:
        """Start the channel manager (lazy startup - channels start on first request)."""
        async with self._lock:
            if self._is_running:
                return
            
            self._is_running = True
            logger.info("Channel manager started (lazy mode - channels start on demand)")
    
    async def prewarm_channels(self, channel_ids: list[int] | None = None) -> dict[int, bool]:
        """
        Pre-warm channels by starting them before first client request.
        
        This eliminates cold-start delays by ensuring channels are already
        streaming when clients tune in.
        
        Args:
            channel_ids: Optional list of channel IDs to pre-warm.
                        If None, pre-warms all enabled channels.
        
        Returns:
            Dictionary mapping channel_id to success status.
        """
        from exstreamtv.database.models import Channel
        from sqlalchemy import select
        
        results: dict[int, bool] = {}
        
        # Get channels to pre-warm
        db = self.db_session_factory()
        try:
            if channel_ids:
                stmt = select(Channel).where(
                    Channel.id.in_(channel_ids),
                    Channel.enabled == True
                )
            else:
                stmt = select(Channel).where(Channel.enabled == True)
            
            result = db.execute(stmt)
            channels = result.scalars().all()
            
            if not channels:
                logger.info("No enabled channels found to pre-warm")
                return results
            
            logger.info(f"Pre-warming {len(channels)} channels...")
            
            for channel in channels:
                try:
                    # Get or create the channel stream
                    channel_stream = await self.get_channel_stream(
                        channel_id=channel.id,
                        channel_number=channel.number,
                        channel_name=channel.name,
                    )
                    
                    # Start the stream if not already running
                    if not channel_stream.is_running:
                        await channel_stream.start()
                        logger.info(
                            f"Pre-warmed channel {channel.number} ({channel.name})"
                        )
                    else:
                        logger.debug(
                            f"Channel {channel.number} already running, skipping pre-warm"
                        )
                    
                    results[channel.id] = True
                    
                except Exception as e:
                    logger.error(
                        f"Failed to pre-warm channel {channel.number} ({channel.name}): {e}"
                    )
                    results[channel.id] = False
            
            # Summary
            success_count = sum(1 for v in results.values() if v)
            fail_count = len(results) - success_count
            logger.info(
                f"Pre-warming complete: {success_count} succeeded, {fail_count} failed"
            )
            
        except Exception as e:
            logger.error(f"Error during channel pre-warming: {e}")
        finally:
            db.close()
        
        return results

    async def stop(self) -> None:
        """Stop all channels and the manager."""
        async with self._lock:
            if not self._is_running:
                return
                
            self._is_running = False
            
            # Stop all channels
            for channel_id, channel_stream in list(self._channels.items()):
                try:
                    await channel_stream.stop()
                except Exception as e:
                    logger.error(f"Error stopping channel {channel_id}: {e}")
            
            self._channels.clear()
            logger.info("Channel manager stopped")

    async def get_channel_stream(
        self,
        channel_id: int,
        channel_number: int,
        channel_name: str,
    ) -> ChannelStream:
        """
        Get or create a channel stream.
        
        Args:
            channel_id: Database ID of the channel.
            channel_number: Channel number for display.
            channel_name: Channel name for logging.
            
        Returns:
            ChannelStream for the channel.
        """
        async with self._lock:
            if channel_id not in self._channels:
                channel_stream = ChannelStream(
                    channel_id=channel_id,
                    channel_number=channel_number,
                    channel_name=channel_name,
                    db_session_factory=self.db_session_factory,
                )
                self._channels[channel_id] = channel_stream
                
            return self._channels[channel_id]

    async def start_channel(
        self,
        channel_id: int,
        channel_number: int,
        channel_name: str,
    ) -> ChannelStream:
        """
        Start a specific channel.
        
        Args:
            channel_id: Database ID of the channel.
            channel_number: Channel number for display.
            channel_name: Channel name for logging.
            
        Returns:
            Started ChannelStream.
        """
        channel_stream = await self.get_channel_stream(
            channel_id, channel_number, channel_name
        )
        await channel_stream.start()
        return channel_stream

    async def stop_channel(self, channel_id: int) -> None:
        """Stop a specific channel."""
        async with self._lock:
            if channel_id in self._channels:
                await self._channels[channel_id].stop()
                del self._channels[channel_id]

    def get_active_channels(self) -> list[int]:
        """Get list of active channel IDs."""
        return [
            channel_id
            for channel_id, stream in self._channels.items()
            if stream.is_running
        ]

    def get_channel_status(self, channel_id: int) -> dict[str, Any]:
        """Get status of a specific channel."""
        if channel_id not in self._channels:
            return {"running": False, "clients": 0}
            
        stream = self._channels[channel_id]
        return {
            "running": stream.is_running,
            "clients": stream.client_count,
            "channel_number": stream.channel_number,
            "channel_name": stream.channel_name,
        }
