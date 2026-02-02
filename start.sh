#!/bin/bash
#
# EXStreamTV Start Script
# Starts the EXStreamTV server on port 8411
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT=8411

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  EXStreamTV Server${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check if server is already running
if lsof -ti:$PORT > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠  Server already running on port $PORT${NC}"
    echo -e "   Use ${YELLOW}./restart.sh${NC} to restart the server"
    exit 1
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
    else
        echo -e "${YELLOW}⚠  No config file found, using defaults${NC}"
    fi
fi

echo -e "${GREEN}▶  Starting EXStreamTV on port $PORT...${NC}"
echo ""

# Start the server
python3 -m exstreamtv

