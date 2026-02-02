# macOS App Component Changelog

All notable changes to the macOS App component will be documented in this file.

## [2.5.0] - 2026-01-17
### Changed
- No changes to macOS app in this release

## [1.4.0] - 2026-01-14
### Added
- **Package Structure**
  - `Package.swift` - Swift Package Manager configuration
  - `Sources/EXStreamTVApp.swift` - SwiftUI app entry point
  - `Sources/AppDelegate.swift` - App delegate with notifications

- **Services**
  - `Services/ServerManager.swift` - Python server lifecycle management
  - `Services/ChannelManager.swift` - Channel status monitoring
  - `Services/DependencyManager.swift` - Dependency management
  - `Services/LoginItemManager.swift` - Login item handling
  - `Services/NotificationManager.swift` - Notification handling
  - `Services/AIProviderManager.swift` - AI provider management

- **Views**
  - `Views/MenuBarView.swift` - Menu bar interface with channel status
  - `Views/SettingsView.swift` - Preferences (server, channels, notifications)
  - `Views/DashboardWindowView.swift` - Floating dashboard window
  - `Views/AboutView.swift` - About panel

- **Utilities**
  - `Utilities/Extensions.swift` - Swift extensions for formatting
  - `Utilities/Logger.swift` - Unified logging

- **Resources**
  - `Info.plist` - App configuration
  - `EXStreamTV.entitlements` - App sandbox and network permissions
  - `Assets.xcassets` - App icons and assets
