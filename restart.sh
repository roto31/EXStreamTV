#!/bin/bash
#
# EXStreamTV Restart Script
# Stops any running server and starts a fresh instance
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT=8411

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  EXStreamTV Server Restart${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check for existing server
if lsof -ti:$PORT > /dev/null 2>&1; then
    echo -e "${YELLOW}■  Stopping existing server on port $PORT...${NC}"
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 2
    echo -e "${GREEN}✓  Server stopped${NC}"
else
    echo -e "${YELLOW}○  No server running on port $PORT${NC}"
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗  Python 3 not found${NC}"
    exit 1
fi

# Check for config file
if [ ! -f "config.yaml" ]; then
    if [ -f "config.example.yaml" ]; then
        echo -e "${YELLOW}⚠  config.yaml not found, copying from config.example.yaml${NC}"
        cp config.example.yaml config.yaml
    fi
fi

echo -e "${GREEN}▶  Starting EXStreamTV on port $PORT...${NC}"
echo ""

# Start the server
python3 -m exstreamtv

