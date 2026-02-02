#!/bin/bash
#
# Notarize the EXStreamTV app for distribution
#

set -e

# Configuration
INPUT_PATH="${1:-dist/EXStreamTV-Installer.dmg}"
APPLE_ID="${APPLE_ID:-}"
TEAM_ID="${TEAM_ID:-}"
APP_PASSWORD="${APP_PASSWORD:-}"  # App-specific password from appleid.apple.com

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Notarizing EXStreamTV${NC}"
echo "File: $INPUT_PATH"
echo ""

# Check if file exists
if [[ ! -f "$INPUT_PATH" ]] && [[ ! -d "$INPUT_PATH" ]]; then
    echo -e "${RED}Error: File not found at $INPUT_PATH${NC}"
    exit 1
fi

# Check credentials
if [[ -z "$APPLE_ID" ]] || [[ -z "$TEAM_ID" ]] || [[ -z "$APP_PASSWORD" ]]; then
    echo -e "${YELLOW}Missing credentials. Please set:${NC}"
    echo "  APPLE_ID - Your Apple ID email"
    echo "  TEAM_ID - Your Team ID (from developer.apple.com)"
    echo "  APP_PASSWORD - App-specific password (from appleid.apple.com)"
    echo ""
    
    read -p "Apple ID: " APPLE_ID
    read -p "Team ID: " TEAM_ID
    read -sp "App-Specific Password: " APP_PASSWORD
    echo ""
fi

# Store credentials in keychain for future use
echo "Storing credentials in keychain..."
xcrun notarytool store-credentials "EXStreamTV-Notarization" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_PASSWORD" 2>/dev/null || true

# Submit for notarization
echo ""
echo "Submitting for notarization..."
echo "This may take several minutes..."

SUBMIT_OUTPUT=$(xcrun notarytool submit "$INPUT_PATH" \
    --keychain-profile "EXStreamTV-Notarization" \
    --wait 2>&1)

echo "$SUBMIT_OUTPUT"

# Extract submission ID
SUBMISSION_ID=$(echo "$SUBMIT_OUTPUT" | grep "id:" | head -1 | awk '{print $2}')

if [[ -z "$SUBMISSION_ID" ]]; then
    echo -e "${RED}Failed to get submission ID${NC}"
    exit 1
fi

echo ""
echo "Submission ID: $SUBMISSION_ID"

# Get detailed log
echo ""
echo "Fetching notarization log..."
xcrun notarytool log "$SUBMISSION_ID" \
    --keychain-profile "EXStreamTV-Notarization" \
    notarization_log.json 2>/dev/null || true

if [[ -f "notarization_log.json" ]]; then
    echo "Log saved to notarization_log.json"
    
    # Check for issues
    if grep -q '"issues"' notarization_log.json; then
        echo -e "${YELLOW}Issues found in notarization log:${NC}"
        cat notarization_log.json | python3 -c "import sys,json; log=json.load(sys.stdin); [print(f'  - {i}') for i in log.get('issues', [])]"
    fi
fi

# Check result
if echo "$SUBMIT_OUTPUT" | grep -q "status: Accepted"; then
    echo -e "${GREEN}✓ Notarization successful!${NC}"
    
    # Staple the ticket
    echo ""
    echo "Stapling notarization ticket..."
    
    if [[ "$INPUT_PATH" == *.dmg ]]; then
        xcrun stapler staple "$INPUT_PATH"
    elif [[ "$INPUT_PATH" == *.pkg ]]; then
        xcrun stapler staple "$INPUT_PATH"
    elif [[ -d "$INPUT_PATH" ]]; then
        xcrun stapler staple "$INPUT_PATH"
    fi
    
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ Ticket stapled successfully!${NC}"
    else
        echo -e "${YELLOW}⚠ Stapling failed (ticket still valid for download)${NC}"
    fi
    
    # Verify stapling
    echo ""
    echo "Verifying stapled ticket..."
    xcrun stapler validate "$INPUT_PATH"
    
else
    echo -e "${RED}✗ Notarization failed${NC}"
    echo ""
    echo "Check notarization_log.json for details"
    exit 1
fi

echo ""
echo -e "${GREEN}Done! Your app is ready for distribution.${NC}"
