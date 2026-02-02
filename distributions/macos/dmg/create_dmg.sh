#!/bin/bash
#
# Create DMG installer for EXStreamTV
#

set -e

# Configuration
APP_NAME="EXStreamTV"
DMG_NAME="EXStreamTV-Installer"
VERSION="${1:-1.4.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
BUILD_DIR="$PROJECT_DIR/build"
DMG_DIR="$BUILD_DIR/dmg"
OUTPUT_DIR="$PROJECT_DIR/dist"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Creating DMG for ${APP_NAME} v${VERSION}${NC}"

# Clean and create directories
rm -rf "$DMG_DIR"
mkdir -p "$DMG_DIR" "$OUTPUT_DIR"

# Build the app first (if not already built)
if [[ ! -d "$BUILD_DIR/${APP_NAME}App.app" ]]; then
    echo "Building ${APP_NAME}App..."
    cd "$PROJECT_DIR/EXStreamTVApp"
    swift build -c release
    
    # Create app bundle from built executable
    # (This is simplified - real implementation would use xcodebuild)
fi

# Copy app to DMG staging directory
cp -R "$BUILD_DIR/${APP_NAME}App.app" "$DMG_DIR/"

# Create Applications symlink
ln -s /Applications "$DMG_DIR/Applications"

# Copy background image if exists
if [[ -f "$SCRIPT_DIR/dmg_background.png" ]]; then
    mkdir -p "$DMG_DIR/.background"
    cp "$SCRIPT_DIR/dmg_background.png" "$DMG_DIR/.background/background.png"
fi

# Create temporary DMG
TEMP_DMG="$BUILD_DIR/temp_${DMG_NAME}.dmg"
FINAL_DMG="$OUTPUT_DIR/${DMG_NAME}-${VERSION}.dmg"

# Remove existing DMGs
rm -f "$TEMP_DMG" "$FINAL_DMG"

# Create DMG using hdiutil
echo "Creating DMG..."
hdiutil create -volname "$APP_NAME" \
    -srcfolder "$DMG_DIR" \
    -ov -format UDRW \
    "$TEMP_DMG"

# Mount the DMG
MOUNT_DIR=$(hdiutil attach -readwrite -noverify "$TEMP_DMG" | grep "Volumes" | awk '{print $3}')

echo "Configuring DMG window..."

# Set window properties using AppleScript
osascript << EOF
tell application "Finder"
    tell disk "${APP_NAME}"
        open
        
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set bounds of container window to {400, 100, 920, 440}
        
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 80
        
        -- Position icons
        set position of item "${APP_NAME}App.app" of container window to {130, 180}
        set position of item "Applications" of container window to {390, 180}
        
        -- Set background image if it exists
        try
            set background picture of viewOptions to file ".background:background.png"
        end try
        
        close
        open
        
        update without registering applications
        delay 1
    end tell
end tell
EOF

# Sync and unmount
sync
hdiutil detach "$MOUNT_DIR"

# Convert to compressed read-only DMG
echo "Compressing DMG..."
hdiutil convert "$TEMP_DMG" -format UDZO -imagekey zlib-level=9 -o "$FINAL_DMG"

# Clean up
rm -f "$TEMP_DMG"

echo -e "${GREEN}DMG created: $FINAL_DMG${NC}"

# Calculate size and checksum
DMG_SIZE=$(du -h "$FINAL_DMG" | awk '{print $1}')
DMG_SHA256=$(shasum -a 256 "$FINAL_DMG" | awk '{print $1}')

echo "Size: $DMG_SIZE"
echo "SHA256: $DMG_SHA256"

# Create checksum file
echo "$DMG_SHA256  ${DMG_NAME}-${VERSION}.dmg" > "$OUTPUT_DIR/${DMG_NAME}-${VERSION}.dmg.sha256"

echo -e "${GREEN}Done!${NC}"
