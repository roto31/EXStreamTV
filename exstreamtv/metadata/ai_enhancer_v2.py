"""AI-assisted metadata enhancer v2 - Uses Ollama with MCP integration (TVDB, TMDB) to improve titles, descriptions, and generate XMLTV EPG data"""

import json
import logging
from datetime import datetime
from typing import Any

import httpx

from ..config import config
from .api_key_manager_v2 import APIKeyManagerV2
from .clients.tmdb_client_v2 import TMDBClientV2
from .clients.tvdb_client_v2 import TVDBClientV2

logger = logging.getLogger(__name__)


class AIMetadataEnhancerV2:
    """
    AI-assisted metadata enhancer v2

    Uses Ollama AI models to enhance metadata with MCP integration:
    - TVDB MCP (with API keys) for TV show metadata
    - TMDB MCP (with API keys) for movie/TV metadata
    - Archive.org MCP for additional context
    - YouTube MCP for related data
    """

    def __init__(
        self,
        api_key_manager: APIKeyManagerV2 | None = None,
        ollama_url: str | None = None,
        ollama_model: str | None = None,
        enabled: bool = True,
    ):
        """
        Initialize AI metadata enhancer

        Args:
            api_key_manager: API key manager instance
            ollama_url: Ollama API URL (defaults to config)
            ollama_model: Ollama model name (defaults to config)
            enabled: Whether AI enhancement is enabled
        """
        self.api_key_manager = api_key_manager or APIKeyManagerV2()
        self.ollama_url = ollama_url or config.auto_healer.ollama_url
        self.ollama_model = ollama_model or config.auto_healer.ollama_model
        self.enabled = enabled and config.metadata.enabled

        # Initialize metadata clients (for MCP integration)
        self.tvdb_client = None
        self.tmdb_client = None

        if self.enabled:
            if config.metadata.enable_tvdb:
                try:
                    self.tvdb_client = TVDBClientV2(self.api_key_manager)
                except Exception as e:
                    logger.warning(f"Failed to initialize TVDB client: {e}")

            if config.metadata.enable_tmdb:
                try:
                    self.tmdb_client = TMDBClientV2(self.api_key_manager)
                except Exception as e:
                    logger.warning(f"Failed to initialize TMDB client: {e}")

        self._http_client = httpx.AsyncClient(timeout=60.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._http_client.aclose()

    async def _call_ollama(self, prompt: str, system_prompt: str | None = None) -> str | None:
        """
        Call Ollama API with prompt

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            AI response text or None if error
        """
        if not self.enabled:
            return None

        try:
            url = f"{self.ollama_url}/api/generate"
            data = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",  # Request JSON response for structured data
            }

            if system_prompt:
                data["system"] = system_prompt

            response = await self._http_client.post(url, json=data)
            response.raise_for_status()

            result = response.json()
            return result.get("response", "")

        except Exception as e:
            logger.exception(f"Ollama API call failed: {e}")
            return None

    async def _query_mcp_sources(self, title: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        Query MCP sources (TVDB, TMDB) for additional metadata context

        Args:
            title: Media title
            metadata: Existing metadata

        Returns:
            Dict with MCP-sourced metadata
        """
        mcp_metadata = {
            "tvdb": None,
            "tmdb": None,
        }

        # Query TVDB if available
        if self.tvdb_client and config.metadata.enable_tvdb:
            try:
                # Search TVDB for series
                tvdb_results = await self.tvdb_client.search(title, type="series")
                if tvdb_results:
                    # Get first result details
                    series_id = tvdb_results[0].get("tvdb_id")
                    if series_id:
                        series_info = await self.tvdb_client.get_series(series_id)
                        if series_info:
                            mcp_metadata["tvdb"] = {
                                "series_id": series_id,
                                "name": series_info.get("name"),
                                "overview": series_info.get("overview"),
                                "first_air_time": series_info.get("first_air_time"),
                                "network": series_info.get("network"),
                            }
            except Exception as e:
                logger.debug(f"TVDB MCP query failed: {e}")

        # Query TMDB if available
        if self.tmdb_client and config.metadata.enable_tmdb:
            try:
                # Try TV show search first
                tmdb_results = await self.tmdb_client.search_tv(title)
                if tmdb_results:
                    tmdb_info = tmdb_results[0]
                    mcp_metadata["tmdb"] = {
                        "id": tmdb_info.get("id"),
                        "name": tmdb_info.get("name"),
                        "overview": tmdb_info.get("overview"),
                        "first_air_date": tmdb_info.get("first_air_date"),
                        "network": tmdb_info.get("networks", [{}])[0].get("name")
                        if tmdb_info.get("networks")
                        else None,
                    }
                else:
                    # Try movie search
                    movie_results = await self.tmdb_client.search_movie(title)
                    if movie_results:
                        movie_info = movie_results[0]
                        mcp_metadata["tmdb"] = {
                            "id": movie_info.get("id"),
                            "title": movie_info.get("title"),
                            "overview": movie_info.get("overview"),
                            "release_date": movie_info.get("release_date"),
                        }
            except Exception as e:
                logger.debug(f"TMDB MCP query failed: {e}")

        return mcp_metadata

    async def enhance_title(
        self, raw_title: str, metadata: dict[str, Any], source: str = "unknown"
    ) -> str:
        """
        Enhance title using AI with MCP context

        Args:
            raw_title: Raw title from source
            metadata: Existing metadata
            source: Source type ("archive_org", "youtube", "plex")

        Returns:
            Enhanced title
        """
        if not self.enabled:
            return raw_title

        # Query MCP sources for context
        mcp_context = await self._query_mcp_sources(raw_title, metadata)

        # Build prompt
        system_prompt = """You are a metadata enhancement assistant. Your task is to improve media titles for EPG (Electronic Program Guide) display.

Rules:
- Keep titles concise and clear (max 60 characters)
- Remove file extensions, URLs, and technical identifiers
- Standardize naming conventions
- Preserve important information (date, episode numbers, etc.)
- Return only the enhanced title, no explanation"""

        prompt = f"""Enhance this media title for EPG display:

Raw Title: {raw_title}
Source: {source}
Description: {metadata.get("description", "")[:200]}

Additional Context from Metadata Sources:
- TVDB: {json.dumps(mcp_context.get("tvdb", {}), indent=2) if mcp_context.get("tvdb") else "None"}
- TMDB: {json.dumps(mcp_context.get("tmdb", {}), indent=2) if mcp_context.get("tmdb") else "None"}

Return a JSON object with the enhanced title:
{{"enhanced_title": "..."}}"""

        try:
            response = await self._call_ollama(prompt, system_prompt)
            if response:
                # Parse JSON response
                try:
                    result = json.loads(response)
                    enhanced_title = result.get("enhanced_title", raw_title)
                    if enhanced_title and len(enhanced_title) > 0:
                        return enhanced_title
                except json.JSONDecodeError:
                    # Fallback: try to extract title from text response
                    if "enhanced_title" in response:
                        import re

                        match = re.search(r'"enhanced_title":\s*"([^"]+)"', response)
                        if match:
                            return match.group(1)
        except Exception as e:
            logger.debug(f"AI title enhancement failed: {e}")

        return raw_title

    async def enhance_description(
        self, raw_description: str, metadata: dict[str, Any], source: str = "unknown"
    ) -> str:
        """
        Enhance description using AI with MCP context

        Args:
            raw_description: Raw description from source
            metadata: Existing metadata
            source: Source type

        Returns:
            Enhanced description
        """
        if not self.enabled:
            return raw_description

        # Query MCP sources for context
        mcp_context = await self._query_mcp_sources(metadata.get("title", ""), metadata)

        # Build prompt
        system_prompt = """You are a metadata enhancement assistant. Your task is to create concise, informative descriptions for EPG (Electronic Program Guide) display.

Rules:
- Keep descriptions under 200 characters
- Extract key information (date, event, participants)
- Format for TV guide display
- Remove HTML tags and formatting
- Return only the enhanced description, no explanation"""

        prompt = f"""Enhance this media description for EPG display:

Raw Description: {raw_description[:500]}
Source: {source}
Title: {metadata.get("title", "")}
Date: {metadata.get("date", "")}
Creator: {metadata.get("creator", "") or metadata.get("uploader", "")}

Additional Context from Metadata Sources:
- TVDB: {json.dumps(mcp_context.get("tvdb", {}), indent=2) if mcp_context.get("tvdb") else "None"}
- TMDB: {json.dumps(mcp_context.get("tmdb", {}), indent=2) if mcp_context.get("tmdb") else "None"}

Return a JSON object with the enhanced description:
{{"enhanced_description": "..."}}"""

        try:
            response = await self._call_ollama(prompt, system_prompt)
            if response:
                try:
                    result = json.loads(response)
                    enhanced_desc = result.get("enhanced_description", raw_description)
                    if enhanced_desc:
                        return enhanced_desc
                except json.JSONDecodeError:
                    if "enhanced_description" in response:
                        import re

                        match = re.search(r'"enhanced_description":\s*"([^"]+)"', response)
                        if match:
                            return match.group(1)
        except Exception as e:
            logger.debug(f"AI description enhancement failed: {e}")

        return raw_description

    async def generate_epg_data(
        self, metadata: dict[str, Any], start_time: datetime, duration: int | None = None
    ) -> dict[str, Any]:
        """
        Generate XMLTV EPG data using AI with MCP context

        Args:
            metadata: Media metadata
            start_time: Program start time
            duration: Program duration in seconds

        Returns:
            EPG data dict with XMLTV structure
        """
        if not self.enabled:
            return self._generate_epg_data_fallback(metadata, start_time, duration)

        # Query MCP sources for context
        mcp_context = await self._query_mcp_sources(metadata.get("title", ""), metadata)

        # Build prompt
        system_prompt = """You are an EPG (Electronic Program Guide) data generator. Your task is to generate proper XMLTV EPG data from media metadata.

Rules:
- Generate proper XMLTV structure
- Include all required fields
- Use proper language attributes
- Extract categories from tags/subjects
- Generate episode numbers if applicable
- Return valid JSON matching XMLTV structure"""

        prompt = f"""Generate XMLTV EPG data for this media:

Title: {metadata.get("title", "")}
Description: {metadata.get("description", "")[:500]}
Date: {metadata.get("date", "")}
Creator: {metadata.get("creator", "") or metadata.get("uploader", "")}
Duration: {duration or metadata.get("duration", 0)} seconds
Tags: {metadata.get("subject", []) or metadata.get("tags", [])}

Additional Context from Metadata Sources:
- TVDB: {json.dumps(mcp_context.get("tvdb", {}), indent=2) if mcp_context.get("tvdb") else "None"}
- TMDB: {json.dumps(mcp_context.get("tmdb", {}), indent=2) if mcp_context.get("tmdb") else "None"}

Return a JSON object with XMLTV EPG structure:
{{
  "title": {{"value": "...", "lang": "en"}},
  "desc": {{"value": "...", "lang": "en"}},
  "date": "YYYYMMDD",
  "category": ["..."],
  "episode-num": {{"system": "...", "value": "..."}},
  "icon": {{"src": "..."}}
}}"""

        try:
            response = await self._call_ollama(prompt, system_prompt)
            if response:
                try:
                    result = json.loads(response)
                    # Validate and return EPG data
                    epg_data = {
                        "title": result.get(
                            "title", {"value": metadata.get("title", ""), "lang": "en"}
                        ),
                        "desc": result.get(
                            "desc", {"value": metadata.get("description", ""), "lang": "en"}
                        ),
                        "date": result.get("date", metadata.get("date", "")),
                        "category": result.get(
                            "category", metadata.get("subject", []) or metadata.get("tags", [])
                        ),
                        "episode-num": result.get("episode-num"),
                        "icon": result.get("icon", {"src": metadata.get("thumbnail", "")}),
                    }
                    return epg_data
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug(f"AI EPG generation failed: {e}")

        # Fallback to rule-based generation
        return self._generate_epg_data_fallback(metadata, start_time, duration)

    def _generate_epg_data_fallback(
        self, metadata: dict[str, Any], start_time: datetime, duration: int | None = None
    ) -> dict[str, Any]:
        """Fallback EPG data generation (rule-based)"""
        # Extract date
        date_str = metadata.get("date", "")
        if date_str:
            try:
                from dateutil import parser

                date_obj = parser.parse(date_str)
                date_str = date_obj.strftime("%Y%m%d")
            except Exception:
                date_str = start_time.strftime("%Y%m%d")
        else:
            date_str = start_time.strftime("%Y%m%d")

        # Extract categories
        categories = []
        if metadata.get("subject"):
            categories = metadata.get("subject", [])[:3]  # Limit to 3 categories
        elif metadata.get("tags"):
            categories = metadata.get("tags", [])[:3]

        return {
            "title": {"value": metadata.get("title", ""), "lang": "en"},
            "desc": {
                "value": metadata.get("description", "")[:500],  # Limit description length
                "lang": "en",
            },
            "date": date_str,
            "category": categories,
            "episode-num": None,  # Can be extracted from title if pattern matches
            "icon": {"src": metadata.get("thumbnail", "")},
        }

    async def enhance_metadata(
        self, metadata: dict[str, Any], source: str = "unknown"
    ) -> dict[str, Any]:
        """
        Enhance complete metadata using AI with MCP integration

        Args:
            metadata: Raw metadata dict
            source: Source type

        Returns:
            Enhanced metadata dict
        """
        if not self.enabled:
            return metadata

        enhanced = metadata.copy()

        # Enhance title
        if metadata.get("title"):
            enhanced["ai_enhanced_title"] = await self.enhance_title(
                metadata.get("title", ""), metadata, source
            )

        # Enhance description
        if metadata.get("description"):
            enhanced["ai_enhanced_description"] = await self.enhance_description(
                metadata.get("description", ""), metadata, source
            )

        # Generate EPG data
        enhanced["epg_data"] = await self.generate_epg_data(
            metadata, datetime.utcnow(), metadata.get("duration") or metadata.get("runtime")
        )

        enhanced["ai_enhanced_at"] = datetime.utcnow()
        enhanced["ai_model_used"] = self.ollama_model

        return enhanced
