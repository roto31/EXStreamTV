"""
TVDB Client v2

Provides TVDB (The TV Database) API client v2.
"""

from exstreamtv.metadata.clients.tvdb_client import TVDBClient

# Alias for v2 naming
TVDBClientV2 = TVDBClient

__all__ = ["TVDBClient", "TVDBClientV2"]
