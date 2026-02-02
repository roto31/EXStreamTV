"""
Configuration management for EXStreamTV.

Handles loading, validation, and access to application configuration.
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

# Global configuration instance
_config: Optional["EXStreamTVConfig"] = None


class ServerConfig(BaseModel):
    """Server configuration."""
    host: str = "0.0.0.0"
    port: int = 8411
    debug: bool = False
    log_level: str = "INFO"
    base_url: str = "http://localhost:8411"
    public_url: Optional[str] = None  # Optional public URL for external access


class DatabaseConfig(BaseModel):
    """Database configuration."""
    url: str = "sqlite:///./exstreamtv.db"
    echo: bool = False


class HardwareAccelerationConfig(BaseModel):
    """Hardware acceleration settings."""
    enabled: bool = True
    preferred: str = "auto"
    fallback_to_software: bool = True


class FFmpegDefaultsConfig(BaseModel):
    """Default FFmpeg encoding settings."""
    video_bitrate: str = "4000k"
    audio_bitrate: str = "128k"
    video_codec: str = "h264"
    audio_codec: str = "aac"
    resolution: str = "1920x1080"
    framerate: int = 30


class FFmpegTimeoutsConfig(BaseModel):
    """FFmpeg timeout settings."""
    connection: int = 30
    read: int = 60
    youtube: int = 120
    archive_org: int = 90


class FFmpegConfig(BaseModel):
    """FFmpeg configuration."""
    path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    log_level: str = "warning"  # FFmpeg log level: quiet, panic, fatal, error, warning, info, verbose, debug
    threads: int = 0  # 0 = auto (let FFmpeg decide), >0 = specific thread count
    hwaccel_device: Optional[str] = None  # Specific device for hardware acceleration (e.g., /dev/dri/renderD128)
    extra_flags: Optional[str] = None  # Additional FFmpeg flags (e.g., "-max_muxing_queue_size 9999")
    hardware_acceleration: HardwareAccelerationConfig = Field(
        default_factory=HardwareAccelerationConfig
    )
    defaults: FFmpegDefaultsConfig = Field(default_factory=FFmpegDefaultsConfig)
    timeouts: FFmpegTimeoutsConfig = Field(default_factory=FFmpegTimeoutsConfig)
    
    # Per-source hardware acceleration overrides
    youtube_hwaccel: Optional[str] = None
    archive_org_hwaccel: Optional[str] = None
    plex_hwaccel: Optional[str] = None
    
    # Per-source video encoder overrides
    youtube_video_encoder: Optional[str] = None
    archive_org_video_encoder: Optional[str] = None
    plex_video_encoder: Optional[str] = None
    
    @property
    def ffmpeg_path(self) -> str:
        """Alias for path for backward compatibility."""
        return self.path


class StreamingConfig(BaseModel):
    """Streaming configuration."""
    buffer_size: int = 2097152  # 2MB
    read_size: int = 65536  # 64KB


class HDHomeRunConfig(BaseModel):
    """HDHomeRun emulation configuration."""
    enabled: bool = True
    device_id: str = "EXSTREAMTV"
    device_auth: str = "exstreamtv"
    tuner_count: int = 4
    friendly_name: str = "EXStreamTV"


class ChannelsConfig(BaseModel):
    """Channel configuration."""
    default_guide_hours: int = 24
    auto_refresh_interval: int = 3600
    max_concurrent_streams: int = 10


class PlexConfig(BaseModel):
    """Plex integration configuration."""
    enabled: bool = False
    url: str = ""
    base_url: str = ""  # Alias for url
    token: str = ""


class JellyfinConfig(BaseModel):
    """Jellyfin integration configuration."""
    enabled: bool = False
    url: str = ""
    api_key: str = ""


class EmbyConfig(BaseModel):
    """Emby integration configuration."""
    enabled: bool = False
    url: str = ""
    api_key: str = ""


class LocalLibraryConfig(BaseModel):
    """Local folder library configuration."""
    enabled: bool = True
    paths: list[str] = Field(default_factory=list)
    scan_interval: int = 3600


class LibrariesConfig(BaseModel):
    """Media libraries configuration."""
    plex: PlexConfig = Field(default_factory=PlexConfig)
    jellyfin: JellyfinConfig = Field(default_factory=JellyfinConfig)
    emby: EmbyConfig = Field(default_factory=EmbyConfig)
    local: LocalLibraryConfig = Field(default_factory=LocalLibraryConfig)


class YouTubeConfig(BaseModel):
    """YouTube source configuration."""
    enabled: bool = True
    cookies_file: str = ""
    rate_limit: int = 5
    quality: str = "best[height<=1080]"


class ArchiveOrgConfig(BaseModel):
    """Archive.org source configuration."""
    enabled: bool = True
    rate_limit: int = 10


class SourcesConfig(BaseModel):
    """Online sources configuration."""
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig)
    archive_org: ArchiveOrgConfig = Field(default_factory=ArchiveOrgConfig)


class OllamaConfig(BaseModel):
    """Ollama AI configuration (legacy)."""
    host: str = "http://localhost:11434"
    model: str = "llama2"


class AutoHealerConfig(BaseModel):
    """Auto-healer and troubleshooting configuration."""
    enabled: bool = True
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"
    auto_fix: bool = False
    dry_run: bool = True
    learning_enabled: bool = True


class AIAutoHealConfig(BaseModel):
    """
    Enhanced AI self-healing configuration.
    
    Provides granular control over all AI features for autonomous
    issue detection, diagnosis, and resolution.
    """
    # Master switch
    enabled: bool = True
    
    # Log collection
    log_buffer_minutes: int = 30
    realtime_streaming: bool = True
    
    # FFmpeg monitoring
    ffmpeg_monitor_enabled: bool = True
    ffmpeg_health_threshold: float = 0.8  # Speed threshold for healthy
    
    # Pattern detection
    pattern_detection_enabled: bool = True
    prediction_confidence_threshold: float = 0.75
    
    # Auto resolution
    auto_resolve_enabled: bool = True
    max_auto_fixes_per_hour: int = 50
    require_approval_above_risk: str = "MEDIUM"  # SAFE, LOW, MEDIUM, HIGH
    
    # Zero-downtime features
    use_error_screen_fallback: bool = True
    hot_swap_enabled: bool = True
    
    # Learning
    learning_enabled: bool = True
    min_success_rate_for_auto: float = 0.9
    
    # Individual feature toggles
    self_healing_toggle: bool = True
    channel_creator_toggle: bool = True
    troubleshooting_toggle: bool = True


class DatabaseBackupConfig(BaseModel):
    """Database backup configuration."""
    enabled: bool = True
    backup_directory: str = "backups"
    interval_hours: int = 24
    keep_count: int = 7
    keep_days: int = 30
    compress: bool = True


class SessionManagerConfig(BaseModel):
    """Session manager configuration."""
    max_sessions_per_channel: int = 50
    idle_timeout_seconds: int = 300
    cleanup_interval_seconds: int = 60


class StreamThrottlerConfig(BaseModel):
    """Stream throttler configuration."""
    enabled: bool = True
    target_bitrate_bps: int = 4_000_000
    mode: str = "realtime"  # realtime, burst, adaptive, disabled


class CloudProviderFallback(BaseModel):
    """Fallback cloud provider configuration."""
    provider: str = "sambanova"
    api_key: str = ""
    model: str = ""


class CloudProviderConfig(BaseModel):
    """Cloud AI provider configuration."""
    provider: str = "groq"
    api_key: str = ""
    model: str = "llama-3.3-70b-versatile"
    fallback: list[CloudProviderFallback] = Field(default_factory=list)


class LocalProviderConfig(BaseModel):
    """Local AI provider (Ollama) configuration."""
    host: str = "http://localhost:11434"
    model: str = "auto"


class AISettingsConfig(BaseModel):
    """AI generation settings."""
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: float = 30.0


class AIAgentConfig(BaseModel):
    """AI agent configuration with unified provider support."""
    enabled: bool = True
    log_analysis: bool = True
    auto_fix: bool = False
    
    # Provider type: cloud, local, or hybrid
    provider_type: str = "cloud"
    
    # Cloud provider settings
    cloud: CloudProviderConfig = Field(default_factory=CloudProviderConfig)
    
    # Local provider settings (Ollama)
    local: LocalProviderConfig = Field(default_factory=LocalProviderConfig)
    
    # Generation settings
    settings: AISettingsConfig = Field(default_factory=AISettingsConfig)
    
    # Legacy settings (deprecated, for backwards compatibility)
    model: str = "gpt-4"
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    auto_healer: AutoHealerConfig = Field(default_factory=AutoHealerConfig)


class FillerConfig(BaseModel):
    """Filler content configuration."""
    enabled: bool = True
    fallback_mode: str = "loop"
    offline_image: str = ""


class EPGConfig(BaseModel):
    """EPG configuration."""
    refresh_interval: int = 3600
    days_ahead: int = 7


class SchedulingConfig(BaseModel):
    """Scheduling configuration."""
    default_mode: str = "continuous"
    filler: FillerConfig = Field(default_factory=FillerConfig)
    epg: EPGConfig = Field(default_factory=EPGConfig)


class PlayoutConfig(BaseModel):
    """Playout configuration."""
    build_days: int = 7
    prebuffer_minutes: int = 5
    max_concurrent: int = 10


class SecurityConfig(BaseModel):
    """Security configuration."""
    enabled: bool = False
    admin_password: str = ""
    session_timeout: int = 86400
    api_key_required: bool = False
    access_token: str | None = None


class LogLifecycleConfig(BaseModel):
    """Log lifecycle management configuration."""
    enabled: bool = True
    max_file_size_mb: int = 50  # Truncate logs larger than this
    archive_after_days: int = 7  # Archive logs older than 7 days
    delete_after_days: int = 30  # Delete archives older than 30 days
    archive_directory: str = "logs/archive"


class BrowserLogsConfig(BaseModel):
    """Browser logs configuration."""
    enabled: bool = True
    file: str = "logs/browser.log"


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    file: str = "logs/exstreamtv.log"
    max_size: str = "10MB"
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    browser_logs: BrowserLogsConfig = Field(default_factory=BrowserLogsConfig)
    lifecycle: LogLifecycleConfig = Field(default_factory=LogLifecycleConfig)


class EXStreamTVConfig(BaseModel):
    """Main EXStreamTV configuration."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    ffmpeg: FFmpegConfig = Field(default_factory=FFmpegConfig)
    streaming: StreamingConfig = Field(default_factory=StreamingConfig)
    hdhomerun: HDHomeRunConfig = Field(default_factory=HDHomeRunConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    libraries: LibrariesConfig = Field(default_factory=LibrariesConfig)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    ai_agent: AIAgentConfig = Field(default_factory=AIAgentConfig)
    scheduling: SchedulingConfig = Field(default_factory=SchedulingConfig)
    playout: PlayoutConfig = Field(default_factory=PlayoutConfig)
    plex: PlexConfig = Field(default_factory=PlexConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    auto_healer: AutoHealerConfig = Field(default_factory=AutoHealerConfig)
    
    # New configurations from Tunarr/dizqueTV integration
    ai_auto_heal: AIAutoHealConfig = Field(default_factory=AIAutoHealConfig)
    database_backup: DatabaseBackupConfig = Field(default_factory=DatabaseBackupConfig)
    session_manager: SessionManagerConfig = Field(default_factory=SessionManagerConfig)
    stream_throttler: StreamThrottlerConfig = Field(default_factory=StreamThrottlerConfig)


def load_config(config_path: Optional[str] = None) -> EXStreamTVConfig:
    """
    Load configuration from file.
    
    Args:
        config_path: Path to config file. Defaults to config.yaml in project root.
        
    Returns:
        Loaded and validated configuration.
    """
    global _config
    
    if config_path is None:
        # Look for config.yaml in current directory or project root
        possible_paths = [
            Path("config.yaml"),
            Path(__file__).parent.parent / "config.yaml",
        ]
        for path in possible_paths:
            if path.exists():
                config_path = str(path)
                break
    
    config_data: dict[str, Any] = {}
    
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}
    
    # Apply environment variable overrides
    env_overrides = _get_env_overrides()
    _deep_merge(config_data, env_overrides)
    
    _config = EXStreamTVConfig(**config_data)
    return _config


def get_config() -> EXStreamTVConfig:
    """
    Get the current configuration.
    
    Returns:
        Current configuration (loads default if not yet loaded).
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> EXStreamTVConfig:
    """
    Reload configuration from disk.
    
    Use this after config.yaml has been modified to pick up changes.
    
    Returns:
        Freshly loaded configuration.
    """
    global _config
    _config = None
    return load_config()


def _get_env_overrides() -> dict[str, Any]:
    """Get configuration overrides from environment variables."""
    overrides: dict[str, Any] = {}
    
    # Map of environment variables to config paths
    env_map = {
        "EXSTREAMTV_HOST": ("server", "host"),
        "EXSTREAMTV_PORT": ("server", "port"),
        "EXSTREAMTV_DEBUG": ("server", "debug"),
        "EXSTREAMTV_DATABASE_URL": ("database", "url"),
        "EXSTREAMTV_FFMPEG_PATH": ("ffmpeg", "path"),
        "EXSTREAMTV_PLEX_URL": ("libraries", "plex", "url"),
        "EXSTREAMTV_PLEX_TOKEN": ("libraries", "plex", "token"),
        "EXSTREAMTV_JELLYFIN_URL": ("libraries", "jellyfin", "url"),
        "EXSTREAMTV_JELLYFIN_API_KEY": ("libraries", "jellyfin", "api_key"),
    }
    
    for env_var, path in env_map.items():
        value = os.environ.get(env_var)
        if value is not None:
            _set_nested(overrides, path, _parse_env_value(value))
    
    return overrides


def _parse_env_value(value: str) -> Any:
    """Parse environment variable value to appropriate type."""
    # Boolean
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    
    # Integer
    try:
        return int(value)
    except ValueError:
        pass
    
    # Float
    try:
        return float(value)
    except ValueError:
        pass
    
    return value


def _set_nested(d: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    """Set a nested dictionary value from a path tuple."""
    for key in path[:-1]:
        d = d.setdefault(key, {})
    d[path[-1]] = value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Deep merge override into base dictionary."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


class _ConfigProxy:
    """
    Proxy object that provides lazy access to configuration.
    
    Allows modules to import `config` directly and access it like:
        from exstreamtv.config import config
        config.server.port
    
    The actual config is loaded on first attribute access.
    """
    
    def __getattr__(self, name: str) -> Any:
        return getattr(get_config(), name)
    
    def __repr__(self) -> str:
        return f"<ConfigProxy for {get_config()}>"


# Lazy config instance for backward compatibility
# Usage: from exstreamtv.config import config
config = _ConfigProxy()
