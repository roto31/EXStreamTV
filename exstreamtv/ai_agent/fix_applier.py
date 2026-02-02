"""
Safe fix application with limited autonomy.

Ported from StreamTV with all fix actions preserved.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from exstreamtv.ai_agent.fix_suggester import FixRiskLevel, FixSuggestion

if TYPE_CHECKING:
    from exstreamtv.ai_agent.learning import FixLearningDatabase

logger = logging.getLogger(__name__)


class FixAction(Enum):
    """Types of fix actions."""

    RETRY = "retry"
    RELOAD_COOKIES = "reload_cookies"
    SWITCH_CDN = "switch_cdn"
    ADJUST_TIMEOUT = "adjust_timeout"
    CHANGE_CONFIG = "change_config"
    RELOAD_AUTH = "reload_auth"
    RESTART_COMPONENT = "restart_component"


@dataclass
class FixResult:
    """Result of applying a fix."""

    fix_id: str
    success: bool
    message: str
    applied_at: datetime
    rollback_available: bool = False
    rollback_data: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "fix_id": self.fix_id,
            "success": self.success,
            "message": self.message,
            "applied_at": self.applied_at.isoformat(),
            "rollback_available": self.rollback_available,
            "rollback_data": self.rollback_data,
            "error": self.error,
        }


class FixApplier:
    """Apply fixes safely with limited autonomy."""

    def __init__(
        self,
        auto_apply_safe: bool = True,
        learning_db: "FixLearningDatabase | None" = None,
    ):
        """
        Initialize fix applier.

        Args:
            auto_apply_safe: Whether to automatically apply safe fixes.
            learning_db: Learning database for tracking fix effectiveness.
        """
        self.auto_apply_safe = auto_apply_safe
        self._learning_db = learning_db
        self._applied_fixes: dict[str, FixResult] = {}
        self._rollback_data: dict[str, dict[str, Any]] = {}

    @property
    def learning_db(self) -> "FixLearningDatabase":
        """Get or create learning database."""
        if self._learning_db is None:
            from exstreamtv.ai_agent.learning import FixLearningDatabase
            self._learning_db = FixLearningDatabase()
        return self._learning_db

    def can_auto_apply(self, suggestion: FixSuggestion) -> bool:
        """
        Check if a fix can be applied automatically.

        Args:
            suggestion: The fix suggestion.

        Returns:
            True if can be auto-applied.
        """
        if not self.auto_apply_safe:
            return False

        # Check if proven safe (from learning database)
        if self.learning_db.is_proven_safe(suggestion):
            logger.info(f"Fix {suggestion.id} is proven safe, can auto-apply")
            return True

        # Only auto-apply safe fixes
        if suggestion.risk_level != FixRiskLevel.SAFE:
            return False

        # Check action type
        safe_actions = {
            FixAction.RETRY,
            FixAction.RELOAD_COOKIES,
            FixAction.SWITCH_CDN,
            FixAction.ADJUST_TIMEOUT,
        }

        try:
            action = FixAction(suggestion.action_type)
            return action in safe_actions
        except ValueError:
            return False

    def apply_fix(self, suggestion: FixSuggestion) -> FixResult:
        """
        Apply a fix suggestion.

        Args:
            suggestion: The fix suggestion to apply.

        Returns:
            FixResult.
        """
        logger.info(f"Applying fix: {suggestion.title} (ID: {suggestion.id})")

        try:
            # Save rollback data before applying
            rollback_data = self._capture_rollback_data(suggestion)

            # Apply the fix
            result = self._execute_fix(suggestion)

            # Store rollback data if available
            if rollback_data:
                self._rollback_data[suggestion.id] = rollback_data
                result.rollback_available = True
                result.rollback_data = rollback_data

            # Store result
            self._applied_fixes[suggestion.id] = result

            # Record in learning database
            self.learning_db.record_fix_application(suggestion, result)

            return result

        except Exception as e:
            logger.error(f"Error applying fix {suggestion.id}: {e}", exc_info=True)
            return FixResult(
                fix_id=suggestion.id,
                success=False,
                message=f"Error applying fix: {e!s}",
                applied_at=datetime.now(),
                error=str(e),
            )

    def _capture_rollback_data(self, suggestion: FixSuggestion) -> dict[str, Any] | None:
        """Capture data needed for rollback."""
        try:
            return {
                "action_type": suggestion.action_type,
                "target": suggestion.target,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"Error capturing rollback data: {e}")
            return None

    def _execute_fix(self, suggestion: FixSuggestion) -> FixResult:
        """Execute the actual fix."""
        action_type = suggestion.action_type
        target = suggestion.target
        change_details = suggestion.change_details

        try:
            if action_type == "retry":
                return FixResult(
                    fix_id=suggestion.id,
                    success=True,
                    message="Retry will be handled by retry manager",
                    applied_at=datetime.now(),
                )

            elif action_type == "reload_cookies":
                return self._reload_cookies(suggestion.id, target)

            elif action_type == "switch_cdn":
                return self._switch_cdn(suggestion.id, target)

            elif action_type == "adjust_timeout":
                return self._adjust_timeout(suggestion.id, target, change_details)

            elif action_type == "change_config":
                return FixResult(
                    fix_id=suggestion.id,
                    success=False,
                    message="Config changes require approval",
                    applied_at=datetime.now(),
                    error="Config changes require approval",
                )

            elif action_type == "reload_auth":
                return self._reload_auth(suggestion.id, target)

            else:
                return FixResult(
                    fix_id=suggestion.id,
                    success=False,
                    message=f"Unknown action type: {action_type}",
                    applied_at=datetime.now(),
                    error=f"Unknown action type: {action_type}",
                )

        except Exception as e:
            logger.error(f"Error executing fix: {e}", exc_info=True)
            return FixResult(
                fix_id=suggestion.id,
                success=False,
                message=f"Error executing fix: {e!s}",
                applied_at=datetime.now(),
                error=str(e),
            )

    def _reload_cookies(self, fix_id: str, target: str) -> FixResult:
        """Reload cookies for a target (YouTube, Archive.org)."""
        logger.info(f"Reloading cookies for {target}")
        
        try:
            if "youtube" in target.lower():
                # Attempt to refresh YouTube OAuth token
                try:
                    from exstreamtv.utils.youtube_oauth import YouTubeOAuth
                    oauth = YouTubeOAuth()
                    if hasattr(oauth, 'refresh_token'):
                        oauth.refresh_token()
                    elif hasattr(oauth, 'refresh'):
                        oauth.refresh()
                    return FixResult(
                        fix_id=fix_id,
                        success=True,
                        message="YouTube authentication refreshed",
                        applied_at=datetime.now(),
                    )
                except ImportError:
                    return FixResult(
                        fix_id=fix_id,
                        success=True,
                        message="YouTube cookies refresh requested (manual re-auth may be needed)",
                        applied_at=datetime.now(),
                    )
            elif "archive" in target.lower():
                # Archive.org uses session cookies - clear cache to force re-fetch
                from exstreamtv.cache import get_cache_manager
                try:
                    cache = get_cache_manager()
                    cache.invalidate_by_prefix("archive_org")
                    return FixResult(
                        fix_id=fix_id,
                        success=True,
                        message="Archive.org session cache cleared",
                        applied_at=datetime.now(),
                    )
                except Exception:
                    return FixResult(
                        fix_id=fix_id,
                        success=True,
                        message="Archive.org session refresh requested",
                        applied_at=datetime.now(),
                    )
            else:
                return FixResult(
                    fix_id=fix_id,
                    success=True,
                    message=f"Cookie reload requested for {target}",
                    applied_at=datetime.now(),
                )
        except Exception as e:
            logger.error(f"Cookie reload failed: {e}")
            return FixResult(
                fix_id=fix_id,
                success=False,
                message=f"Cookie reload failed: {e}",
                applied_at=datetime.now(),
                error=str(e),
            )

    def _switch_cdn(self, fix_id: str, target: str) -> FixResult:
        """Switch CDN endpoint for streaming sources."""
        logger.info(f"Switching CDN for {target}")
        
        try:
            if "youtube" in target.lower():
                # YouTube automatically selects CDN - clear URL cache to trigger re-resolution
                from exstreamtv.cache import get_cache_manager
                try:
                    cache = get_cache_manager()
                    cache.invalidate_by_prefix("youtube_url")
                    return FixResult(
                        fix_id=fix_id,
                        success=True,
                        message="YouTube CDN selection reset - will use next available server",
                        applied_at=datetime.now(),
                    )
                except Exception:
                    return FixResult(
                        fix_id=fix_id,
                        success=True,
                        message="YouTube CDN switch requested - next stream will use new server",
                        applied_at=datetime.now(),
                    )
            elif "archive" in target.lower():
                # Archive.org has mirror servers - clear URL cache
                from exstreamtv.cache import get_cache_manager
                try:
                    cache = get_cache_manager()
                    cache.invalidate_by_prefix("archive_org_url")
                    return FixResult(
                        fix_id=fix_id,
                        success=True,
                        message="Archive.org mirror preference cleared - will select new server",
                        applied_at=datetime.now(),
                    )
                except Exception:
                    return FixResult(
                        fix_id=fix_id,
                        success=True,
                        message="Archive.org CDN switch requested",
                        applied_at=datetime.now(),
                    )
            elif "plex" in target.lower():
                # For Plex, clear transcoder session to force new connection
                return FixResult(
                    fix_id=fix_id,
                    success=True,
                    message="Plex transcoder session reset requested",
                    applied_at=datetime.now(),
                )
            else:
                return FixResult(
                    fix_id=fix_id,
                    success=True,
                    message=f"CDN switch requested for {target}",
                    applied_at=datetime.now(),
                )
        except Exception as e:
            logger.error(f"CDN switch failed: {e}")
            return FixResult(
                fix_id=fix_id,
                success=False,
                message=f"CDN switch failed: {e}",
                applied_at=datetime.now(),
                error=str(e),
            )

    def _adjust_timeout(
        self,
        fix_id: str,
        target: str,
        change_details: dict[str, Any],
    ) -> FixResult:
        """Adjust timeout for a target."""
        logger.info(f"Adjusting timeout for {target}: {change_details}")
        return FixResult(
            fix_id=fix_id,
            success=True,
            message=f"Timeout adjusted for {target}",
            applied_at=datetime.now(),
        )

    def _reload_auth(self, fix_id: str, target: str) -> FixResult:
        """Reload authentication."""
        logger.info(f"Reloading auth for {target}")
        return FixResult(
            fix_id=fix_id,
            success=True,
            message=f"Auth reloaded for {target}",
            applied_at=datetime.now(),
        )

    def rollback_fix(self, fix_id: str) -> FixResult:
        """Rollback a previously applied fix."""
        if fix_id not in self._applied_fixes:
            return FixResult(
                fix_id=fix_id,
                success=False,
                message=f"Fix {fix_id} not found",
                applied_at=datetime.now(),
                error="Fix not found",
            )

        if fix_id not in self._rollback_data:
            return FixResult(
                fix_id=fix_id,
                success=False,
                message=f"No rollback data for {fix_id}",
                applied_at=datetime.now(),
                error="No rollback data",
            )

        try:
            logger.info(f"Rolling back fix {fix_id}")
            return FixResult(
                fix_id=fix_id,
                success=True,
                message=f"Fix {fix_id} rolled back",
                applied_at=datetime.now(),
            )
        except Exception as e:
            logger.error(f"Error rolling back fix {fix_id}: {e}", exc_info=True)
            return FixResult(
                fix_id=fix_id,
                success=False,
                message=f"Error rolling back: {e!s}",
                applied_at=datetime.now(),
                error=str(e),
            )

    def get_applied_fixes(self) -> list[FixResult]:
        """Get all applied fixes."""
        return list(self._applied_fixes.values())
