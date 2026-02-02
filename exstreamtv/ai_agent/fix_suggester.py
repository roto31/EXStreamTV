"""
Fix suggestion engine using Ollama AI with rule-based fallback.

Ported from StreamTV with all fix strategies preserved.
"""

import contextlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from exstreamtv.ai_agent.log_analyzer import LogMatch

logger = logging.getLogger(__name__)


class FixRiskLevel(Enum):
    """Risk level for a fix."""

    SAFE = "safe"  # Can be applied automatically
    LOW = "low"  # Low risk, may require approval
    MEDIUM = "medium"  # Medium risk, requires approval
    HIGH = "high"  # High risk, requires explicit approval
    CRITICAL = "critical"  # Critical risk, manual intervention required


@dataclass
class FixSuggestion:
    """A suggested fix for an error."""

    id: str
    title: str
    description: str
    risk_level: FixRiskLevel
    action_type: str  # e.g., "retry", "reload_cookies", "switch_cdn"
    target: str  # What this fix targets
    change_details: dict[str, Any]
    estimated_effectiveness: float  # 0.0-1.0
    log_match: LogMatch | None = None
    created_at: datetime | None = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result["risk_level"] = self.risk_level.value
        result["created_at"] = self.created_at.isoformat() if self.created_at else None
        if self.log_match:
            result["log_match"] = {
                "pattern": self.log_match.pattern.name,
                "category": self.log_match.pattern.category,
                "message": self.log_match.message[:200],
            }
        return result


class FixSuggester:
    """Suggest fixes for errors using Ollama AI with rule-based fallback."""

    def __init__(
        self,
        ollama_model: str = "mistral:7b",
        ollama_base_url: str = "http://localhost:11434",
    ):
        """
        Initialize fix suggester.

        Args:
            ollama_model: Ollama model to use.
            ollama_base_url: Ollama API base URL.
        """
        self.ollama_model = ollama_model
        self.ollama_base_url = ollama_base_url
        self._suggestions_cache: dict[str, list[FixSuggestion]] = {}

    def _check_ollama_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            import httpx

            response = httpx.get(f"{self.ollama_base_url}/api/tags", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False

    def _call_ollama(self, prompt: str) -> str | None:
        """Call Ollama API."""
        try:
            import httpx

            response = httpx.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                    },
                },
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("response", "").strip()
            else:
                logger.warning(f"Ollama API returned status {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error calling Ollama: {e}", exc_info=True)
            return None

    def suggest_fixes(self, log_match: LogMatch) -> list[FixSuggestion]:
        """
        Suggest fixes for a log match.

        Args:
            log_match: The log match to suggest fixes for.

        Returns:
            List of fix suggestions.
        """
        # Check cache
        cache_key = f"{log_match.pattern.name}_{log_match.pattern.category}"
        if cache_key in self._suggestions_cache:
            suggestions = []
            for cached in self._suggestions_cache[cache_key]:
                new_suggestion = FixSuggestion(
                    id=cached.id,
                    title=cached.title,
                    description=cached.description,
                    risk_level=cached.risk_level,
                    action_type=cached.action_type,
                    target=cached.target,
                    change_details=cached.change_details,
                    estimated_effectiveness=cached.estimated_effectiveness,
                    log_match=log_match,
                )
                suggestions.append(new_suggestion)
            return suggestions

        # Check if Ollama is available
        if not self._check_ollama_available():
            logger.debug("Ollama not available, using rule-based suggestions")
            return self._suggest_rule_based_fixes(log_match)

        # Build prompt for Ollama
        prompt = self._build_fix_prompt(log_match)

        # Call Ollama
        ai_response = self._call_ollama(prompt)

        if not ai_response:
            logger.warning("Ollama returned no response, using rule-based suggestions")
            return self._suggest_rule_based_fixes(log_match)

        # Extract structured fixes
        suggestions = self._extract_structured_fixes(ai_response, log_match)

        # Cache suggestions
        if suggestions:
            self._suggestions_cache[cache_key] = suggestions

        return suggestions

    def _build_fix_prompt(self, log_match: LogMatch) -> str:
        """Build prompt for Ollama."""
        pattern = log_match.pattern
        context = log_match.context

        return f"""You are a troubleshooting assistant for EXStreamTV, a media streaming platform.

Error Details:
- Pattern: {pattern.name}
- Category: {pattern.category}
- Severity: {pattern.severity.value}
- Description: {pattern.description}
- Error Message: {log_match.message}
- Context: {json.dumps(context, indent=2)}

EXStreamTV Architecture:
- Uses FFmpeg for transcoding streams to MPEG-TS
- Supports YouTube (via yt-dlp), Archive.org, Plex, Jellyfin, Emby as sources
- Has error handling with retry logic and fallback mechanisms
- Uses cookies for authentication (YouTube, Archive.org)
- Has CDN management for Archive.org with automatic failover

Please suggest fixes for this error. Return your response as JSON:

{{
  "fixes": [
    {{
      "title": "Short descriptive title",
      "description": "Detailed description of the fix",
      "risk_level": "safe|low|medium|high|critical",
      "action_type": "retry|reload_cookies|switch_cdn|adjust_timeout|change_config|reload_auth",
      "target": "component name",
      "change_details": {{}},
      "estimated_effectiveness": 0.0-1.0
    }}
  ]
}}

Guidelines:
- "safe" fixes can be applied automatically
- "low" to "high" risk fixes require approval
- "critical" fixes require manual intervention
- Focus on actionable fixes

Return only the JSON, no additional text."""

    def _extract_structured_fixes(
        self,
        ai_response: str,
        log_match: LogMatch,
    ) -> list[FixSuggestion]:
        """Extract structured fix suggestions from AI response."""
        suggestions = []

        try:
            if "{" in ai_response:
                start = ai_response.find("{")
                end = ai_response.rfind("}") + 1
                if end > start:
                    json_str = ai_response[start:end]
                    with contextlib.suppress(json.JSONDecodeError):
                        json_match = json.loads(json_str)
                        fixes = json_match.get("fixes", [])
                        for i, fix_data in enumerate(fixes):
                            if isinstance(fix_data, dict):
                                suggestion = self._parse_fix_data(fix_data, log_match, i)
                                if suggestion:
                                    suggestions.append(suggestion)
        except Exception as e:
            logger.warning(f"Error parsing structured fixes: {e}")

        if not suggestions:
            suggestions = self._extract_fixes_from_text(ai_response, log_match)

        return suggestions

    def _parse_fix_data(
        self,
        fix_data: dict[str, Any],
        log_match: LogMatch,
        index: int,
    ) -> FixSuggestion | None:
        """Parse a fix data dictionary into a FixSuggestion."""
        try:
            risk_str = fix_data.get("risk_level", "medium").lower()
            risk_level = FixRiskLevel.MEDIUM
            for risk in FixRiskLevel:
                if risk.value == risk_str:
                    risk_level = risk
                    break

            return FixSuggestion(
                id=f"fix_{log_match.pattern.name}_{index}_{datetime.now().timestamp()}",
                title=fix_data.get("title", f"Fix for {log_match.pattern.name}"),
                description=fix_data.get("description", ""),
                risk_level=risk_level,
                action_type=fix_data.get("action_type", "unknown"),
                target=fix_data.get("target", log_match.pattern.category),
                change_details=fix_data.get("change_details", {}),
                estimated_effectiveness=float(fix_data.get("estimated_effectiveness", 0.5)),
                log_match=log_match,
            )
        except Exception as e:
            logger.warning(f"Error parsing fix data: {e}")
            return None

    def _extract_fixes_from_text(
        self,
        text: str,
        log_match: LogMatch,
    ) -> list[FixSuggestion]:
        """Extract fix suggestions from plain text response."""
        suggestions = []
        lines = text.split("\n")
        current_fix = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if re.match(r"^(\d+\.|[-*]|Fix:)\s+", line, re.IGNORECASE):
                if current_fix:
                    suggestions.append(current_fix)

                title = re.sub(r"^(\d+\.|[-*]|Fix:)\s+", "", line, flags=re.IGNORECASE)
                current_fix = FixSuggestion(
                    id=f"fix_{log_match.pattern.name}_{len(suggestions)}_{datetime.now().timestamp()}",
                    title=title,
                    description="",
                    risk_level=FixRiskLevel.MEDIUM,
                    action_type="unknown",
                    target=log_match.pattern.category,
                    change_details={},
                    estimated_effectiveness=0.5,
                    log_match=log_match,
                )
            elif current_fix:
                if current_fix.description:
                    current_fix.description += " " + line
                else:
                    current_fix.description = line

        if current_fix:
            suggestions.append(current_fix)

        return suggestions

    def _suggest_rule_based_fixes(self, log_match: LogMatch) -> list[FixSuggestion]:
        """Suggest fixes based on rules (fallback when Ollama unavailable)."""
        suggestions = []
        pattern = log_match.pattern
        context = log_match.context

        if pattern.name == "ffmpeg_http_error":
            status_code = context.get("status_code")
            if status_code == 500:
                suggestions.append(
                    FixSuggestion(
                        id=f"fix_ffmpeg_500_{datetime.now().timestamp()}",
                        title="Retry FFmpeg stream without custom headers",
                        description="CDN sometimes rejects custom headers. Retry without cookies/Referer.",
                        risk_level=FixRiskLevel.SAFE,
                        action_type="retry",
                        target="ffmpeg",
                        change_details={"skip_headers": True},
                        estimated_effectiveness=0.7,
                        log_match=log_match,
                    )
                )
            elif status_code in [401, 403]:
                suggestions.append(
                    FixSuggestion(
                        id=f"fix_ffmpeg_auth_{datetime.now().timestamp()}",
                        title="Reload authentication cookies",
                        description="Reload cookies for the source and retry.",
                        risk_level=FixRiskLevel.SAFE,
                        action_type="reload_cookies",
                        target=pattern.category,
                        change_details={},
                        estimated_effectiveness=0.8,
                        log_match=log_match,
                    )
                )

        elif pattern.name == "youtube_rate_limit":
            suggestions.append(
                FixSuggestion(
                    id=f"fix_youtube_rate_limit_{datetime.now().timestamp()}",
                    title="Increase request delay",
                    description="Increase delay between YouTube API requests.",
                    risk_level=FixRiskLevel.SAFE,
                    action_type="adjust_timeout",
                    target="youtube",
                    change_details={"request_delay": 30.0},
                    estimated_effectiveness=0.9,
                    log_match=log_match,
                )
            )

        elif pattern.name == "youtube_auth_error":
            suggestions.append(
                FixSuggestion(
                    id=f"fix_youtube_auth_{datetime.now().timestamp()}",
                    title="Reload YouTube cookies",
                    description="Reload YouTube authentication cookies and retry.",
                    risk_level=FixRiskLevel.SAFE,
                    action_type="reload_cookies",
                    target="youtube",
                    change_details={},
                    estimated_effectiveness=0.8,
                    log_match=log_match,
                )
            )

        elif pattern.name == "archive_org_500":
            suggestions.append(
                FixSuggestion(
                    id=f"fix_archive_500_{datetime.now().timestamp()}",
                    title="Switch Archive.org CDN server",
                    description="Switch to a different CDN server.",
                    risk_level=FixRiskLevel.SAFE,
                    action_type="switch_cdn",
                    target="archive_org",
                    change_details={},
                    estimated_effectiveness=0.7,
                    log_match=log_match,
                )
            )

        elif pattern.name == "cannot_tune_channel":
            suggestions.append(
                FixSuggestion(
                    id=f"fix_tune_channel_{datetime.now().timestamp()}",
                    title="Check stream startup and validation",
                    description="Verify stream is starting correctly.",
                    risk_level=FixRiskLevel.MEDIUM,
                    action_type="retry",
                    target="streaming",
                    change_details={},
                    estimated_effectiveness=0.6,
                    log_match=log_match,
                )
            )

        elif pattern.name == "cookie_error":
            suggestions.append(
                FixSuggestion(
                    id=f"fix_cookie_{datetime.now().timestamp()}",
                    title="Reload cookies",
                    description="Reload authentication cookies for the affected source.",
                    risk_level=FixRiskLevel.SAFE,
                    action_type="reload_cookies",
                    target=pattern.category,
                    change_details={},
                    estimated_effectiveness=0.8,
                    log_match=log_match,
                )
            )

        # Default suggestion
        if not suggestions:
            suggestions.append(
                FixSuggestion(
                    id=f"fix_generic_{datetime.now().timestamp()}",
                    title="Retry operation",
                    description="Retry the failed operation with exponential backoff.",
                    risk_level=FixRiskLevel.SAFE,
                    action_type="retry",
                    target=pattern.category,
                    change_details={},
                    estimated_effectiveness=0.5,
                    log_match=log_match,
                )
            )

        return suggestions
