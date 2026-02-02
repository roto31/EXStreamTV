# EXStreamTV Version Archive

This directory contains historical version documentation for the EXStreamTV platform.

## Purpose

The archive serves as a reference for:
1. **Version History**: Understanding what was available at each release
2. **Rollback Reference**: Knowing what components existed in previous versions
3. **Change Tracking**: Documenting the evolution of the platform

## Structure

Each version directory contains:

```
v{X.Y.Z}/
├── VERSION          # Platform version number
├── MANIFEST.md      # Component inventory at this version
└── components/      # (Optional) Component-specific changelogs
    └── {component}/
        └── CHANGELOG.md
```

## Version History

| Version | Date | Summary |
|---------|------|---------|
| [v2.5.0](../Build/v2.5.0/) | 2026-01-17 | Block Schedule Database Integration |
| [v2.4.0](v2.4.0/) | 2026-01-17 | AI Channel Creator API Endpoints |
| [v2.3.0](v2.3.0/) | 2026-01-17 | AI Channel Creator Infrastructure |
| [v2.2.0](v2.2.0/) | 2026-01-17 | Complete AI Persona Suite |
| [v2.1.0](v2.1.0/) | 2026-01-17 | AI Channel Creator Personas |
| [v2.0.1](v2.0.1/) | 2026-01-17 | Media Filtering & UI Improvements |
| [v2.0.0](v2.0.0/) | 2026-01-14 | ErsatzTV-Compatible API & Integrations |
| [v1.8.0](v1.8.0/) | 2026-01-14 | Performance Optimization |
| [v1.6.0](v1.6.0/) | 2026-01-14 | Documentation & Release |
| [v1.5.0](v1.5.0/) | 2026-01-14 | Testing Suite |
| [v1.4.0](v1.4.0/) | 2026-01-14 | macOS App Enhancement |
| [v1.3.0](v1.3.0/) | 2026-01-14 | WebUI Extensions |
| [v1.2.0](v1.2.0/) | 2026-01-14 | Local Media Libraries |
| [v1.0.9](v1.0.9/) | 2026-01-14 | ErsatzTV Playout Engine |
| [v1.0.8](v1.0.8/) | 2026-01-14 | ErsatzTV FFmpeg Pipeline |
| [v1.0.7](v1.0.7/) | 2026-01-14 | Import Path Updates |
| [v1.0.6](v1.0.6/) | 2026-01-14 | Complete Module Port |
| [v1.0.5](v1.0.5/) | 2026-01-14 | WebUI Templates |
| [v1.0.4](v1.0.4/) | 2026-01-14 | AI Agent Module |
| [v1.0.3](v1.0.3/) | 2026-01-14 | Streaming Module |
| [v1.0.2](v1.0.2/) | 2026-01-14 | Database Models & FFmpeg |
| [v1.0.1](v1.0.1/) | 2026-01-14 | Project Infrastructure |
| [v1.0.0](v1.0.0/) | 2026-01-14 | Initial Project Creation |

## Notes

- Archive versions contain **documentation only**, not source code snapshots
- Source code history is maintained in Git
- The current version is always in `Build/v{X.Y.Z}/` (real file copies, NOT symlinks)
- Components maintain their own VERSION and CHANGELOG.md files
- No symbolic links are used anywhere in the versioning system

## Versioning Standard

EXStreamTV follows [Semantic Versioning 2.0.0](https://semver.org):

- **MAJOR** (X): Breaking/incompatible API changes
- **MINOR** (Y): Backward-compatible functionality additions
- **PATCH** (Z): Backward-compatible bug fixes
