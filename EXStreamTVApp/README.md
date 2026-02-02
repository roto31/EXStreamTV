# EXStreamTV macOS Menu Bar App

A native macOS menu bar application for controlling the EXStreamTV IPTV streaming server.

## Features

### Core Features
- **Menu Bar Integration**: Quick access to server controls from the macOS menu bar
- **Server Management**: Start, stop, and restart the Python server
- **Live Status**: Real-time server status and active stream monitoring
- **Quick Actions**: Open Web UI, channels, logs with one click
- **Native Dashboard**: Embedded WebView dashboard window
- **Settings**: Configure server port, Python path, and preferences

### New in v1.4
- **Onboarding Wizard**: 6-step guided setup on first launch
- **AI Configuration**: Configure cloud (Groq, SambaNova) or local (Ollama) AI providers
- **Native Video Player**: Watch channels directly in the app with PiP support
- **Channel Switcher**: Quick channel navigation with keyboard shortcuts
- **System Notifications**: Alerts for server events, errors, and AI suggestions
- **Dock Badge**: Shows active stream count
- **Launch at Login**: Start automatically with macOS using SMAppService
- **Dependency Manager**: Check and install Python/FFmpeg dependencies

## Requirements

- macOS 13.0 (Ventura) or later
- Python 3.10+ with EXStreamTV package installed
- FFmpeg for streaming capabilities

## Building

### Using Swift Package Manager

```bash
cd EXStreamTVApp
swift build
```

### Using Xcode

1. Open the `EXStreamTVApp` folder in Xcode
2. Select your development team in Signing & Capabilities
3. Build and run (⌘R)

## Configuration

On first launch, the app will try to auto-detect the EXStreamTV server location. You can configure:

- **Server Port**: Default is 8411
- **Python Path**: Path to Python 3 executable
- **Server Path**: Path to the EXStreamTV project directory
- **Auto-start**: Start server automatically when app launches
- **Launch at Login**: Start the menu bar app at system login

## Usage

### Menu Bar Icon

- Click the TV icon in the menu bar to open the control panel
- The icon shows active stream count when streaming
- Green indicates server is running, gray when stopped

### Server Control

- **Start**: Launch the Python EXStreamTV server
- **Stop**: Gracefully stop the server
- **Restart**: Stop and restart the server

### Quick Actions

- **Open Web UI**: Opens the full web interface in your browser
- **Open Dashboard**: Opens the native dashboard window
- **View Channels**: Jump to channel management
- **View Logs**: View server logs

### Settings

Access via the gear icon in the menu bar popover or ⌘, shortcut.

## Architecture

```
EXStreamTVApp/
├── Package.swift              # Swift Package manifest
├── Sources/
│   ├── EXStreamTVApp.swift    # Main app entry point
│   ├── AppDelegate.swift      # Application delegate (with onboarding)
│   ├── Services/
│   │   ├── ServerManager.swift       # Python server control
│   │   ├── ChannelManager.swift      # Channel data management
│   │   ├── AIProviderManager.swift   # AI provider configuration
│   │   ├── DependencyManager.swift   # Python/FFmpeg dependency checks
│   │   ├── LoginItemManager.swift    # Launch at Login (SMAppService)
│   │   └── NotificationManager.swift # System notifications
│   ├── Views/
│   │   ├── MenuBarView.swift         # Menu bar popover
│   │   ├── SettingsView.swift        # Settings window (with AI tab)
│   │   ├── AISettingsView.swift      # AI provider configuration UI
│   │   ├── PlayerView.swift          # Native video player
│   │   ├── ChannelSwitcher.swift     # Channel switching overlay
│   │   ├── DashboardWindowView.swift # Native dashboard
│   │   ├── AboutView.swift           # About window
│   │   └── Onboarding/               # Onboarding wizard views
│   │       ├── OnboardingWizard.swift
│   │       ├── OnboardingState.swift
│   │       ├── AISetupStep.swift
│   │       ├── GroqSetupView.swift
│   │       └── LocalAISetupView.swift
│   ├── Utilities/
│   │   ├── Extensions.swift  # Swift extensions
│   │   └── Logger.swift      # Logging utilities
│   └── Resources/
│       ├── Assets.xcassets/  # App icons and colors
│       ├── Info.plist        # App metadata
│       └── EXStreamTV.entitlements
└── README.md
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd+G` | Open channel switcher |
| `Cmd+Up` | Previous channel |
| `Cmd+Down` | Next channel |
| `Cmd+,` | Open Settings |
| `Cmd+Q` | Quit app |
| `Space` | Play/Pause (in player) |
| `M` | Mute (in player) |
| `F` | Fullscreen (in player) |

## Code Signing and Distribution

### Requirements for Distribution

To distribute the EXStreamTV macOS app via TestFlight or the App Store, you need:

1. **Apple Developer Program Membership** ($99/year)
2. **Xcode 15+** installed on macOS
3. **Valid signing certificates** in your Keychain

### Creating an Xcode Project from Package.swift

The app uses Swift Package Manager. To create an Xcode project for signing:

```bash
# Navigate to the app directory
cd EXStreamTVApp

# Generate Xcode project (optional - Xcode can open Package.swift directly)
swift package generate-xcodeproj
```

Alternatively, open `Package.swift` directly in Xcode 15+:

```bash
open Package.swift
```

### Configuring Code Signing

1. **Open in Xcode**: Open `Package.swift` in Xcode
2. **Select the target**: Click on "EXStreamTVApp" in the project navigator
3. **Signing & Capabilities tab**:
   - Enable "Automatically manage signing"
   - Select your Development Team
   - Bundle Identifier: `com.exstreamtv.app` (or your custom identifier)
4. **Verify entitlements**: Ensure `EXStreamTV.entitlements` is linked

### Building for Distribution

#### Development Build

```bash
swift build -c release
```

#### Archive for Distribution

In Xcode:
1. Select **Product > Archive**
2. Wait for the archive to complete
3. In the Organizer, select **Distribute App**

### Notarization

Apple requires notarization for apps distributed outside the App Store.

#### Using xcrun notarytool

```bash
# Store credentials (one-time setup)
xcrun notarytool store-credentials "AC_PASSWORD" \
  --apple-id "your-apple-id@email.com" \
  --team-id "YOUR_TEAM_ID" \
  --password "app-specific-password"

# Create a ZIP of the app
ditto -c -k --keepParent "EXStreamTVApp.app" "EXStreamTVApp.zip"

# Submit for notarization
xcrun notarytool submit "EXStreamTVApp.zip" \
  --keychain-profile "AC_PASSWORD" \
  --wait

# Staple the ticket to the app
xcrun stapler staple "EXStreamTVApp.app"
```

#### Verifying Notarization

```bash
spctl -a -t exec -vv "EXStreamTVApp.app"
```

### TestFlight Distribution

To distribute via TestFlight:

1. **Create App in App Store Connect**:
   - Go to [App Store Connect](https://appstoreconnect.apple.com)
   - Create new app with Bundle ID `com.exstreamtv.app`

2. **Archive in Xcode**:
   - Product > Archive
   - Select the archive in Organizer

3. **Upload to TestFlight**:
   - Click "Distribute App"
   - Select "App Store Connect"
   - Choose "Upload"
   - Complete the upload wizard

4. **Configure TestFlight**:
   - In App Store Connect, go to TestFlight
   - Add internal/external testers
   - Submit for Beta App Review (external testers)

### GitHub Release Distribution

For distribution via GitHub Releases:

1. **Build the release**:
   ```bash
   swift build -c release
   ```

2. **Create DMG** (optional):
   ```bash
   # Create a temporary directory
   mkdir -p dmg_contents
   cp -R .build/release/EXStreamTVApp.app dmg_contents/
   
   # Create DMG
   hdiutil create -volname "EXStreamTV" \
     -srcfolder dmg_contents \
     -ov -format UDZO \
     "EXStreamTV-1.4.0.dmg"
   ```

3. **Create ZIP**:
   ```bash
   ditto -c -k --keepParent ".build/release/EXStreamTVApp.app" "EXStreamTVApp.zip"
   ```

4. **Upload to GitHub Release**:
   - Create a new release on GitHub
   - Attach the DMG or ZIP file
   - Include release notes

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "Developer cannot be verified" | Right-click app, select Open, then click Open |
| Signing identity not found | Install certificates in Keychain Access |
| Notarization fails | Check bundle ID matches App Store Connect |
| TestFlight upload fails | Verify version/build numbers are incremented |

### Entitlements Reference

The app uses the following entitlements (`EXStreamTV.entitlements`):

```xml
<key>com.apple.security.app-sandbox</key>
<false/>
<key>com.apple.security.network.client</key>
<true/>
<key>com.apple.security.network.server</key>
<true/>
<key>com.apple.security.files.user-selected.read-write</key>
<true/>
<key>com.apple.security.automation.apple-events</key>
<true/>
```

Note: App Sandbox is disabled to allow process management (starting/stopping the Python server).

## Documentation

For detailed usage instructions, see:
- [macOS App Guide](../docs/guides/MACOS_APP_GUIDE.md) - Complete user guide
- [Onboarding Guide](../docs/guides/ONBOARDING.md) - First-run wizard
- [AI Setup Guide](../docs/guides/AI_SETUP.md) - AI configuration

## License

MIT License - See LICENSE file for details.
