"""
Mock Jellyfin/Emby API responses for testing.
"""

JELLYFIN_LIBRARIES = {
    "Items": [
        {
            "Id": "abc123def456",
            "Name": "Movies",
            "CollectionType": "movies",
            "Type": "CollectionFolder",
            "IsFolder": True,
        },
        {
            "Id": "ghi789jkl012",
            "Name": "TV Shows",
            "CollectionType": "tvshows",
            "Type": "CollectionFolder",
            "IsFolder": True,
        },
    ],
    "TotalRecordCount": 2,
}

JELLYFIN_ITEMS = {
    "Items": [
        {
            "Id": "movie001",
            "Name": "Test Movie 1",
            "Type": "Movie",
            "ProductionYear": 2024,
            "Overview": "A test movie for testing.",
            "OfficialRating": "PG-13",
            "CommunityRating": 7.5,
            "RunTimeTicks": 72000000000,  # 2 hours in ticks
            "Genres": ["Action", "Adventure"],
            "ImageTags": {
                "Primary": "abc123",
                "Backdrop": "def456",
            },
            "MediaSources": [
                {
                    "Id": "source001",
                    "Name": "1080p BluRay",
                    "Path": "/media/movies/test_movie_1.mkv",
                    "Size": 10737418240,
                    "Bitrate": 8000000,
                    "Container": "mkv",
                    "MediaStreams": [
                        {
                            "Type": "Video",
                            "Codec": "h264",
                            "Width": 1920,
                            "Height": 1080,
                        },
                        {
                            "Type": "Audio",
                            "Codec": "aac",
                            "Channels": 2,
                            "Language": "eng",
                        },
                    ],
                }
            ],
            "ProviderIds": {
                "Imdb": "tt1234567",
                "Tmdb": "123456",
            },
        },
        {
            "Id": "movie002",
            "Name": "Test Movie 2",
            "Type": "Movie",
            "ProductionYear": 2023,
            "RunTimeTicks": 54000000000,
        },
    ],
    "TotalRecordCount": 2,
}

JELLYFIN_USER_AUTH = {
    "User": {
        "Id": "user123",
        "Name": "TestUser",
    },
    "AccessToken": "test_access_token_12345",
    "ServerId": "server001",
}

JELLYFIN_SYSTEM_INFO = {
    "ServerName": "Test Jellyfin Server",
    "Version": "10.8.0",
    "Id": "server001",
    "OperatingSystem": "Linux",
    "HasPendingRestart": False,
}
