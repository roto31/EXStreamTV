"""
EXStreamTV Integration Module

Provides integrations with external services:
- IPTV sources (M3U, Xtream Codes)
- HDHomeRun tuner input
- Notification services (Discord, Telegram, Pushover, Slack)
- Home Assistant
- Cloud storage (Google Drive, Dropbox, S3)
- Plugin system
"""

from exstreamtv.integration.iptv_sources import (
    IPTVSourceManager,
    IPTVSourceConfig,
    IPTVChannel,
    M3USourceProvider,
    XtreamCodesProvider,
    SourceType,
    iptv_source_manager,
)

from exstreamtv.integration.hdhomerun_tuner import (
    HDHomeRunManager,
    HDHomeRunDevice,
    TunerChannel,
    hdhomerun_manager,
)

from exstreamtv.integration.notifications import (
    NotificationManager,
    Notification,
    NotificationType,
    NotificationPriority,
    DiscordService,
    DiscordConfig,
    TelegramService,
    TelegramConfig,
    PushoverService,
    PushoverConfig,
    SlackService,
    SlackConfig,
    notification_manager,
)

from exstreamtv.integration.homeassistant import (
    HomeAssistantIntegration,
    HAConfig,
    HAMediaPlayerState,
    setup_homeassistant,
    shutdown_homeassistant,
)

from exstreamtv.integration.plugins import (
    PluginManager,
    Plugin,
    PluginInfo,
    PluginType,
    PluginState,
    SourcePlugin,
    ProviderPlugin,
    NotificationPlugin,
    HookType,
    setup_plugins,
    shutdown_plugins,
    get_plugin_manager,
)

from exstreamtv.integration.cloud_storage import (
    CloudStorageManager,
    CloudStorageConfig,
    CloudFile,
    CloudProvider,
    GoogleDriveProvider,
    GoogleDriveConfig,
    DropboxProvider,
    DropboxConfig,
    S3Provider,
    S3Config,
    cloud_storage_manager,
)

__all__ = [
    # IPTV Sources
    "IPTVSourceManager",
    "IPTVSourceConfig",
    "IPTVChannel",
    "M3USourceProvider",
    "XtreamCodesProvider",
    "SourceType",
    "iptv_source_manager",
    
    # HDHomeRun
    "HDHomeRunManager",
    "HDHomeRunDevice",
    "TunerChannel",
    "hdhomerun_manager",
    
    # Notifications
    "NotificationManager",
    "Notification",
    "NotificationType",
    "NotificationPriority",
    "DiscordService",
    "DiscordConfig",
    "TelegramService",
    "TelegramConfig",
    "PushoverService",
    "PushoverConfig",
    "SlackService",
    "SlackConfig",
    "notification_manager",
    
    # Home Assistant
    "HomeAssistantIntegration",
    "HAConfig",
    "HAMediaPlayerState",
    "setup_homeassistant",
    "shutdown_homeassistant",
    
    # Plugins
    "PluginManager",
    "Plugin",
    "PluginInfo",
    "PluginType",
    "PluginState",
    "SourcePlugin",
    "ProviderPlugin",
    "NotificationPlugin",
    "HookType",
    "setup_plugins",
    "shutdown_plugins",
    "get_plugin_manager",
    
    # Cloud Storage
    "CloudStorageManager",
    "CloudStorageConfig",
    "CloudFile",
    "CloudProvider",
    "GoogleDriveProvider",
    "GoogleDriveConfig",
    "DropboxProvider",
    "DropboxConfig",
    "S3Provider",
    "S3Config",
    "cloud_storage_manager",
]
