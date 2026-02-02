# WebUI Templates Component Changelog

All notable changes to the WebUI Templates component will be documented in this file.

## [2.5.0] - 2026-01-17
### Changed
- No changes to templates in this release

## [2.4.0] - 2026-01-17
### Enhanced
- `ai_channel.html` - Enhanced with new features
  - **Persona Selector Grid**: Visual persona selection before starting session
  - **Dynamic Header**: Updates to show selected persona's name and title
  - **Change Persona Button**: Switch personas mid-conversation
  - **Enhanced Preview Panel**: Improved styling with section icons, source badges
  - New CSS classes: `.persona-selector`, `.persona-grid`, `.persona-card`, `.plan-section`, `.plan-warning`, `.source-badge`, `.btn-ghost`

## [2.0.1] - 2026-01-17
### Added
- `media.html` - Collapsible advanced filters panel
  - Filter dropdowns: Type, Year (with decade ranges), Duration, Content Rating
  - Genre text input with debounce
  - Sort controls with ascending/descending toggle
  - Active filter count badge
  - "Clear All Filters" button

### Fixed
- Missing `</div>` tag in filters panel
- Grid class not reset when switching libraries
- View mode rendering wrong variable
- Missing loading element
- Poster cropping in detail panel

## [2.0.0] - 2026-01-14
### Added
- Blocks management page with group support
- Filler presets page with mode-specific fields
- Templates page with enable/disable toggles
- Deco page with type badges and grouping
- Updated navigation with new menu items

## [1.3.0] - 2026-01-14
### Added
- `dashboard.html` - Enhanced dashboard with live stats
- `guide.html` - EPG/Program Guide with timeline view
- `media_browser.html` - Media browser with filters
- `schedule_builder.html` - Visual schedule builder
- `system_monitor.html` - System resource monitoring
- `channel_editor.html` - Channel configuration editor
- `libraries.html` - Library management UI

## [1.0.5] - 2026-01-14
### Added
- Initial port of 36 HTML templates with Apple Design System styling
- Dashboard, Channels, Playlists, Schedules, Playouts pages
- Settings pages: FFmpeg, HDHomeRun, Plex, Security, Resolutions, Watermarks
- Authentication pages: YouTube, Archive.org, OAuth setup
- Media management: Collections, Import, Player
- AI integration: Ollama chat, Log analysis
- Static assets: `apple-design-system.css`, `apple-animations.js`
