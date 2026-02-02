"""Importers for creating channels and content from YAML files and M3U playlists

This module provides importers for:
- YAML channel configuration files
- M3U/M3U8 playlists
- ErsatzTV database migration
- StreamTV database migration
"""

# Lazy imports to avoid circular dependencies during testing
# Core importers with database dependencies are imported on-demand
def __getattr__(name):
    """Lazy import for module attributes."""
    if name == "ChannelImporter":
        from .channel_importer import ChannelImporter
        return ChannelImporter
    elif name == "import_channels_from_yaml":
        from .channel_importer import import_channels_from_yaml
        return import_channels_from_yaml
    elif name == "M3UEntry":
        from .m3u_importer import M3UEntry
        return M3UEntry
    elif name == "M3UImporter":
        from .m3u_importer import M3UImporter
        return M3UImporter
    elif name == "M3UParser":
        from .m3u_importer import M3UParser
        return M3UParser
    elif name == "import_channels_from_m3u":
        from .m3u_importer import import_channels_from_m3u
        return import_channels_from_m3u
    elif name == "M3UMetadataEnricher":
        from .m3u_metadata import M3UMetadataEnricher
        return M3UMetadataEnricher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ChannelImporter",
    "M3UEntry",
    "M3UImporter",
    "M3UMetadataEnricher",
    "M3UParser",
    "import_channels_from_m3u",
    "import_channels_from_yaml",
]
