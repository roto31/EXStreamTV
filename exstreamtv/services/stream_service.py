"""
Stream orchestration facade: ChannelContext FSM + ChannelManager integration.

Routers and tasks should enqueue commands on StreamCommandQueue rather than
calling start_channel/stop_channel directly when serialized semantics are required.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

from exstreamtv.patterns.commands.config_types import TranscodeConfig
from exstreamtv.patterns.state import ChannelContext, StreamError

if TYPE_CHECKING:
    from exstreamtv.streaming.channel_manager import ChannelManager

logger = logging.getLogger(__name__)


class StreamService:
    """Owns per-channel ChannelContext instances keyed by str(channel_db_id)."""

    def __init__(self, channel_manager: ChannelManager) -> None:
        self._channel_manager = channel_manager
        self._contexts: dict[str, ChannelContext] = {}
        self._transcode_configs: dict[str, TranscodeConfig] = {}
        # Issue 6.4: Lock guards check-then-set on _contexts to prevent
        # duplicate ChannelStream creation under concurrent requests.
        self._lock = asyncio.Lock()

    @property
    def contexts(self) -> dict[str, ChannelContext]:
        return self._contexts

    def set_transcode_config(self, channel_id: str, cfg: TranscodeConfig) -> None:
        self._transcode_configs[channel_id] = cfg

    def get_transcode_config(self, channel_id: str) -> TranscodeConfig | None:
        return self._transcode_configs.get(channel_id)

    async def get_context(self, channel_id: str) -> ChannelContext | None:
        return self._contexts.get(channel_id)

    async def get_or_create_context(self, channel_id: str) -> ChannelContext:
        # Issue 6.4: Lock prevents two concurrent requests from both
        # passing the membership check and creating duplicate contexts.
        async with self._lock:
            if channel_id in self._contexts:
                return self._contexts[channel_id]
            return await self._create_context_locked(channel_id)

    async def _create_context_locked(self, channel_id: str) -> ChannelContext:
        """Create and register a new context. Caller must hold self._lock."""
        try:
            cid = int(channel_id, 10)
        except ValueError as e:
            raise StreamError(f"Invalid channel_id {channel_id!r}") from e

        from exstreamtv.database.models import Channel

        db = self._channel_manager.db_session_factory()
        try:
            row = db.execute(select(Channel).where(Channel.id == cid)).scalar_one_or_none()
        finally:
            db.close()

        if row is None:
            raise StreamError(f"Unknown channel id {channel_id}")

        ctx = ChannelContext(
            channel_id=channel_id,
            channel_db_id=row.id,
            channel_number=row.number,
            channel_name=row.name,
            channel_manager=self._channel_manager,
        )
        try:
            stream = await self._channel_manager.get_channel_stream(
                row.id, row.number, row.name
            )
            ctx.sync_state_from_stream_running(stream.is_running)
        except Exception as e:
            logger.debug(
                "_create_context_locked: could not sync stream state for %s: %s",
                channel_id,
                e,
            )
        self._contexts[channel_id] = ctx
        return ctx

    async def start_channel(self, channel_id: str) -> bool:
        """Direct start (prefers FSM Idle -> Starting); for legacy callers."""
        ctx = await self.get_or_create_context(channel_id)
        await ctx.get_state().start(ctx)
        return True

    async def stop_channel(self, channel_id: str) -> bool:
        """Stop channel and clean up context (Issue 3.1: prevents unbounded growth)."""
        ctx = await self.get_context(channel_id)
        if ctx is None:
            return True
        try:
            await ctx.get_state().stop(ctx)
        finally:
            # Issue 3.1/3.2: Remove context and config to prevent unbounded dict growth.
            # Cleanup runs even if stop() raises so dicts never grow unbounded.
            async with self._lock:
                self._contexts.pop(channel_id, None)
                self._transcode_configs.pop(channel_id, None)
        return True

    async def on_health_check_passed(self, channel_id: str) -> None:
        ctx = await self.get_context(channel_id)
        if ctx:
            await ctx.get_state().on_health_check_passed(ctx)

    async def on_health_check_failed(self, channel_id: str) -> None:
        ctx = await self.get_context(channel_id)
        if ctx:
            await ctx.get_state().on_health_check_failed(ctx)

    async def sync_context_from_stream(self, channel_id: str, is_running: bool) -> None:
        """Align FSM with ChannelStream.is_running when health pipeline updates."""
        ctx = await self.get_context(channel_id)
        if ctx:
            ctx.sync_state_from_stream_running(is_running)

    def is_stream_running_fsm(self, channel_id: str) -> bool:
        ctx = self._contexts.get(channel_id)
        if not ctx:
            return False
        return ctx.get_state().is_running()
