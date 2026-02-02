"""Auto-healing system coordinator - monitors, analyzes, and fixes errors automatically"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .error_fixer import ErrorFixer
from .error_monitor import ErrorMonitor
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class AutoHealer:
    """Coordinates error monitoring, AI analysis, and automatic fixing"""

    def __init__(
        self,
        workspace_root: Path,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.2:latest",
        dry_run: bool = True,
        enable_ai: bool = True,
    ):
        """
        Initialize auto-healer

        Args:
            workspace_root: Root directory of the workspace
            ollama_url: Ollama API URL
            ollama_model: Ollama model to use
            dry_run: If True, only simulate fixes
            enable_ai: If True, use AI for analysis and suggestions
        """
        self.workspace_root = Path(workspace_root)
        self.dry_run = dry_run
        self.enable_ai = enable_ai

        # Initialize components
        self.monitor = ErrorMonitor()
        self.fixer = ErrorFixer(workspace_root, dry_run=dry_run)
        self.ollama = OllamaClient(base_url=ollama_url, model=ollama_model) if enable_ai else None

        # Stats
        self.run_count = 0
        self.total_errors_detected = 0
        self.total_fixes_applied = 0
        self.last_run_time = None

        logger.info(f"Initialized AutoHealer (dry_run={dry_run}, enable_ai={enable_ai})")

    async def __aenter__(self):
        """Async context manager entry"""
        if self.ollama:
            await self.ollama.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.ollama:
            await self.ollama.__aexit__(exc_type, exc_val, exc_tb)

    async def run_health_check(self) -> dict[str, Any]:
        """
        Run a full health check cycle

        Returns:
            Dict with health check results
        """
        self.run_count += 1
        self.last_run_time = datetime.now()

        result = {
            "run_number": self.run_count,
            "timestamp": self.last_run_time.isoformat(),
            "dry_run": self.dry_run,
            "ai_enabled": self.enable_ai,
            "errors_detected": [],
            "fixes_applied": [],
            "ai_analyses": [],
            "summary": {},
        }

        try:
            logger.info("=" * 70)
            logger.info(f"AUTO-HEALER: Starting health check #{self.run_count}")
            logger.info("=" * 70)

            # Step 1: Check Ollama availability
            if self.enable_ai and self.ollama:
                ollama_available = await self.ollama.is_available()
                result["ollama_available"] = ollama_available

                if not ollama_available:
                    logger.warning("Ollama not available - continuing without AI analysis")
                    self.enable_ai = False
                else:
                    models = await self.ollama.list_models()
                    logger.info(f"Ollama available with models: {models}")

            # Step 2: Scan logs for errors
            logger.info("Scanning recent logs for errors...")
            detected_errors, log_lines = await self.monitor.scan_recent_logs(
                minutes=60, max_lines=1000
            )

            result["errors_detected"] = detected_errors
            self.total_errors_detected += len(detected_errors)

            if not detected_errors:
                logger.info("✅ No errors detected - system healthy!")
                result["summary"]["status"] = "healthy"
                return result

            logger.warning(f"⚠️  Detected {len(detected_errors)} error(s)")

            # Step 3: Group and prioritize errors
            grouped_errors = self.monitor.group_errors_by_category(detected_errors)
            high_priority = self.monitor.get_high_priority_errors(detected_errors)

            result["grouped_errors"] = grouped_errors
            result["high_priority_errors"] = high_priority

            logger.info("Error breakdown by category:")
            for category, errors in grouped_errors.items():
                logger.info(f"  - {category}: {len(errors)} error(s)")

            # Step 4: Analyze with AI (if enabled and available)
            if self.enable_ai and self.ollama:
                logger.info("Analyzing errors with AI...")

                for error in high_priority[:5]:  # Analyze top 5 high-priority errors
                    analysis = await self._analyze_error_with_ai(error, log_lines)
                    result["ai_analyses"].append(analysis)

            # Step 5: Apply fixes
            logger.info("Attempting to apply fixes...")

            # Process unique error patterns
            unique_patterns = {error["pattern_name"] for error in detected_errors}

            for pattern_name in unique_patterns:
                pattern_errors = [e for e in detected_errors if e["pattern_name"] == pattern_name]
                count = len(pattern_errors)

                logger.info(f"Processing {count} instance(s) of '{pattern_name}'")

                # Get AI suggestion if available
                ai_suggestion = None
                if self.enable_ai and pattern_errors:
                    matching_analysis = next(
                        (
                            a
                            for a in result.get("ai_analyses", [])
                            if a.get("error_pattern") == pattern_name
                        ),
                        None,
                    )
                    if matching_analysis:
                        ai_suggestion = matching_analysis.get("fix_suggestion")

                # Apply fix
                fix_result = await self.fixer.apply_fix(pattern_name, ai_suggestion)
                result["fixes_applied"].append(fix_result)

                if fix_result["success"]:
                    fixes_count = len(fix_result.get("fixes_applied", []))
                    self.total_fixes_applied += fixes_count
                    logger.info(f"✅ Applied {fixes_count} fix(es) for '{pattern_name}'")
                else:
                    logger.warning(f"❌ No fix applied for '{pattern_name}'")

            # Step 6: Generate summary
            result["summary"] = self._generate_summary(result)

            logger.info("=" * 70)
            logger.info(f"AUTO-HEALER: Health check #{self.run_count} complete")
            logger.info(f"  Status: {result['summary']['status']}")
            logger.info(f"  Errors detected: {len(detected_errors)}")
            logger.info(f"  Fixes applied: {result['summary']['fixes_applied']}")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Error during health check: {e}", exc_info=True)
            result["error"] = str(e)
            result["summary"]["status"] = "error"

        return result

    async def _analyze_error_with_ai(
        self, error: dict[str, Any], log_lines: list[str]
    ) -> dict[str, Any]:
        """Analyze a single error with AI"""
        analysis_result = {
            "error_pattern": error["pattern_name"],
            "error_line": error["line"],
            "ai_analysis": None,
            "fix_suggestion": None,
        }

        try:
            # Extract context
            context = {
                "pattern": error["pattern_name"],
                "category": error["category"],
                "severity": error["severity"],
                "description": error["description"],
            }

            # Analyze error
            ai_analysis = await self.ollama.analyze_error(
                error_message=error["line"], context=context, log_excerpt=error.get("context", "")
            )

            analysis_result["ai_analysis"] = ai_analysis

            # Get fix suggestion if confidence is high enough
            if ai_analysis.get("confidence", 0) > 0.6:
                fix_suggestion = await self.ollama.suggest_fix(
                    error_type=error["category"],
                    error_details=error["line"],
                    current_config=None,  # Could load relevant config here
                    code_context=error.get("context", ""),
                )

                analysis_result["fix_suggestion"] = fix_suggestion

        except Exception as e:
            logger.exception(f"Error during AI analysis: {e}")
            analysis_result["error"] = str(e)

        return analysis_result

    def _generate_summary(self, result: dict[str, Any]) -> dict[str, Any]:
        """Generate summary of health check results"""
        errors_count = len(result.get("errors_detected", []))
        fixes_applied = sum(
            len(fix.get("fixes_applied", []))
            for fix in result.get("fixes_applied", [])
            if fix.get("success")
        )

        # Determine status
        high_priority_count = len(result.get("high_priority_errors", []))

        if errors_count == 0:
            status = "healthy"
        elif high_priority_count > 0 and fixes_applied == 0:
            status = "critical"
        elif fixes_applied > 0:
            status = "healing"
        else:
            status = "degraded"

        return {
            "status": status,
            "errors_detected": errors_count,
            "high_priority": high_priority_count,
            "fixes_applied": fixes_applied,
            "categories": list(result.get("grouped_errors", {}).keys()),
            "ai_analyses_performed": len(result.get("ai_analyses", [])),
            "recommendations": self._generate_recommendations(result),
        }

    def _generate_recommendations(self, result: dict[str, Any]) -> list[str]:
        """Generate actionable recommendations"""
        recommendations = []

        errors_count = len(result.get("errors_detected", []))
        high_priority_count = len(result.get("high_priority_errors", []))
        fixes_applied = len([f for f in result.get("fixes_applied", []) if f.get("success")])

        if high_priority_count > 5:
            recommendations.append(
                f"⚠️  {high_priority_count} high-priority errors detected - immediate attention recommended"
            )

        if errors_count > 0 and fixes_applied == 0:
            recommendations.append(
                "💡 No automatic fixes available - manual intervention may be required"
            )

        if self.dry_run and fixes_applied > 0:
            recommendations.append(
                "🔧 Fixes available but not applied (dry-run mode) - run with --apply to apply fixes"
            )

        # Check for specific patterns
        grouped = result.get("grouped_errors", {})

        if "timeout" in grouped and len(grouped["timeout"]) > 3:
            recommendations.append(
                "⏱️  Multiple timeout errors - consider increasing timeout values or checking network connectivity"
            )

        if "ffmpeg" in grouped and len(grouped["ffmpeg"]) > 3:
            recommendations.append(
                "🎬 Multiple FFmpeg errors - check video file formats and codec compatibility"
            )

        if "connection" in grouped and len(grouped["connection"]) > 3:
            recommendations.append(
                "🌐 Multiple connection errors - check external service availability (Archive.org, Plex, etc.)"
            )

        if not recommendations:
            recommendations.append("✅ System appears stable")

        return recommendations

    async def run_continuous_monitoring(
        self, interval_minutes: int = 30, max_iterations: int | None = None
    ):
        """
        Run continuous monitoring and healing

        Args:
            interval_minutes: Time between health checks
            max_iterations: Maximum number of iterations (None for infinite)
        """
        iteration = 0

        logger.info(f"Starting continuous monitoring (interval={interval_minutes}min)")

        try:
            while True:
                iteration += 1

                if max_iterations and iteration > max_iterations:
                    logger.info(f"Reached max iterations ({max_iterations}), stopping")
                    break

                # Run health check
                await self.run_health_check()

                # Wait for next iteration
                if max_iterations is None or iteration < max_iterations:
                    logger.info(f"Next health check in {interval_minutes} minutes...")
                    await asyncio.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            logger.info("Continuous monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error in continuous monitoring: {e}", exc_info=True)

    def get_stats(self) -> dict[str, Any]:
        """Get auto-healer statistics"""
        return {
            "run_count": self.run_count,
            "total_errors_detected": self.total_errors_detected,
            "total_fixes_applied": self.total_fixes_applied,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "dry_run": self.dry_run,
            "ai_enabled": self.enable_ai,
        }
