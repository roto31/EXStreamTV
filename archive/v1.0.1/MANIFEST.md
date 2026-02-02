# EXStreamTV v1.0.1 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: Infrastructure Setup

## Summary

Project directory structure and core configuration system.

## Components at This Version

| Component | Version | Status |
|-----------|---------|--------|
| Backend Core | 1.0.1 | Created |
| Database | 1.0.1 | Created |
| Documentation | 1.0.1 | Created |
| Distributions | 1.0.1 | Created |
| Containers | 1.0.1 | Created |

## Files Created

### Core Package
- `exstreamtv/__init__.py`
- `exstreamtv/config.py` - Configuration system

### Database
- `exstreamtv/database/__init__.py`
- `exstreamtv/database/connection.py` - Database connection management
- `exstreamtv/database/models/` - Models package structure

### Configuration
- `requirements.txt` - Production dependencies
- `requirements-dev.txt` - Development dependencies
- `pyproject.toml` - Python packaging configuration
- `.gitignore` - Python/Xcode/macOS artifacts
- `config.example.yaml` - All configuration options

### Documentation
- `docs/` - Documentation structure
- `docs/BUILD_PROGRESS.md` - Build tracking
- `docs/architecture/SYSTEM_DESIGN.md` - System architecture

### Infrastructure
- `tests/` - Test directory structure
- `EXStreamTVApp/` - macOS menu bar app placeholder
- `containers/` - Docker/Kubernetes configs
- `distributions/` - Platform installers
- `scripts/` - Migration and utility scripts

## Previous Version

← v1.0.0: Initial Project Creation

## Next Version

→ v1.0.2: Database Models & FFmpeg
