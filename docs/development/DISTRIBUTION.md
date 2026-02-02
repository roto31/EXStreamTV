# Distribution Guide

Developer documentation for building, signing, and distributing EXStreamTV.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Building the App](#building-the-app)
- [Creating a DMG](#creating-a-dmg)
- [Creating a PKG](#creating-a-pkg)
- [Code Signing](#code-signing)
- [Notarization](#notarization)
- [Bundled Dependencies](#bundled-dependencies)
- [Release Checklist](#release-checklist)

---

## Overview

EXStreamTV can be distributed in two formats:

| Format | Use Case | Includes |
|--------|----------|----------|
| **DMG** | Simple drag-and-drop install | App bundle only |
| **PKG** | Full installer with options | App + dependencies + AI setup |

Both require code signing and notarization for distribution outside the Mac App Store.

---

## Prerequisites

### Developer Requirements

1. **Apple Developer Account** ($99/year for distribution)
2. **Developer ID Application Certificate**
3. **Developer ID Installer Certificate** (for PKG)
4. **Xcode Command Line Tools**

### Install Certificates

1. Open Keychain Access
2. Go to **Keychain Access** > **Certificate Assistant** > **Request Certificate from CA**
3. Upload to [developer.apple.com](https://developer.apple.com/account/resources/certificates)
4. Download and install the certificates

### Verify Certificates

```bash
# List available signing identities
security find-identity -v -p codesigning

# Should show something like:
# "Developer ID Application: Your Name (TEAM_ID)"
# "Developer ID Installer: Your Name (TEAM_ID)"
```

---

## Building the App

### Release Build

```bash
cd EXStreamTVApp

# Build for release
swift build -c release

# Or build universal binary (Intel + Apple Silicon)
swift build -c release --arch arm64 --arch x86_64
```

### Create App Bundle

The build output is in `.build/release/`. For distribution, create a proper app bundle:

```bash
# Copy to build directory
mkdir -p ../build
cp -r .build/release/EXStreamTVApp.app ../build/
```

### Verify Build

```bash
# Check the binary
file build/EXStreamTVApp.app/Contents/MacOS/EXStreamTVApp
# Should show: Mach-O universal binary with 2 architectures

# Check bundle info
plutil -p build/EXStreamTVApp.app/Contents/Info.plist
```

---

## Creating a DMG

Use the provided script to create a DMG installer.

### Using create_dmg.sh

```bash
cd distributions/macos/dmg

# Create DMG with version number
./create_dmg.sh 1.4.0
```

### What the Script Does

1. Creates staging directory
2. Copies app bundle
3. Creates Applications symlink
4. Sets window layout
5. Compresses to DMG
6. Generates SHA256 checksum

### Output

```
dist/
├── EXStreamTV-Installer-1.4.0.dmg
└── EXStreamTV-Installer-1.4.0.dmg.sha256
```

### Manual DMG Creation

```bash
# Create temporary DMG
hdiutil create -volname "EXStreamTV" \
    -srcfolder build/staging \
    -ov -format UDRW \
    temp.dmg

# Convert to compressed
hdiutil convert temp.dmg -format UDZO -o EXStreamTV-1.4.0.dmg
```

---

## Creating a PKG

The PKG installer provides a full installation experience with AI setup options.

### Structure

```
distributions/macos/pkg/
├── Distribution.xml      # Installer UI definition
├── scripts/
│   ├── preinstall       # Pre-installation checks
│   └── postinstall      # Post-installation setup
└── resources/
    ├── welcome.html     # Welcome page
    ├── license.html     # License agreement
    ├── ai_setup.html    # AI provider selection
    └── conclusion.html  # Completion page
```

### Building the PKG

```bash
# Build component packages
pkgbuild --root build/EXStreamTVApp.app \
    --identifier com.exstreamtv.app \
    --version 1.4.0 \
    --install-location /Applications/EXStreamTV.app \
    app.pkg

# Build distribution package
productbuild --distribution Distribution.xml \
    --resources resources \
    --package-path . \
    EXStreamTV-1.4.0.pkg
```

### AI Setup in PKG

The `Distribution.xml` includes AI provider choices:

```xml
<choice id="ai-cloud" title="Cloud AI (Recommended)">
    <!-- Configures cloud AI in postinstall -->
</choice>
<choice id="ai-local" title="Local AI">
    <!-- Installs Ollama and downloads model -->
</choice>
<choice id="ai-skip" title="Skip">
    <!-- User configures later -->
</choice>
```

The `postinstall` script handles the selected option.

---

## Code Signing

All distributed apps must be signed with your Developer ID.

### Using sign_app.sh

```bash
cd distributions/macos

# Sign with automatic identity detection
./sign_app.sh ../build/EXStreamTVApp.app

# Or specify identity
SIGNING_IDENTITY="Developer ID Application: Your Name (TEAM_ID)" \
./sign_app.sh ../build/EXStreamTVApp.app
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SIGNING_IDENTITY` | Full name of signing certificate |

### What Gets Signed

1. Embedded frameworks (in order)
2. Dynamic libraries
3. Helper executables
4. Main app bundle (with entitlements)

### Entitlements

The app requires these entitlements (`EXStreamTVApp.entitlements`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <key>com.apple.security.app-sandbox</key>
    <false/>
    <key>com.apple.security.network.client</key>
    <true/>
    <key>com.apple.security.network.server</key>
    <true/>
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
</dict>
</plist>
```

### Verify Signing

```bash
# Check signature
codesign --verify --deep --strict --verbose=2 EXStreamTVApp.app

# Check entitlements
codesign -d --entitlements - EXStreamTVApp.app

# Gatekeeper check
spctl --assess --type execute --verbose EXStreamTVApp.app
```

---

## Notarization

Apple requires notarization for apps distributed outside the Mac App Store.

### Using notarize.sh

```bash
cd distributions/macos

# Set credentials
export APPLE_ID="your@email.com"
export TEAM_ID="YOURTEAMID"
export APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"  # App-specific password

# Notarize
./notarize.sh ../dist/EXStreamTV-Installer-1.4.0.dmg
```

### Getting an App-Specific Password

1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign in > Security > App-Specific Passwords
3. Generate a new password
4. Use this password for `APP_PASSWORD`

### Manual Notarization

```bash
# Store credentials
xcrun notarytool store-credentials "EXStreamTV" \
    --apple-id "your@email.com" \
    --team-id "YOURTEAMID" \
    --password "xxxx-xxxx-xxxx-xxxx"

# Submit for notarization
xcrun notarytool submit EXStreamTV-1.4.0.dmg \
    --keychain-profile "EXStreamTV" \
    --wait

# Staple the ticket
xcrun stapler staple EXStreamTV-1.4.0.dmg
```

### Checking Status

```bash
# Get submission log
xcrun notarytool log <submission-id> \
    --keychain-profile "EXStreamTV" \
    log.json

# View log
cat log.json | python3 -m json.tool
```

### Common Issues

**"The signature of the binary is invalid"**
- Re-sign with `--options runtime` flag
- Ensure all nested bundles are signed

**"The executable requests the com.apple.security.* entitlement"**
- Check entitlements are correct
- Hardened Runtime must be enabled

---

## Bundled Dependencies

The PKG installer can include bundled Python and FFmpeg.

### Structure

```
distributions/macos/bundled/
├── python/           # Python 3.11 distribution
│   ├── bin/python3
│   └── lib/
└── ffmpeg/           # FFmpeg binaries
    └── bin/
        ├── ffmpeg
        └── ffprobe
```

### Obtaining Python

```bash
# Build Python with universal binary
./configure --enable-universalsdk --with-universal-archs=universal2
make
make install DESTDIR=bundled/python
```

Or use the official installer and extract:

```bash
# Download from python.org
curl -O https://www.python.org/ftp/python/3.11.7/python-3.11.7-macos11.pkg
```

### Obtaining FFmpeg

Download static builds from [evermeet.cx](https://evermeet.cx/ffmpeg/):

```bash
curl -O https://evermeet.cx/ffmpeg/ffmpeg-6.1.1.zip
curl -O https://evermeet.cx/ffmpeg/ffprobe-6.1.1.zip
unzip ffmpeg-6.1.1.zip -d bundled/ffmpeg/bin/
unzip ffprobe-6.1.1.zip -d bundled/ffmpeg/bin/
```

### Size Optimization

```bash
# Strip Python test files
find bundled/python -name "test" -type d -exec rm -rf {} +
find bundled/python -name "__pycache__" -exec rm -rf {} +

# Total size: ~150MB (Python ~100MB, FFmpeg ~50MB)
```

---

## Release Checklist

### Before Building

- [ ] Update version in `Package.swift`
- [ ] Update version in `Info.plist`
- [ ] Update `CHANGELOG.md`
- [ ] Run all tests
- [ ] Test on macOS 13, 14, and 15

### Build Process

- [ ] Create release build
- [ ] Build universal binary (Intel + Apple Silicon)
- [ ] Verify app launches on both architectures

### Code Signing

- [ ] Sign app with Developer ID
- [ ] Verify signature: `codesign --verify`
- [ ] Test Gatekeeper: `spctl --assess`

### Create Installers

- [ ] Create DMG: `./create_dmg.sh X.Y.Z`
- [ ] Create PKG (if applicable)
- [ ] Verify DMG mounts correctly
- [ ] Test PKG installation

### Notarization

- [ ] Submit DMG for notarization
- [ ] Submit PKG for notarization
- [ ] Staple tickets
- [ ] Verify: `xcrun stapler validate`

### Distribution

- [ ] Upload to GitHub Releases
- [ ] Update download links in README
- [ ] Announce release
- [ ] Update documentation

### Post-Release

- [ ] Monitor for crash reports
- [ ] Respond to initial feedback
- [ ] Tag release in git: `git tag v2.6.0`

---

## Troubleshooting

### "Code signature invalid"

```bash
# Re-sign everything
codesign --force --deep --options runtime --timestamp \
    --sign "Developer ID Application: ..." \
    EXStreamTVApp.app
```

### "Notarization failed: The software is not signed"

Ensure you're using `--options runtime` when signing:

```bash
codesign --options runtime --timestamp --sign "..." app.app
```

### "Package is damaged" on first launch

The app needs to be notarized and stapled:

```bash
xcrun stapler staple EXStreamTV.dmg
```

### PKG fails system requirements check

Check the JavaScript in Distribution.xml:

```javascript
function installCheck() {
    if (system.version.ProductVersion < '13.0') {
        my.result.message = 'Requires macOS 13.0+';
        return false;
    }
    return true;
}
```
