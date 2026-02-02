"""
Mock TMDB API responses for testing.
"""

TMDB_MOVIE_SEARCH = {
    "page": 1,
    "results": [
        {
            "id": 123456,
            "title": "Test Movie",
            "original_title": "Test Movie Original",
            "overview": "A test movie for testing metadata lookup.",
            "release_date": "2024-01-15",
            "vote_average": 7.5,
            "vote_count": 1234,
            "popularity": 45.67,
            "poster_path": "/poster123.jpg",
            "backdrop_path": "/backdrop123.jpg",
            "genre_ids": [28, 12, 878],
            "adult": False,
        },
        {
            "id": 123457,
            "title": "Test Movie 2",
            "original_title": "Test Movie 2",
            "overview": "Another test movie.",
            "release_date": "2023-06-20",
            "vote_average": 6.8,
            "vote_count": 567,
            "poster_path": "/poster456.jpg",
        },
    ],
    "total_pages": 1,
    "total_results": 2,
}

TMDB_TV_SEARCH = {
    "page": 1,
    "results": [
        {
            "id": 78901,
            "name": "Test Show",
            "original_name": "Test Show Original",
            "overview": "A test TV show for testing metadata lookup.",
            "first_air_date": "2020-03-15",
            "vote_average": 8.2,
            "vote_count": 2345,
            "popularity": 78.90,
            "poster_path": "/tvposter123.jpg",
            "backdrop_path": "/tvbackdrop123.jpg",
            "genre_ids": [18, 9648],
        },
    ],
    "total_pages": 1,
    "total_results": 1,
}

TMDB_MOVIE_DETAILS = {
    "id": 123456,
    "title": "Test Movie",
    "original_title": "Test Movie Original",
    "tagline": "The ultimate test movie.",
    "overview": "A test movie for testing metadata lookup. This is a longer description.",
    "release_date": "2024-01-15",
    "runtime": 120,
    "status": "Released",
    "vote_average": 7.5,
    "vote_count": 1234,
    "popularity": 45.67,
    "budget": 50000000,
    "revenue": 150000000,
    "poster_path": "/poster123.jpg",
    "backdrop_path": "/backdrop123.jpg",
    "imdb_id": "tt1234567",
    "genres": [
        {"id": 28, "name": "Action"},
        {"id": 12, "name": "Adventure"},
        {"id": 878, "name": "Science Fiction"},
    ],
    "production_companies": [
        {"id": 1, "name": "Test Studios", "logo_path": "/logo1.png"},
    ],
    "production_countries": [
        {"iso_3166_1": "US", "name": "United States of America"},
    ],
    "spoken_languages": [
        {"iso_639_1": "en", "name": "English"},
    ],
    "credits": {
        "cast": [
            {
                "id": 1001,
                "name": "Test Actor",
                "character": "Main Character",
                "order": 0,
                "profile_path": "/actor1.jpg",
            },
            {
                "id": 1002,
                "name": "Test Actress",
                "character": "Supporting Character",
                "order": 1,
                "profile_path": "/actress1.jpg",
            },
        ],
        "crew": [
            {
                "id": 2001,
                "name": "Test Director",
                "job": "Director",
                "department": "Directing",
            },
            {
                "id": 2002,
                "name": "Test Writer",
                "job": "Writer",
                "department": "Writing",
            },
        ],
    },
    "videos": {
        "results": [
            {
                "id": "vid001",
                "key": "abc123xyz",
                "name": "Official Trailer",
                "type": "Trailer",
                "site": "YouTube",
            },
        ],
    },
    "external_ids": {
        "imdb_id": "tt1234567",
        "facebook_id": None,
        "instagram_id": None,
        "twitter_id": None,
    },
}

TMDB_TV_DETAILS = {
    "id": 78901,
    "name": "Test Show",
    "original_name": "Test Show Original",
    "overview": "A test TV show for testing metadata lookup.",
    "first_air_date": "2020-03-15",
    "last_air_date": "2024-01-10",
    "status": "Returning Series",
    "vote_average": 8.2,
    "vote_count": 2345,
    "number_of_seasons": 4,
    "number_of_episodes": 48,
    "episode_run_time": [45],
    "poster_path": "/tvposter123.jpg",
    "backdrop_path": "/tvbackdrop123.jpg",
    "genres": [
        {"id": 18, "name": "Drama"},
        {"id": 9648, "name": "Mystery"},
    ],
    "created_by": [
        {"id": 3001, "name": "Test Creator"},
    ],
    "networks": [
        {"id": 101, "name": "Test Network"},
    ],
    "seasons": [
        {
            "id": 101,
            "season_number": 1,
            "name": "Season 1",
            "episode_count": 12,
            "air_date": "2020-03-15",
        },
        {
            "id": 102,
            "season_number": 2,
            "name": "Season 2",
            "episode_count": 12,
            "air_date": "2021-03-15",
        },
    ],
    "external_ids": {
        "imdb_id": "tt7654321",
        "tvdb_id": 654321,
    },
}

TMDB_CONFIGURATION = {
    "images": {
        "base_url": "http://image.tmdb.org/t/p/",
        "secure_base_url": "https://image.tmdb.org/t/p/",
        "poster_sizes": ["w92", "w154", "w185", "w342", "w500", "w780", "original"],
        "backdrop_sizes": ["w300", "w780", "w1280", "original"],
        "profile_sizes": ["w45", "w185", "h632", "original"],
    },
}
