"""
Unified Troubleshooting Service for EXStreamTV

Integrates all AI troubleshooting components:
- PersonaManager (System Admin persona)
- UnifiedAIProvider (cloud/local AI)
- LogAnalyzer (multi-source log parsing)
- FixSuggester (AI-powered fix suggestions)
- ApprovalManager (risky fix approval workflow)
- FixApplier (safe fix application)
- FixLearningDatabase (effectiveness tracking)
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from exstreamtv.ai_agent.fix_applier import FixApplier, FixResult
from exstreamtv.ai_agent.fix_suggester import FixSuggester, FixSuggestion
from exstreamtv.ai_agent.approval_manager import ApprovalManager, ApprovalRequest
from exstreamtv.ai_agent.learning import FixLearningDatabase
from exstreamtv.ai_agent.log_analyzer import LogAnalyzer, LogMatch
from exstreamtv.ai_agent.persona_manager import PersonaManager, PersonaType, get_persona_manager
from exstreamtv.ai_agent.prompts.system_admin import (
    build_troubleshooting_prompt,
    get_sysadmin_welcome_message,
)
from exstreamtv.config import EXStreamTVConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class TroubleshootingResult:
    """Result of troubleshooting analysis."""

    success: bool
    query: str
    response: str
    log_matches: dict[str, list[dict[str, Any]]]
    fix_suggestions: list[dict[str, Any]]
    persona_used: str
    model_used: str
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "query": self.query,
            "response": self.response,
            "log_matches": self.log_matches,
            "fix_suggestions": self.fix_suggestions,
            "persona_used": self.persona_used,
            "model_used": self.model_used,
            "timestamp": self.timestamp.isoformat(),
        }


class TroubleshootingService:
    """
    Unified troubleshooting service integrating:
    - PersonaManager (System Admin persona)
    - LogAnalyzer (multi-source log parsing)
    - FixSuggester (AI-powered fix suggestions)
    - ApprovalManager (risky fix approval workflow)
    - FixApplier (safe fix application)
    - FixLearningDatabase (effectiveness tracking)
    """

    def __init__(self, config: EXStreamTVConfig | None = None):
        """
        Initialize the troubleshooting service.

        Args:
            config: EXStreamTV configuration
        """
        self.config = config or get_config()
        self._persona_manager = get_persona_manager()
        self._log_analyzer = LogAnalyzer()
        self._learning_db = FixLearningDatabase()
        self._fix_suggester = FixSuggester(
            ollama_model=self.config.auto_healer.ollama_model,
            ollama_base_url=self.config.auto_healer.ollama_url,
        )
        self._approval_manager = ApprovalManager(learning_db=self._learning_db)
        self._fix_applier = FixApplier(
            auto_apply_safe=self.config.auto_healer.auto_fix,
            learning_db=self._learning_db,
        )
        self._conversation_history: list[dict[str, str]] = []

        logger.info("TroubleshootingService initialized")

    @property
    def persona_manager(self) -> PersonaManager:
        """Get the persona manager."""
        return self._persona_manager

    @property
    def log_analyzer(self) -> LogAnalyzer:
        """Get the log analyzer."""
        return self._log_analyzer

    @property
    def learning_db(self) -> FixLearningDatabase:
        """Get the learning database."""
        return self._learning_db

    def get_welcome_message(self) -> str:
        """Get the System Admin persona welcome message."""
        return get_sysadmin_welcome_message()

    async def analyze_and_suggest(
        self,
        query: str,
        include_app_logs: bool = True,
        include_plex_logs: bool = True,
        include_browser_logs: bool = True,
        include_ollama_logs: bool = True,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> TroubleshootingResult:
        """
        Run full troubleshooting analysis.

        Args:
            query: User's troubleshooting query
            include_app_logs: Include EXStreamTV application logs
            include_plex_logs: Include Plex Media Server logs
            include_browser_logs: Include browser console logs
            include_ollama_logs: Include Ollama AI logs
            conversation_history: Previous conversation messages

        Returns:
            TroubleshootingResult with analysis and suggestions
        """
        # Get log context
        log_matches = self._log_analyzer.get_context_for_troubleshooting(
            include_app=include_app_logs,
            include_plex=include_plex_logs,
            include_browser=include_browser_logs,
            include_ollama=include_ollama_logs,
        )

        # Convert log matches to dict format for prompt
        log_context: dict[str, list[dict]] = {}
        for source, matches in log_matches.items():
            log_context[source] = [
                {
                    "message": m.message,
                    "severity": m.pattern.severity.value,
                    "category": m.pattern.category,
                    "pattern": m.pattern.name,
                }
                for m in matches
            ]

        # Build prompt using System Admin persona
        history = conversation_history or self._conversation_history
        prompt = build_troubleshooting_prompt(
            user_message=query,
            conversation_history=history,
            log_context=log_context,
        )

        # Try to get AI response
        response = ""
        model_used = "none"
        fix_suggestions: list[dict[str, Any]] = []

        try:
            response, model_used = await self._get_ai_response(prompt)

            # Extract fix suggestions from response
            fix_suggestions = self._extract_fixes_from_response(response, log_matches)

        except Exception as e:
            logger.error(f"Error getting AI response: {e}")
            response = self._generate_fallback_response(query, log_context)
            model_used = "fallback"

        # Update conversation history
        self._conversation_history.append({"role": "user", "content": query})
        self._conversation_history.append({"role": "assistant", "content": response})

        # Keep only last 20 messages
        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:]

        return TroubleshootingResult(
            success=True,
            query=query,
            response=response,
            log_matches=log_context,
            fix_suggestions=fix_suggestions,
            persona_used="system_admin",
            model_used=model_used,
            timestamp=datetime.now(),
        )

    async def _get_ai_response(self, prompt: str) -> tuple[str, str]:
        """
        Get AI response using available providers.

        Args:
            prompt: The prompt to send

        Returns:
            Tuple of (response_text, model_name)
        """
        import httpx
        import os

        # Try Ollama first (local)
        ollama_url = os.getenv("OLLAMA_URL") or self.config.auto_healer.ollama_url

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": self.config.auto_healer.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.9,
                        },
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", ""), self.config.auto_healer.ollama_model

        except Exception as e:
            logger.warning(f"Ollama unavailable: {e}")

        # Fall back to cloud AI if configured
        try:
            from exstreamtv.ai_agent.provider_manager import get_ai_provider

            provider = get_ai_provider()
            if provider:
                result = await provider.generate(prompt)
                return result.get("response", ""), result.get("model", "cloud")
        except Exception as e:
            logger.warning(f"Cloud AI unavailable: {e}")

        raise RuntimeError("No AI providers available")

    def _extract_fixes_from_response(
        self,
        response: str,
        log_matches: dict[str, list[LogMatch]],
    ) -> list[dict[str, Any]]:
        """Extract fix suggestions from AI response."""
        import json
        import re

        fixes = []

        # Try to find JSON in response
        json_match = re.search(r'\{[^{}]*"fixes"[^{}]*\[.*?\].*?\}', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                if isinstance(data, dict) and "fixes" in data:
                    for fix in data["fixes"]:
                        if isinstance(fix, dict):
                            fixes.append({
                                "title": fix.get("title", "Suggested Fix"),
                                "description": fix.get("description", ""),
                                "action": fix.get("action", "unknown"),
                                "risk_level": fix.get("risk_level", "medium"),
                                "steps": fix.get("steps", []),
                            })
            except json.JSONDecodeError:
                pass

        # If no JSON fixes found, generate from log matches
        if not fixes:
            for source, matches in log_matches.items():
                for match in matches[:3]:  # Top 3 per source
                    suggestions = self._fix_suggester.suggest_fixes(match)
                    for suggestion in suggestions:
                        fixes.append(suggestion.to_dict())

        return fixes

    def _generate_fallback_response(
        self,
        query: str,
        log_context: dict[str, list[dict]],
    ) -> str:
        """Generate fallback response when AI is unavailable."""
        lines = ["I'm currently unable to connect to the AI service, but I can share what I found in the logs:\n"]

        has_issues = False
        for source, errors in log_context.items():
            if errors:
                has_issues = True
                lines.append(f"\n**{source.upper()} Issues ({len(errors)}):**")
                for error in errors[:5]:
                    lines.append(f"- [{error.get('severity', 'ERROR')}] {error.get('message', '')[:100]}")

        if not has_issues:
            lines.append("\nNo critical issues found in the logs. The system appears to be running normally.")
            lines.append("\nIf you're experiencing specific issues, please describe them in more detail.")
        else:
            lines.append("\n\n**Recommended Actions:**")
            lines.append("1. Check the specific error messages above")
            lines.append("2. Review recent changes to your configuration")
            lines.append("3. Try restarting the affected service")
            lines.append("4. Once AI service is available, ask for detailed analysis")

        return "\n".join(lines)

    async def apply_fix(self, fix_id: str) -> FixResult:
        """
        Apply a suggested fix with approval workflow.

        Args:
            fix_id: ID of the fix to apply

        Returns:
            FixResult with outcome
        """
        # This would need to look up the fix from stored suggestions
        # For now, return a placeholder
        return FixResult(
            fix_id=fix_id,
            success=False,
            message="Fix application requires stored fix context",
            applied_at=datetime.now(),
            error="Not implemented - use direct fix application",
        )

    def get_pending_approvals(self) -> list[ApprovalRequest]:
        """Get pending fix approval requests."""
        return self._approval_manager.get_pending_requests()

    def approve_fix(self, request_id: str, approved_by: str | None = None) -> bool:
        """Approve a fix request."""
        return self._approval_manager.approve(request_id, approved_by)

    def reject_fix(self, request_id: str, reason: str | None = None) -> bool:
        """Reject a fix request."""
        return self._approval_manager.reject(request_id, reason)

    def get_fix_history(self) -> list[FixResult]:
        """Get history of applied fixes."""
        return self._fix_applier.get_applied_fixes()

    def clear_conversation(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()


# Singleton instance
_troubleshooting_service: TroubleshootingService | None = None


def get_troubleshooting_service() -> TroubleshootingService:
    """Get the global TroubleshootingService instance."""
    global _troubleshooting_service
    if _troubleshooting_service is None:
        _troubleshooting_service = TroubleshootingService()
    return _troubleshooting_service
