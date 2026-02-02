#!/bin/bash
#
# EXStreamTV Stop Script
# Stops the running EXStreamTV server
#

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PORT=8411

echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}  EXStreamTV Server Stop${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check for existing server
if lsof -ti:$PORT > /dev/null 2>&1; then
    echo -e "${YELLOW}■  Stopping server on port $PORT...${NC}"
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 1
    
    # Verify it stopped
    if lsof -ti:$PORT > /dev/null 2>&1; then
        echo -e "${RED}✗  Failed to stop server${NC}"
        exit 1
    else
        echo -e "${GREEN}✓  Server stopped successfully${NC}"
    fi
else
    echo -e "${YELLOW}○  No server running on port $PORT${NC}"
fi

