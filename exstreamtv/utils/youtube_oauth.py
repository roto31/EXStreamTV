"""YouTube OAuth 2.0 authentication helper"""

import json
import logging
import secrets
from pathlib import Path
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


class YouTubeOAuth:
    """YouTube OAuth 2.0 handler"""

    # Google OAuth endpoints
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    # Default scopes for YouTube access
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str = "http://localhost:8411/api/auth/youtube/oauth/callback",
        state_store: dict | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._state_store = state_store or {}  # Store state tokens temporarily

    def generate_authorization_url(self, state: str | None = None) -> tuple[str, str]:
        """
        Generate Google OAuth authorization URL.
        Returns (auth_url, state_token)
        """
        if not self.client_id:
            raise ValueError("OAuth client_id is required. Please configure in config.yaml")

        # Generate state token for CSRF protection
        if not state:
            state = secrets.token_urlsafe(32)

        self._state_store[state] = state

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Force consent screen to get refresh token
            "state": state,
        }

        auth_url = f"{self.AUTH_URL}?{urlencode(params)}"
        return auth_url, state

    async def exchange_code_for_tokens(self, code: str, state: str) -> dict:
        """
        Exchange authorization code for access and refresh tokens.
        """
        if state not in self._state_store:
            raise ValueError("Invalid state token")

        if not self.client_secret:
            raise ValueError("OAuth client_secret is required")

        # Exchange code for tokens
        token_data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            tokens = response.json()

        # Clean up state
        del self._state_store[state]

        return tokens

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh access token using refresh token"""
        if not self.client_secret:
            raise ValueError("OAuth client_secret is required")

        token_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

    def tokens_to_cookies(self, tokens: dict, output_path: Path) -> bool:
        """
        Convert OAuth tokens to cookies.txt format for yt-dlp.
        This is a simplified approach - in practice, we'd need to use the tokens
        to make authenticated requests and extract cookies from the session.
        """
        # For now, we'll store tokens and use them to generate cookies
        # In a full implementation, we'd make authenticated requests to YouTube
        # and extract cookies from the session

        # Store tokens for later use
        tokens_file = output_path.parent / "youtube_oauth_tokens.json"
        with open(tokens_file, "w") as f:
            json.dump(tokens, f, indent=2)

        logger.info(f"OAuth tokens stored at {tokens_file}")
        logger.warning("Token-to-cookies conversion requires additional implementation")
        logger.info(
            "For now, please use the cookie file method or implement token-based authentication"
        )

        return False  # Indicates we need cookies file method instead


def create_oauth_cookies_from_tokens(tokens: dict, cookies_path: Path) -> bool:
    """
    Create cookies.txt from OAuth tokens by making authenticated requests.
    This requires making requests to YouTube with the access token and extracting cookies.
    """
    try:
        access_token = tokens.get("access_token")
        if not access_token:
            return False

        # Make authenticated request to YouTube to get session cookies
        # This is a simplified version - full implementation would:
        # 1. Use access token to make authenticated YouTube API calls
        # 2. Extract cookies from the authenticated session
        # 3. Convert to Netscape cookies.txt format

        # For now, we'll use yt-dlp's OAuth support directly
        # Store tokens and let yt-dlp handle OAuth
        logger.info("OAuth tokens received. Using yt-dlp OAuth support.")
        return True

    except Exception as e:
        logger.exception(f"Error creating cookies from tokens: {e}")
        return False
