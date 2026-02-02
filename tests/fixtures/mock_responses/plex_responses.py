"""
Mock Plex API responses for testing.
"""

PLEX_LIBRARY_SECTIONS = {
    "MediaContainer": {
        "size": 2,
        "Directory": [
            {
                "key": "1",
                "type": "movie",
                "title": "Movies",
                "agent": "tv.plex.agents.movie",
                "scanner": "Plex Movie",
            },
            {
                "key": "2",
                "type": "show",
                "title": "TV Shows",
                "agent": "tv.plex.agents.series",
                "scanner": "Plex TV Series",
            },
        ]
    }
}

PLEX_MOVIES_RESPONSE = {
    "MediaContainer": {
        "size": 3,
        "Metadata": [
            {
                "ratingKey": "12345",
                "key": "/library/metadata/12345",
                "type": "movie",
                "title": "Test Movie 1",
                "year": 2024,
                "duration": 7200000,
                "summary": "A test movie for testing purposes.",
                "contentRating": "PG-13",
                "rating": 7.5,
                "audienceRating": 8.0,
                "thumb": "/library/metadata/12345/thumb/1234567890",
                "art": "/library/metadata/12345/art/1234567890",
                "Media": [
                    {
                        "id": 1001,
                        "duration": 7200000,
                        "bitrate": 8000,
                        "width": 1920,
                        "height": 1080,
                        "videoCodec": "h264",
                        "audioCodec": "aac",
                        "Part": [
                            {
                                "id": 2001,
                                "key": "/library/parts/2001/file.mp4",
                                "duration": 7200000,
                                "file": "/media/movies/test_movie_1.mp4",
                            }
                        ]
                    }
                ],
                "Genre": [
                    {"tag": "Action"},
                    {"tag": "Adventure"},
                ],
            },
            {
                "ratingKey": "12346",
                "key": "/library/metadata/12346",
                "type": "movie",
                "title": "Test Movie 2",
                "year": 2023,
                "duration": 5400000,
                "summary": "Another test movie.",
            },
            {
                "ratingKey": "12347",
                "key": "/library/metadata/12347",
                "type": "movie",
                "title": "Test Movie 3",
                "year": 2022,
                "duration": 6300000,
            },
        ]
    }
}

PLEX_SHOWS_RESPONSE = {
    "MediaContainer": {
        "size": 2,
        "Metadata": [
            {
                "ratingKey": "20001",
                "key": "/library/metadata/20001/children",
                "type": "show",
                "title": "Test Show 1",
                "year": 2020,
                "childCount": 5,
                "summary": "A test TV show.",
                "Genre": [
                    {"tag": "Drama"},
                    {"tag": "Mystery"},
                ],
            },
            {
                "ratingKey": "20002",
                "key": "/library/metadata/20002/children",
                "type": "show",
                "title": "Test Show 2",
                "year": 2021,
                "childCount": 3,
            },
        ]
    }
}

PLEX_METADATA_RESPONSE = {
    "MediaContainer": {
        "size": 1,
        "Metadata": [
            {
                "ratingKey": "12345",
                "key": "/library/metadata/12345",
                "guid": "plex://movie/5d776830880197001ec90540",
                "type": "movie",
                "title": "Test Movie 1",
                "originalTitle": "Test Movie Original",
                "year": 2024,
                "duration": 7200000,
                "summary": "A test movie for testing purposes.",
                "tagline": "The ultimate test movie.",
                "contentRating": "PG-13",
                "rating": 7.5,
                "audienceRating": 8.0,
                "studio": "Test Studios",
                "thumb": "/library/metadata/12345/thumb/1234567890",
                "art": "/library/metadata/12345/art/1234567890",
                "Genre": [
                    {"tag": "Action"},
                    {"tag": "Adventure"},
                ],
                "Director": [
                    {"tag": "Test Director"},
                ],
                "Writer": [
                    {"tag": "Test Writer"},
                ],
                "Role": [
                    {"tag": "Test Actor", "role": "Main Character"},
                ],
                "Guid": [
                    {"id": "imdb://tt1234567"},
                    {"id": "tmdb://123456"},
                ],
            }
        ]
    }
}
