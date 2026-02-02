"""YAML validation API endpoints"""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

# Optional imports - handle missing watchdog gracefully
try:
    from ..validation import LiveValidator, ValidationResult

    LIVE_VALIDATOR_AVAILABLE = True
except ImportError:
    LiveValidator = None  # type: ignore
    ValidationResult = None  # type: ignore
    LIVE_VALIDATOR_AVAILABLE = False


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/validation", tags=["Validation"])

# Global live validator instance
_live_validator: Any | None = None


def get_live_validator() -> Any | None:
    """Get the global live validator instance"""
    return _live_validator


def init_live_validator() -> Any | None:
    """Initialize the global live validator.

    Returns:
        Any | None: LiveValidator instance if successful, None otherwise
    """
    global _live_validator

    if not LIVE_VALIDATOR_AVAILABLE:
        logger.warning(
            "Live validator not available: watchdog module is required. Install with: pip install watchdog"
        )
        return None

    if _live_validator is not None:
        return _live_validator

    # Determine watch directories
    base_dir = Path(__file__).parent.parent.parent
    watch_directories = [base_dir / "schedules", base_dir / "data", base_dir / "archive"]

    # Filter to only existing directories
    watch_directories = [d for d in watch_directories if d.exists()]

    if not watch_directories:
        logger.warning("No watch directories found for YAML validation")
        return None

    try:
        _live_validator = LiveValidator(
            watch_directories=watch_directories,
            cache_ttl_seconds=300,  # 5 minutes
        )

        # Start watching
        _live_validator.start_watching()

        # Validate all existing files
        _live_validator.validate_all_files()

        logger.info(f"Live validator initialized, watching {len(watch_directories)} directories")

        return _live_validator
    except Exception as e:
        logger.error(f"Failed to initialize live validator: {e}", exc_info=True)
        return None


@router.get("/status")
def get_validation_status(
    validator: Any | None = Depends(get_live_validator),
) -> dict[str, Any]:
    """Get validation status.

    Returns:
        dict[str, Any]: Status dictionary with enabled flag, watching status, and file counts

    Raises:
        HTTPException: Never raised (returns disabled status if validator unavailable)
    """
    if validator is None:
        return {"enabled": False, "message": "Live validator not initialized"}

    results = validator.get_all_results()
    valid_count = sum(1 for r in results.values() if r.valid)
    invalid_count = len(results) - valid_count

    return {
        "enabled": True,
        "watching": validator.watcher.is_running() if validator.watcher else False,
        "total_files": len(results),
        "valid_files": valid_count,
        "invalid_files": invalid_count,
    }


@router.get("/results")
def get_all_validation_results(
    validator: Any | None = Depends(get_live_validator),
) -> dict[str, Any]:
    """Get all validation results.

    Returns:
        dict[str, Any]: Dictionary containing results list

    Raises:
        HTTPException: 503 if live validator not initialized
    """
    if validator is None:
        raise HTTPException(status_code=503, detail="Live validator not initialized")

    results = validator.get_all_results()
    return {"results": [r.to_dict() for r in results.values()]}


@router.get("/results/{file_path:path}")
def get_validation_result(
    file_path: str, validator: Any | None = Depends(get_live_validator)
) -> dict[str, Any]:
    """Get validation result for a specific file.

    Args:
        file_path: Path to the file (can be relative or absolute)

    Returns:
        dict[str, Any]: Validation result dictionary

    Raises:
        HTTPException: 503 if validator not initialized, 404 if file not found
    """
    if validator is None:
        raise HTTPException(status_code=503, detail="Live validator not initialized")

    file_path_obj = Path(file_path)
    if not file_path_obj.is_absolute():
        # Try to resolve relative to common directories
        base_dir = Path(__file__).parent.parent.parent
        possible_paths = [
            base_dir / file_path,
            base_dir / "schedules" / file_path,
            base_dir / "data" / file_path,
            base_dir / "archive" / file_path,
        ]

        for path in possible_paths:
            if path.exists():
                file_path_obj = path
                break
        else:
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    result = validator.validate_file(file_path_obj, force=True)
    return result.to_dict()


@router.post("/validate")
def validate_file(
    file_path: str,
    force: bool = False,
    validator: Any | None = Depends(get_live_validator),
) -> dict[str, Any]:
    """Manually trigger validation for a file.

    Args:
        file_path: Path to the file to validate
        force: Force re-validation even if cached result exists

    Returns:
        dict[str, Any]: Validation result dictionary

    Raises:
        HTTPException: 503 if validator not initialized, 404 if file not found
    """
    if validator is None:
        raise HTTPException(status_code=503, detail="Live validator not initialized")

    file_path_obj = Path(file_path)
    if not file_path_obj.is_absolute():
        base_dir = Path(__file__).parent.parent.parent
        file_path_obj = base_dir / file_path

    if not file_path_obj.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    result = validator.validate_file(file_path_obj, force=force)
    return result.to_dict()


@router.post("/validate-all")
def validate_all_files(
    validator: Any | None = Depends(get_live_validator),
) -> dict[str, Any]:
    """Manually trigger validation for all watched files.

    Returns:
        dict[str, Any]: Dictionary with results list, total, valid, and invalid counts

    Raises:
        HTTPException: 503 if validator not initialized
    """
    if validator is None:
        raise HTTPException(status_code=503, detail="Live validator not initialized")

    results = validator.validate_all_files()
    return {
        "results": [r.to_dict() for r in results.values()],
        "total": len(results),
        "valid": sum(1 for r in results.values() if r.valid),
        "invalid": sum(1 for r in results.values() if not r.valid),
    }


@router.post("/clear-cache")
def clear_validation_cache(
    validator: Any | None = Depends(get_live_validator),
) -> dict[str, str]:
    """Clear validation cache.

    Returns:
        dict[str, str]: Success message dictionary

    Raises:
        HTTPException: 503 if validator not initialized
    """
    if validator is None:
        raise HTTPException(status_code=503, detail="Live validator not initialized")

    validator.clear_cache()
    return {"message": "Cache cleared"}
