"""
Media library integrations.
"""

from exstreamtv.media.libraries.base import LibraryManager, BaseLibrary, LibraryType
from exstreamtv.media.libraries.local import LocalLibrary
from exstreamtv.media.libraries.plex import PlexLibrary
from exstreamtv.media.libraries.jellyfin import JellyfinLibrary, EmbyLibrary

__all__ = [
    "LibraryManager",
    "BaseLibrary",
    "LibraryType",
    "LocalLibrary",
    "PlexLibrary",
    "JellyfinLibrary",
    "EmbyLibrary",
]
