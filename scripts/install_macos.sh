#!/bin/bash
#
# EXStreamTV macOS Installation Script
# Installs all dependencies and sets up the environment
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PYTHON_MIN_VERSION="3.10"
EXSTREAMTV_PORT="${EXSTREAMTV_PORT:-8411}"

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  EXStreamTV macOS Installer${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Function to check command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to compare version numbers
version_gte() {
    # Returns 0 if $1 >= $2
    printf '%s\n%s\n' "$2" "$1" | sort -V -C
}

# Function to get Python version
get_python_version() {
    "$1" --version 2>&1 | awk '{print $2}'
}

# ============================================================
# Step 1: Check/Install Homebrew
# ============================================================
echo -e "${GREEN}[1/7]${NC} Checking for Homebrew..."

if command_exists brew; then
    echo -e "  ${GREEN}✓${NC} Homebrew is installed"
    brew update &> /dev/null || true
else
    echo -e "  ${YELLOW}⚠${NC} Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    
    echo -e "  ${GREEN}✓${NC} Homebrew installed successfully"
fi

# ============================================================
# Step 2: Check/Install Python
# ============================================================
echo -e "${GREEN}[2/7]${NC} Checking for Python ${PYTHON_MIN_VERSION}+..."

PYTHON_CMD=""

# Check for python3
if command_exists python3; then
    PYTHON_VERSION=$(get_python_version python3)
    if version_gte "$PYTHON_VERSION" "$PYTHON_MIN_VERSION"; then
        PYTHON_CMD="python3"
        echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION found"
    fi
fi

# Install Python if not found or version too old
if [[ -z "$PYTHON_CMD" ]]; then
    echo -e "  ${YELLOW}⚠${NC} Python ${PYTHON_MIN_VERSION}+ not found. Installing via Homebrew..."
    brew install python@3.11
    PYTHON_CMD="python3.11"
    echo -e "  ${GREEN}✓${NC} Python installed successfully"
fi

# ============================================================
# Step 3: Check/Install FFmpeg
# ============================================================
echo -e "${GREEN}[3/7]${NC} Checking for FFmpeg..."

if command_exists ffmpeg; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -n1 | awk '{print $3}')
    echo -e "  ${GREEN}✓${NC} FFmpeg $FFMPEG_VERSION found"
    
    # Check for VideoToolbox support
    if ffmpeg -encoders 2>&1 | grep -q "videotoolbox"; then
        echo -e "  ${GREEN}✓${NC} VideoToolbox hardware acceleration available"
    else
        echo -e "  ${YELLOW}⚠${NC} VideoToolbox not available (software encoding will be used)"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} FFmpeg not found. Installing via Homebrew..."
    brew install ffmpeg
    echo -e "  ${GREEN}✓${NC} FFmpeg installed successfully"
fi

# ============================================================
# Step 4: Create Virtual Environment
# ============================================================
echo -e "${GREEN}[4/7]${NC} Setting up Python virtual environment..."

cd "$PROJECT_DIR"

if [[ -d "venv" ]]; then
    echo -e "  ${YELLOW}⚠${NC} Virtual environment already exists"
    read -p "  Recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        $PYTHON_CMD -m venv venv
        echo -e "  ${GREEN}✓${NC} Virtual environment recreated"
    fi
else
    $PYTHON_CMD -m venv venv
    echo -e "  ${GREEN}✓${NC} Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip &> /dev/null

# ============================================================
# Step 5: Install Python Dependencies
# ============================================================
echo -e "${GREEN}[5/7]${NC} Installing Python dependencies..."

if [[ -f "requirements.txt" ]]; then
    pip install -r requirements.txt
    echo -e "  ${GREEN}✓${NC} Dependencies installed"
else
    echo -e "  ${RED}✗${NC} requirements.txt not found!"
    exit 1
fi

# ============================================================
# Step 6: Initialize Database
# ============================================================
echo -e "${GREEN}[6/7]${NC} Initializing database..."

# Create config if it doesn't exist
if [[ ! -f "config.yaml" ]] && [[ -f "config.example.yaml" ]]; then
    cp config.example.yaml config.yaml
    echo -e "  ${GREEN}✓${NC} Created config.yaml from example"
fi

# Run database migrations
if [[ -f "alembic.ini" ]]; then
    alembic upgrade head 2>/dev/null || python -m exstreamtv.database init 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Database initialized"
else
    echo -e "  ${YELLOW}⚠${NC} Skipping database initialization (alembic.ini not found)"
fi

# ============================================================
# Step 7: Optional - Install Ollama for Local AI
# ============================================================
echo -e "${GREEN}[7/7]${NC} Optional: Local AI Setup..."

read -p "  Install Ollama for local AI? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command_exists ollama; then
        echo -e "  ${GREEN}✓${NC} Ollama already installed"
    else
        echo -e "  Installing Ollama..."
        brew install ollama
        echo -e "  ${GREEN}✓${NC} Ollama installed"
    fi
    
    # Detect RAM for model recommendation
    RAM_GB=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)}')
    
    if [[ $RAM_GB -lt 6 ]]; then
        RECOMMENDED_MODEL="phi4-mini:3.8b-q4"
    elif [[ $RAM_GB -lt 12 ]]; then
        RECOMMENDED_MODEL="granite3.1:2b-instruct"
    elif [[ $RAM_GB -lt 24 ]]; then
        RECOMMENDED_MODEL="qwen2.5:7b"
    else
        RECOMMENDED_MODEL="qwen2.5:14b"
    fi
    
    echo -e "  Your Mac has ${RAM_GB}GB RAM"
    echo -e "  Recommended model: ${RECOMMENDED_MODEL}"
    
    read -p "  Download recommended model now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "  Downloading ${RECOMMENDED_MODEL}..."
        ollama pull "$RECOMMENDED_MODEL"
        echo -e "  ${GREEN}✓${NC} Model downloaded"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} Skipping local AI setup (you can use Cloud AI instead)"
fi

# ============================================================
# Complete
# ============================================================
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "To start EXStreamTV:"
echo -e "  ${BLUE}cd $PROJECT_DIR${NC}"
echo -e "  ${BLUE}source venv/bin/activate${NC}"
echo -e "  ${BLUE}./start.sh${NC}"
echo ""
echo -e "Or use the macOS menu bar app:"
echo -e "  ${BLUE}cd EXStreamTVApp && swift build -c release${NC}"
echo ""
echo -e "Web interface will be available at:"
echo -e "  ${BLUE}http://localhost:${EXSTREAMTV_PORT}${NC}"
echo ""
