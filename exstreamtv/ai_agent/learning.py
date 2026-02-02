"""
Learning capabilities for AI agent - fix effectiveness tracking.

Ported from StreamTV with predictive error prevention.
"""

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exstreamtv.ai_agent.fix_applier import FixResult
    from exstreamtv.ai_agent.fix_suggester import FixSuggestion

logger = logging.getLogger(__name__)


@dataclass
class FixEffectiveness:
    """Track effectiveness of a fix."""

    fix_id: str
    pattern_name: str
    action_type: str
    target: str
    success_count: int = 0
    failure_count: int = 0
    total_applications: int = 0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    average_effectiveness: float = 0.0
    proven_safe: bool = False
    proven_safe_since: datetime | None = None
    validation_period_days: int = 7

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        if self.last_success:
            result["last_success"] = self.last_success.isoformat()
        if self.last_failure:
            result["last_failure"] = self.last_failure.isoformat()
        if self.proven_safe_since:
            result["proven_safe_since"] = self.proven_safe_since.isoformat()
        return result

    def update_effectiveness(self, success: bool) -> None:
        """Update effectiveness metrics."""
        self.total_applications += 1

        if success:
            self.success_count += 1
            self.last_success = datetime.now()
        else:
            self.failure_count += 1
            self.last_failure = datetime.now()

        if self.total_applications > 0:
            self.average_effectiveness = self.success_count / self.total_applications

        self._check_proven_safe()

    def _check_proven_safe(self) -> None:
        """Check if fix is proven safe."""
        if self.proven_safe:
            return

        # Need at least 10 successful applications
        if self.success_count < 10:
            return

        # Need success rate >= 90%
        if self.average_effectiveness < 0.9:
            return

        # Need to have been used successfully for validation period
        if self.last_success:
            days_since_first_success = (datetime.now() - self.last_success).days
            if days_since_first_success >= self.validation_period_days:
                self.proven_safe = True
                self.proven_safe_since = datetime.now()
                logger.info(f"Fix {self.fix_id} is now proven safe")


class FixLearningDatabase:
    """Database for tracking fix effectiveness."""

    def __init__(self, db_path: Path | None = None):
        """
        Initialize learning database.

        Args:
            db_path: Path to JSON database file.
        """
        if db_path is None:
            base_dir = Path(__file__).parent.parent.parent
            db_path = base_dir / "data" / "ai_agent_fixes.json"

        self.db_path = db_path
        self.effectiveness: dict[str, FixEffectiveness] = {}
        self._load()

    def _load(self) -> None:
        """Load effectiveness data from file."""
        if not self.db_path.exists():
            logger.info(f"Learning database not found, creating new: {self.db_path}")
            return

        try:
            with open(self.db_path) as f:
                data = json.load(f)

            for fix_id, fix_data in data.items():
                effectiveness = FixEffectiveness(
                    fix_id=fix_data.get("fix_id", fix_id),
                    pattern_name=fix_data.get("pattern_name", ""),
                    action_type=fix_data.get("action_type", ""),
                    target=fix_data.get("target", ""),
                    success_count=fix_data.get("success_count", 0),
                    failure_count=fix_data.get("failure_count", 0),
                    total_applications=fix_data.get("total_applications", 0),
                    average_effectiveness=fix_data.get("average_effectiveness", 0.0),
                    proven_safe=fix_data.get("proven_safe", False),
                    validation_period_days=fix_data.get("validation_period_days", 7),
                )

                if fix_data.get("last_success"):
                    effectiveness.last_success = datetime.fromisoformat(
                        fix_data["last_success"]
                    )
                if fix_data.get("last_failure"):
                    effectiveness.last_failure = datetime.fromisoformat(
                        fix_data["last_failure"]
                    )
                if fix_data.get("proven_safe_since"):
                    effectiveness.proven_safe_since = datetime.fromisoformat(
                        fix_data["proven_safe_since"]
                    )

                self.effectiveness[fix_id] = effectiveness

            logger.info(f"Loaded {len(self.effectiveness)} fix effectiveness records")

        except Exception as e:
            logger.error(f"Error loading learning database: {e}", exc_info=True)
            self.effectiveness = {}

    def _save(self) -> None:
        """Save effectiveness data to file."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                fix_id: effectiveness.to_dict()
                for fix_id, effectiveness in self.effectiveness.items()
            }

            with open(self.db_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(self.effectiveness)} fix effectiveness records")

        except Exception as e:
            logger.error(f"Error saving learning database: {e}", exc_info=True)

    def record_fix_application(
        self,
        suggestion: "FixSuggestion",
        result: "FixResult",
    ) -> None:
        """
        Record a fix application and its result.

        Args:
            suggestion: The fix suggestion that was applied.
            result: The result of applying the fix.
        """
        if suggestion.log_match is None:
            logger.warning("Cannot record fix without log_match")
            return

        fix_key = (
            f"{suggestion.log_match.pattern.name}_"
            f"{suggestion.action_type}_{suggestion.target}"
        )

        if fix_key not in self.effectiveness:
            self.effectiveness[fix_key] = FixEffectiveness(
                fix_id=fix_key,
                pattern_name=suggestion.log_match.pattern.name,
                action_type=suggestion.action_type,
                target=suggestion.target,
            )

        effectiveness = self.effectiveness[fix_key]
        effectiveness.update_effectiveness(result.success)

        self._save()

    def is_proven_safe(self, suggestion: "FixSuggestion") -> bool:
        """
        Check if a fix is proven safe.

        Args:
            suggestion: The fix suggestion.

        Returns:
            True if proven safe.
        """
        if suggestion.log_match is None:
            return False

        fix_key = (
            f"{suggestion.log_match.pattern.name}_"
            f"{suggestion.action_type}_{suggestion.target}"
        )

        if fix_key in self.effectiveness:
            return self.effectiveness[fix_key].proven_safe

        return False

    def get_effectiveness(self, suggestion: "FixSuggestion") -> float | None:
        """
        Get effectiveness score for a fix.

        Args:
            suggestion: The fix suggestion.

        Returns:
            Effectiveness score (0.0-1.0) or None.
        """
        if suggestion.log_match is None:
            return None

        fix_key = (
            f"{suggestion.log_match.pattern.name}_"
            f"{suggestion.action_type}_{suggestion.target}"
        )

        if fix_key in self.effectiveness:
            return self.effectiveness[fix_key].average_effectiveness

        return None

    def get_proven_safe_fixes(self) -> list[FixEffectiveness]:
        """Get all proven safe fixes."""
        return [eff for eff in self.effectiveness.values() if eff.proven_safe]

    def get_statistics(self) -> dict[str, Any]:
        """Get learning database statistics."""
        total_fixes = len(self.effectiveness)
        proven_safe = sum(1 for eff in self.effectiveness.values() if eff.proven_safe)
        total_applications = sum(
            eff.total_applications for eff in self.effectiveness.values()
        )
        total_successes = sum(
            eff.success_count for eff in self.effectiveness.values()
        )

        return {
            "total_fixes_tracked": total_fixes,
            "proven_safe_fixes": proven_safe,
            "total_applications": total_applications,
            "total_successes": total_successes,
            "overall_success_rate": (
                total_successes / total_applications if total_applications > 0 else 0.0
            ),
        }


class PredictiveErrorPrevention:
    """Predictive error prevention based on patterns."""

    def __init__(self, learning_db: FixLearningDatabase):
        """
        Initialize predictive error prevention.

        Args:
            learning_db: The learning database.
        """
        self.learning_db = learning_db
        self._error_patterns: dict[str, list[str]] = defaultdict(list)

    def record_error_sequence(
        self,
        error_pattern: str,
        previous_errors: list[str],
    ) -> None:
        """
        Record a sequence of errors leading to a pattern.

        Args:
            error_pattern: The final error pattern.
            previous_errors: List of previous error patterns.
        """
        self._error_patterns[error_pattern].extend(previous_errors)

    def predict_likely_errors(self, current_errors: list[str]) -> list[str]:
        """
        Predict likely next errors based on current sequence.

        Args:
            current_errors: Current sequence of errors.

        Returns:
            List of predicted error patterns.
        """
        predictions = []

        for pattern, sequences in self._error_patterns.items():
            for seq in sequences:
                if len(current_errors) <= len(seq):
                    if current_errors == seq[: len(current_errors)]:
                        predictions.append(pattern)

        return predictions

    def suggest_preventive_actions(
        self,
        predicted_errors: list[str],
    ) -> list[dict[str, Any]]:
        """
        Suggest preventive actions for predicted errors.

        Args:
            predicted_errors: List of predicted error patterns.

        Returns:
            List of preventive action suggestions.
        """
        actions = []

        for error_pattern in predicted_errors:
            proven_safe = self.learning_db.get_proven_safe_fixes()
            relevant_fixes = [
                fix for fix in proven_safe if fix.pattern_name == error_pattern
            ]

            for fix in relevant_fixes:
                actions.append({
                    "action_type": fix.action_type,
                    "target": fix.target,
                    "description": f"Preventive action for {error_pattern}",
                    "confidence": fix.average_effectiveness,
                })

        return actions
