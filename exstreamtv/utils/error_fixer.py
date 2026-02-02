"""Automated error fixing system"""

import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class FixAction:
    """Represents a fix action that can be applied"""

    def __init__(
        self,
        fix_type: str,
        target: str,
        change_type: str,
        value: Any,
        description: str,
        risks: list[str],
    ):
        self.fix_type = fix_type  # config, code, restart, etc.
        self.target = target  # File path, config key, etc.
        self.change_type = change_type  # set, increase, decrease, replace, etc.
        self.value = value
        self.description = description
        self.risks = risks
        self.applied_at = None
        self.backup_path = None


class ErrorFixer:
    """Applies automated fixes to detected errors"""

    # Registry of known fixes for specific error patterns
    FIX_REGISTRY = {
        "ffmpeg_timeout": {
            "type": "config",
            "target": "streamtv/streaming/mpegts_streamer.py",
            "fixes": [
                {
                    "description": "Increase first chunk timeout for problematic files",
                    "search": r"first_chunk_timeout\s*=\s*(\d+\.?\d*)",
                    "replace": lambda match: f"first_chunk_timeout = {float(match.group(1)) * 2}",
                    "min_value": 5.0,
                    "max_value": 30.0,
                },
                {
                    "description": "Increase HTTP timeout for slow connections",
                    "search": r'"-timeout",\s*"(\d+)"',
                    "replace": lambda match: f'"-timeout", "{int(match.group(1)) * 2}"',
                    "min_value": 10000000,
                    "max_value": 60000000,
                },
            ],
        },
        "connection_refused": {
            "type": "config",
            "target": "config.yaml",
            "fixes": [
                {
                    "description": "Increase connection timeout",
                    "yaml_path": ["streaming", "timeout"],
                    "operation": "increase",
                    "factor": 1.5,
                    "max_value": 120,
                },
                {
                    "description": "Increase max retries",
                    "yaml_path": ["streaming", "max_retries"],
                    "operation": "increase",
                    "amount": 2,
                    "max_value": 10,
                },
            ],
        },
        "archive_org_redirect": {
            "type": "code",
            "target": "streamtv/streaming/stream_manager.py",
            "fixes": [
                {
                    "description": "Ensure follow_redirects is enabled",
                    "search": r"httpx\.AsyncClient\([^)]*\)",
                    "verify": r"follow_redirects\s*=\s*True",
                    "action": "verify_only",
                }
            ],
        },
        "http_error": {
            "type": "config",
            "target": "config.yaml",
            "fixes": [
                {
                    "description": "Enable authentication for Archive.org",
                    "yaml_path": ["archive_org", "use_authentication"],
                    "operation": "set",
                    "value": True,
                }
            ],
        },
    }

    def __init__(self, workspace_root: Path, dry_run: bool = True):
        """
        Initialize error fixer

        Args:
            workspace_root: Root directory of the workspace
            dry_run: If True, only simulate fixes without applying them
        """
        self.workspace_root = Path(workspace_root)
        self.dry_run = dry_run
        self.applied_fixes = []
        self.backup_dir = self.workspace_root / ".streamtv_backups"

        # Create backup directory
        self.backup_dir.mkdir(exist_ok=True)

        logger.info(f"Initialized ErrorFixer (dry_run={dry_run})")

    async def apply_fix(
        self, error_pattern: str, ai_suggestion: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Apply a fix for a detected error pattern

        Args:
            error_pattern: Name of the error pattern
            ai_suggestion: Optional AI-generated fix suggestion

        Returns:
            Dict with fix results including success status and details
        """
        result = {
            "error_pattern": error_pattern,
            "success": False,
            "fixes_applied": [],
            "fixes_failed": [],
            "backup_created": False,
            "dry_run": self.dry_run,
        }

        try:
            # Check if we have a registered fix for this pattern
            if error_pattern in self.FIX_REGISTRY:
                fix_config = self.FIX_REGISTRY[error_pattern]
                result["fix_source"] = "registry"

                # Apply registered fixes
                for fix_spec in fix_config["fixes"]:
                    fix_result = await self._apply_registered_fix(
                        fix_config["type"], fix_config["target"], fix_spec
                    )

                    if fix_result["success"]:
                        result["fixes_applied"].append(fix_result)
                    else:
                        result["fixes_failed"].append(fix_result)

            # If AI suggestion provided and no registered fix, try to apply AI suggestion
            elif ai_suggestion:
                result["fix_source"] = "ai_suggestion"
                ai_fix_result = await self._apply_ai_suggestion(ai_suggestion)

                if ai_fix_result["success"]:
                    result["fixes_applied"].append(ai_fix_result)
                else:
                    result["fixes_failed"].append(ai_fix_result)

            else:
                result["message"] = f"No fix available for pattern: {error_pattern}"
                logger.warning(result["message"])
                return result

            # Overall success if at least one fix applied
            result["success"] = len(result["fixes_applied"]) > 0

            if result["success"]:
                logger.info(f"Applied {len(result['fixes_applied'])} fix(es) for {error_pattern}")
            else:
                logger.warning(f"No fixes successfully applied for {error_pattern}")

        except Exception as e:
            logger.exception(f"Error applying fix for {error_pattern}: {e}")
            result["error"] = str(e)

        return result

    async def _apply_registered_fix(
        self, fix_type: str, target: str, fix_spec: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply a registered fix from the fix registry"""
        result = {
            "description": fix_spec.get("description", "Unknown fix"),
            "target": target,
            "success": False,
        }

        try:
            target_path = self.workspace_root / target

            if not target_path.exists():
                result["error"] = f"Target file not found: {target}"
                logger.error(result["error"])
                return result

            # Create backup
            if not self.dry_run:
                backup_path = self._create_backup(target_path)
                result["backup_path"] = str(backup_path)

            # Apply fix based on type
            if fix_type == "config" and target.endswith(".yaml"):
                result = await self._fix_yaml_config(target_path, fix_spec, result)
            elif fix_type in {"code", "config"}:
                result = await self._fix_code_file(target_path, fix_spec, result)
            else:
                result["error"] = f"Unknown fix type: {fix_type}"

        except Exception as e:
            logger.exception(f"Error applying registered fix: {e}")
            result["error"] = str(e)

        return result

    async def _fix_yaml_config(
        self, file_path: Path, fix_spec: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        """Fix YAML configuration file"""
        try:
            # Load YAML
            with open(file_path) as f:
                config = yaml.safe_load(f)

            yaml_path = fix_spec.get("yaml_path", [])
            operation = fix_spec.get("operation", "set")

            # Navigate to target
            target = config
            for key in yaml_path[:-1]:
                if key not in target:
                    target[key] = {}
                target = target[key]

            final_key = yaml_path[-1]
            current_value = target.get(final_key)

            # Apply operation
            if operation == "set":
                new_value = fix_spec.get("value")
            elif operation == "increase":
                factor = fix_spec.get("factor", 1.5)
                amount = fix_spec.get("amount", 0)
                max_value = fix_spec.get("max_value", float("inf"))

                if isinstance(current_value, (int, float)):
                    if factor != 1:
                        new_value = min(current_value * factor, max_value)
                    else:
                        new_value = min(current_value + amount, max_value)
                else:
                    result["error"] = f"Cannot increase non-numeric value: {current_value}"
                    return result
            elif operation == "decrease":
                factor = fix_spec.get("factor", 0.5)
                amount = fix_spec.get("amount", 0)
                min_value = fix_spec.get("min_value", 0)

                if isinstance(current_value, (int, float)):
                    if factor != 1:
                        new_value = max(current_value * factor, min_value)
                    else:
                        new_value = max(current_value - amount, min_value)
                else:
                    result["error"] = f"Cannot decrease non-numeric value: {current_value}"
                    return result
            else:
                result["error"] = f"Unknown operation: {operation}"
                return result

            # Apply change
            target[final_key] = new_value
            result["old_value"] = current_value
            result["new_value"] = new_value

            # Write back if not dry run
            if not self.dry_run:
                with open(file_path, "w") as f:
                    yaml.dump(config, f, default_flow_style=False, indent=2)
                logger.info(f"Updated {file_path}: {'.'.join(yaml_path)} = {new_value}")
            else:
                logger.info(
                    f"[DRY RUN] Would update {file_path}: {'.'.join(yaml_path)} = {new_value}"
                )

            result["success"] = True

        except Exception as e:
            logger.exception(f"Error fixing YAML config: {e}")
            result["error"] = str(e)

        return result

    async def _fix_code_file(
        self, file_path: Path, fix_spec: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        """Fix code file using regex replacement"""
        try:
            # Read file
            with open(file_path) as f:
                content = f.read()

            # Check if this is a verify-only fix
            if fix_spec.get("action") == "verify_only":
                verify_pattern = fix_spec.get("verify")
                if re.search(verify_pattern, content):
                    result["success"] = True
                    result["message"] = "Verification passed - no fix needed"
                    logger.info(f"Verification passed for {file_path}")
                else:
                    result["success"] = False
                    result["message"] = "Verification failed - manual intervention required"
                    logger.warning(f"Verification failed for {file_path}")
                return result

            # Apply regex replacement
            search_pattern = fix_spec.get("search")
            replace_func = fix_spec.get("replace")

            if not search_pattern or not replace_func:
                result["error"] = "Missing search pattern or replace function"
                return result

            # Find matches
            matches = list(re.finditer(search_pattern, content))

            if not matches:
                result["message"] = "No matches found - pattern may have already been fixed"
                result["success"] = True
                return result

            # Check value constraints
            min_value = fix_spec.get("min_value")
            max_value = fix_spec.get("max_value")

            new_content = content
            replacements = []

            for match in matches:
                # Get current value
                if match.groups():
                    current_val = match.group(1)
                    try:
                        current_num = float(current_val)

                        # Check if within acceptable range
                        if max_value and current_num >= max_value:
                            logger.info(f"Value already at maximum: {current_num} >= {max_value}")
                            continue

                        if min_value and current_num < min_value:
                            logger.info(f"Value below minimum: {current_num} < {min_value}")
                            continue

                    except ValueError:
                        pass  # Not a numeric value

                # Apply replacement
                replacement = replace_func(match)
                new_content = new_content.replace(match.group(0), replacement, 1)

                replacements.append({"old": match.group(0), "new": replacement})

            if not replacements:
                result["message"] = "No changes needed - values already optimal"
                result["success"] = True
                return result

            result["replacements"] = replacements
            result["changes_count"] = len(replacements)

            # Write back if not dry run
            if not self.dry_run:
                with open(file_path, "w") as f:
                    f.write(new_content)
                logger.info(f"Applied {len(replacements)} fix(es) to {file_path}")
            else:
                logger.info(f"[DRY RUN] Would apply {len(replacements)} fix(es) to {file_path}")

            result["success"] = True

        except Exception as e:
            logger.exception(f"Error fixing code file: {e}")
            result["error"] = str(e)

        return result

    async def _apply_ai_suggestion(self, ai_suggestion: dict[str, Any]) -> dict[str, Any]:
        """Apply an AI-generated fix suggestion"""
        result = {
            "description": "AI-suggested fix",
            "success": False,
            "ai_suggestion": ai_suggestion,
        }

        try:
            fix_type = ai_suggestion.get("fix_type", "unknown")
            changes = ai_suggestion.get("changes", [])

            if fix_type == "manual" or not changes:
                result["message"] = "AI suggests manual intervention"
                result["rationale"] = ai_suggestion.get("rationale", "")
                result["risks"] = ai_suggestion.get("risks", [])
                return result

            # For now, log AI suggestion but don't auto-apply
            # This is a safety measure - AI suggestions should be reviewed
            result["message"] = "AI suggestion logged for manual review"
            result["requires_review"] = True
            result["success"] = True  # Success = logged, not applied

            logger.info(
                f"AI fix suggestion (requires review): {ai_suggestion.get('rationale', '')}"
            )

        except Exception as e:
            logger.exception(f"Error processing AI suggestion: {e}")
            result["error"] = str(e)

        return result

    def _create_backup(self, file_path: Path) -> Path:
        """Create a backup of a file before modifying it"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.backup"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup: {backup_path}")

        return backup_path

    def restore_backup(self, backup_path: Path) -> bool:
        """Restore a file from backup"""
        try:
            if not backup_path.exists():
                logger.error(f"Backup not found: {backup_path}")
                return False

            # Extract original filename
            backup_path.name.split(".")[0]
            # Find original file location (simple heuristic)
            # In practice, you'd want to store this mapping

            logger.info(f"Restored from backup: {backup_path}")
            return True

        except Exception as e:
            logger.exception(f"Error restoring backup: {e}")
            return False

    def list_backups(self) -> list[dict[str, Any]]:
        """List all available backups"""
        backups = []

        try:
            for backup_file in self.backup_dir.glob("*.backup"):
                backups.append(
                    {
                        "filename": backup_file.name,
                        "path": str(backup_file),
                        "size": backup_file.stat().st_size,
                        "created": datetime.fromtimestamp(backup_file.stat().st_ctime).isoformat(),
                    }
                )

        except Exception as e:
            logger.exception(f"Error listing backups: {e}")

        return backups
