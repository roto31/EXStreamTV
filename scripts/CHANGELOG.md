# Scripts Component Changelog

All notable changes to the Scripts component will be documented in this file.

## [2.5.0] - 2026-01-25
### Added
- `version_bump.py` - Version synchronization tool for platform releases
  - Bumps version across all component VERSION files
  - Updates pyproject.toml and root VERSION
  - Creates Build folder for new versions
  - Supports dry-run mode and single-component updates
- `release.py` - Release management tool
  - Validates version consistency across all files
  - Generates build manifests (Markdown and JSON)
  - Archives previous versions to archive folder
  - Prepares releases with pre-flight checks

## [1.0.2] - 2026-01-14
### Added
- `migrate_from_streamtv.py` - StreamTV database migration script
- `migrate_from_ersatztv.py` - ErsatzTV database migration script
- `migrate_schema.py` - Schema migration utilities
- `install_macos.sh` - macOS installation script
