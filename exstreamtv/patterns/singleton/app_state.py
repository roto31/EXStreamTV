from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exstreamtv.patterns.chain.url_resolvers import URLResolver
    from exstreamtv.patterns.commands.command_queue import StreamCommandQueue
    from exstreamtv.patterns.mediator.stream_mediator import StreamMediator
    from exstreamtv.patterns.observer.event_bus import StreamEventBus
    from exstreamtv.services.stream_service import StreamService


@dataclass
class PatternRuntimeState:
    """Document pattern singletons attached to FastAPI app.state in lifespan."""

    stream_service: StreamService | None = None
    command_queue: StreamCommandQueue | None = None
    url_resolver_chain: URLResolver | None = None
    mediator: StreamMediator | None = None
    event_bus: StreamEventBus | None = None
    streamlink_session: Any | None = None
