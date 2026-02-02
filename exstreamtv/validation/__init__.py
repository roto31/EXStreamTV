"""YAML validation using JSON schemas"""

from .validator import ValidationError, YAMLValidator

# Optional imports for file watching (requires watchdog)
try:
    from .yaml_watcher import YAMLFileHandler, YAMLWatcher

    WATCHDOG_AVAILABLE = True
except ImportError:
    YAMLWatcher = None  # type: ignore
    YAMLFileHandler = None  # type: ignore
    WATCHDOG_AVAILABLE = False

# Optional imports for live validation (requires watchdog)
try:
    from .live_validator import LiveValidator, ValidationResult

    LIVE_VALIDATOR_AVAILABLE = True
except ImportError:
    LiveValidator = None  # type: ignore
    ValidationResult = None  # type: ignore
    LIVE_VALIDATOR_AVAILABLE = False

__all__ = ["ValidationError", "YAMLValidator"]
if WATCHDOG_AVAILABLE:
    __all__.extend(["YAMLFileHandler", "YAMLWatcher"])
if LIVE_VALIDATOR_AVAILABLE:
    __all__.extend(["LiveValidator", "ValidationResult"])
