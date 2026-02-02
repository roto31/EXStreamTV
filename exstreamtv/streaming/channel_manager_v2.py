"""
Channel Manager v2 Compatibility Module

This module provides backward compatibility for v2 modules that import
from channel_manager_v2. It re-exports the main channel manager.

DEPRECATED: This module is deprecated and will be removed in a future version.
Import from exstreamtv.streaming.channel_manager instead.
"""

import warnings

warnings.warn(
    "channel_manager_v2 is deprecated. Import from exstreamtv.streaming.channel_manager directly.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from main channel_manager
from exstreamtv.streaming.channel_manager import (
    ChannelManager,
    ChannelStream,
)

# Aliases for v2 naming conventions
ChannelManagerV2 = ChannelManager
ChannelStreamV2 = ChannelStream

__all__ = [
    "ChannelManager",
    "ChannelManagerV2",
    "ChannelStream",
    "ChannelStreamV2",
]
