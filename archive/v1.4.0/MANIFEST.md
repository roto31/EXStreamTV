# EXStreamTV v1.4.0 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: macOS App (Phase 7)

## Summary

Native macOS menu bar application with SwiftUI.

## Components at This Version

| Component | Version | Status |
|-----------|---------|--------|
| macOS App | 1.4.0 | Created |

## macOS App Structure

### Package Configuration
- `Package.swift` - Swift Package Manager configuration
- `Sources/EXStreamTVApp.swift` - SwiftUI app entry point
- `Sources/AppDelegate.swift` - App delegate with notifications

### Services
- `Services/ServerManager.swift` - Python server lifecycle management
- `Services/ChannelManager.swift` - Channel status monitoring

### Views
- `Views/MenuBarView.swift` - Menu bar interface with channel status
- `Views/SettingsView.swift` - Preferences (server, channels, notifications)
- `Views/DashboardWindowView.swift` - Floating dashboard window
- `Views/AboutView.swift` - About panel

### Utilities
- `Utilities/Extensions.swift` - Swift extensions for formatting
- `Utilities/Logger.swift` - Unified logging

### Resources
- `Info.plist` - App configuration
- `EXStreamTV.entitlements` - App sandbox and network permissions
- `Assets.xcassets` - App icons and assets

## Previous Version

← v1.3.0: WebUI Extensions

## Next Version

→ v1.5.0: Testing Suite
