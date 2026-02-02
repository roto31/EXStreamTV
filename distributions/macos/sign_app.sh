#!/bin/bash
#
# Code sign the EXStreamTV app for distribution
#

set -e

# Configuration
APP_PATH="${1:-build/EXStreamTVApp.app}"
IDENTITY="${SIGNING_IDENTITY:-Developer ID Application: Your Name (TEAM_ID)}"
ENTITLEMENTS="EXStreamTVApp/EXStreamTVApp.entitlements"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Code Signing EXStreamTV${NC}"
echo "App Path: $APP_PATH"
echo "Identity: $IDENTITY"
echo ""

# Check if app exists
if [[ ! -d "$APP_PATH" ]]; then
    echo -e "${RED}Error: App not found at $APP_PATH${NC}"
    exit 1
fi

# Check for signing identity
if [[ "$IDENTITY" == *"Your Name"* ]]; then
    echo -e "${YELLOW}Warning: Using placeholder signing identity${NC}"
    echo "Set SIGNING_IDENTITY environment variable to your Developer ID"
    echo ""
    echo "Available identities:"
    security find-identity -v -p codesigning
    echo ""
    read -p "Enter signing identity or press Enter to skip: " input_identity
    
    if [[ -n "$input_identity" ]]; then
        IDENTITY="$input_identity"
    else
        echo -e "${YELLOW}Skipping code signing${NC}"
        exit 0
    fi
fi

# Sign embedded frameworks and libraries first
echo "Signing embedded frameworks..."
find "$APP_PATH/Contents/Frameworks" -name "*.framework" -exec \
    codesign --force --options runtime --timestamp --sign "$IDENTITY" {} \; 2>/dev/null || true

find "$APP_PATH/Contents/Frameworks" -name "*.dylib" -exec \
    codesign --force --options runtime --timestamp --sign "$IDENTITY" {} \; 2>/dev/null || true

# Sign helper tools
echo "Signing helper tools..."
find "$APP_PATH/Contents/MacOS" -type f -perm +111 ! -name "EXStreamTVApp" -exec \
    codesign --force --options runtime --timestamp --sign "$IDENTITY" {} \; 2>/dev/null || true

# Sign the main app
echo "Signing main application..."
if [[ -f "$ENTITLEMENTS" ]]; then
    codesign --force --deep --options runtime --timestamp \
        --entitlements "$ENTITLEMENTS" \
        --sign "$IDENTITY" \
        "$APP_PATH"
else
    codesign --force --deep --options runtime --timestamp \
        --sign "$IDENTITY" \
        "$APP_PATH"
fi

# Verify signature
echo ""
echo "Verifying signature..."
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✓ Code signing successful!${NC}"
else
    echo -e "${RED}✗ Code signing verification failed${NC}"
    exit 1
fi

# Check entitlements
echo ""
echo "Entitlements:"
codesign -d --entitlements - "$APP_PATH" 2>/dev/null || echo "No entitlements found"

# Spctl assessment (for Developer ID)
echo ""
echo "Gatekeeper assessment..."
spctl --assess --type execute --verbose "$APP_PATH" 2>&1 || true

echo ""
echo -e "${GREEN}Done!${NC}"
