"""
Metadata Clients Package

Provides clients for various metadata providers.
"""

from exstreamtv.metadata.clients.base import MetadataClient
from exstreamtv.metadata.clients.tmdb_client_v2 import TMDBClient, TMDBClientV2
from exstreamtv.metadata.clients.tvdb_client import TVDBClient
from exstreamtv.metadata.clients.tvdb_client_v2 import TVDBClientV2

__all__ = [
    "MetadataClient",
    "TMDBClient",
    "TMDBClientV2",
    "TVDBClient",
    "TVDBClientV2",
]
