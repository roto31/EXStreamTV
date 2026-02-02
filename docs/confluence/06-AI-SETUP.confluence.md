{info:title=AI Setup Guide}
Version 2.6.0 | Last Updated: 2026-01-31
{info}

h1. AI Setup Guide

EXStreamTV uses AI to help create channels, troubleshoot issues, and analyze logs. This guide covers configuring AI providers for your installation.

----

h2. Table of Contents

* [Overview|#overview]
* [Provider Options|#provider-options]
* [Cloud AI Setup|#cloud-ai-setup]
* [Local AI Setup|#local-ai-setup]
* [Hybrid Mode|#hybrid-mode]
* [AI Self-Healing System|#ai-self-healing-system]
* [Database Backup|#database-backup]
* [Troubleshooting|#troubleshooting]

----

h2. Overview

EXStreamTV supports three AI provider modes:

||Mode||Description||Best For||
|*Cloud*|Uses cloud AI services (Groq, SambaNova, OpenRouter)|Most users - fast setup, no local resources needed|
|*Local*|Runs AI models on your Mac via Ollama|Privacy-focused users, offline usage|
|*Hybrid*|Cloud primary with local fallback|Best reliability - works offline when cloud unavailable|

{tip}All cloud providers offer *free tiers* - no credit card required.{tip}

----

h2. Provider Options

h3. Cloud Providers Comparison

||Provider||Free Tier||Speed||Models||Signup Time||
|*Groq*|14,400 req/day, 30 req/min|Ultra-fast|Llama 3.3 70B, Mixtral|30 seconds|
|*SambaNova*|1M tokens/day|Fast|Llama 3.3 70B, DeepSeek|1 minute|
|*OpenRouter*|$5 credit|Varies|100+ models|2 minutes|

h3. Local Models by RAM

||RAM||Recommended Model||Size||Capabilities||
|4GB|phi4-mini:3.8b-q4|2.5GB|Basic channel creation, troubleshooting|
|6-8GB|granite3.1:2b-instruct|2GB|Full troubleshooting, tool calling|
|8-16GB|qwen2.5:7b|4.4GB|All features, excellent JSON output|
|16GB+|qwen2.5:14b|9GB|Best quality, all 6 channel personas|
|32GB+|qwen2.5-coder:32b|18GB|Power users, complex schedules|

----

h2. Cloud AI Setup

h3. Groq (Recommended)

Groq offers the fastest inference and a generous free tier.

h4. Step 1: Get Your API Key

# Go to [console.groq.com|https://console.groq.com/keys]
# Sign in with Google or GitHub (takes 10 seconds)
# Click *Create API Key*
# Copy your API key (starts with {{gsk_}})

h4. Step 2: Configure EXStreamTV

*Option A: Environment Variable*

{code:language=bash}
export GROQ_API_KEY="gsk_your_key_here"
{code}

Add to your shell profile ({{~/.zshrc}} or {{~/.bashrc}}) for persistence.

*Option B: Configuration File*

Edit {{config.yaml}}:

{code:language=yaml}
ai_agent:
  enabled: true
  provider_type: "cloud"
  cloud:
    provider: "groq"
    api_key: "gsk_your_key_here"
    model: "llama-3.3-70b-versatile"
{code}

*Option C: macOS App Settings*

# Open EXStreamTV menu bar app
# Go to *Settings* > *AI* tab
# Select *Cloud AI*
# Choose *Groq*
# Paste your API key
# Click *Validate & Save*

h4. Groq Free Tier Limits

* 30 requests per minute
* 14,400 requests per day
* 6,000 tokens per minute
* No credit card required

----

h2. Local AI Setup

Local AI runs entirely on your Mac using Ollama. No internet required after setup.

h3. Installing Ollama

*Option 1: Homebrew (Recommended)*

{code:language=bash}
brew install ollama
{code}

*Option 2: Direct Download*

# Go to [ollama.com/download|https://ollama.com/download]
# Download and install the macOS app

h3. Starting Ollama

{code:language=bash}
# Start Ollama service
ollama serve
{code}

h3. Downloading Models

{code:language=bash}
# Download recommended model for 8GB RAM
ollama pull qwen2.5:7b

# Verify installation
ollama list
{code}

h3. Configure for Local AI

{code:language=yaml}
ai_agent:
  enabled: true
  provider_type: "local"
  local:
    host: "http://localhost:11434"
    model: "qwen2.5:7b"  # or "auto" for automatic selection
{code}

----

h2. Hybrid Mode

Hybrid mode uses cloud AI when available and falls back to local when offline.

h3. Configuration

{code:language=yaml}
ai_agent:
  provider_type: "hybrid"
  
  cloud:
    provider: "groq"
    api_key: "${GROQ_API_KEY}"
    model: "llama-3.3-70b-versatile"
    
    # Optional fallback providers
    fallback:
      - provider: "sambanova"
        api_key: "${SAMBANOVA_API_KEY}"
        model: "Meta-Llama-3.3-70B-Instruct"
  
  local:
    host: "http://localhost:11434"
    model: "auto"
{code}

h3. How Hybrid Mode Works

# Attempts cloud provider first (Groq)
# If cloud fails, tries fallback cloud providers in order
# If all cloud providers fail, uses local Ollama
# Returns error only if all providers fail

----

h2. AI Self-Healing System

{panel:title=NEW in v2.6.0|borderStyle=solid|borderColor=#9C27B0}
EXStreamTV v2.6.0 introduces an AI-powered self-healing system that autonomously detects and resolves streaming issues.
{panel}

h3. Overview

{mermaid}
flowchart TB
    subgraph Detection[Detection]
        Logs[Application Logs]
        FFmpeg[FFmpeg Stderr]
    end
    
    subgraph Analysis[Analysis]
        Collector[UnifiedLogCollector]
        Monitor[FFmpegAIMonitor]
        Detector[PatternDetector]
    end
    
    subgraph Resolution[Resolution]
        Resolver[AutoResolver]
        ErrorScreen[ErrorScreenGenerator]
    end
    
    Logs --> Collector
    FFmpeg --> Monitor
    Collector --> Detector
    Monitor --> Detector
    Detector --> Resolver
    Resolver --> ErrorScreen
{mermaid}

h3. Configuration

{code:language=yaml|title=config.yaml}
ai_auto_heal:
  enabled: true
  
  # Log collection
  log_buffer_minutes: 30
  realtime_streaming: true
  
  # FFmpeg monitoring
  ffmpeg_monitor_enabled: true
  ffmpeg_health_threshold: 0.8  # Speed threshold for healthy
  
  # Pattern detection
  pattern_detection_enabled: true
  prediction_confidence_threshold: 0.75
  
  # Auto resolution
  auto_resolve_enabled: true
  max_auto_fixes_per_hour: 50
  require_approval_above_risk: "MEDIUM"  # SAFE, LOW, MEDIUM, HIGH
  
  # Zero-downtime features
  use_error_screen_fallback: true
  hot_swap_enabled: true
  
  # Learning
  learning_enabled: true
{code}

h3. Components

h4. 1. Unified Log Collector

Aggregates logs from all sources in real-time:
* Application logs
* FFmpeg stderr
* Plex/Jellyfin events
* System logs

{code:language=python}
from exstreamtv.ai_agent.unified_log_collector import get_log_collector

collector = get_log_collector()

# Get recent errors
errors = collector.get_recent_errors(minutes=60)

# Get context window for a channel
context = collector.get_context_window(channel_id=1, minutes=5)
{code}

h4. 2. FFmpeg AI Monitor

Monitors FFmpeg processes for issues:

||Metric||Description||Healthy Range||
|FPS|Frames per second|25-30|
|Speed|Encoding speed|0.95-1.1x|
|Bitrate|Output bitrate|Target ±20%|
|Dropped Frames|Frame drops|< 10/minute|

h4. 3. Pattern Detector

Detects known problematic patterns:

||Pattern||Indicators||Risk Level||
|DB Pool Exhaustion|pool exhausted, connection timeout|HIGH|
|FFmpeg Degradation|speed < 1.0x, dropping frames|MEDIUM|
|URL Expiration|403 forbidden, token expired|MEDIUM|
|Network Instability|connection reset, timeout|HIGH|
|Memory Pressure|out of memory|CRITICAL|

h4. 4. Auto Resolver

Automatically resolves detected issues:

||Issue Type||Strategy||Downtime||
|FFmpeg Hang|Restart|~2 sec|
|URL Expired|Refresh|0 sec|
|DB Pool Exhausted|Expand|0 sec|
|Source Unavailable|Fallback|0 sec|

h3. Error Screen Fallback

During issue resolution, clients receive an error screen instead of a broken stream:

{code:language=yaml}
ai_auto_heal:
  use_error_screen_fallback: true
{code}

h3. Monitoring AI Health

{code:language=bash}
# Via API
curl http://localhost:8411/api/ai/health

# Via WebUI
# Navigate to Settings > AI > Health Status
{code}

h3. Risk Levels

Configure which fixes require approval:

||Risk Level||Example Fixes||Default Behavior||
|SAFE|Refresh URL, Switch fallback|Auto-apply|
|LOW|Expand pool, Restart channel|Auto-apply|
|MEDIUM|Reduce load, Kill process|Requires approval|
|HIGH|Full restart, Database restore|Requires approval|

----

h2. Database Backup

{panel:title=NEW in v2.6.0|borderStyle=solid|borderColor=#4CAF50}
EXStreamTV now includes automatic database backup.
{panel}

h3. Configuration

{code:language=yaml}
database_backup:
  enabled: true
  backup_directory: "backups"
  interval_hours: 24      # Backup every 24 hours
  keep_count: 7           # Keep 7 most recent
  keep_days: 30           # Delete older than 30 days
  compress: true          # Gzip compression
{code}

h3. Manual Backup

{code:language=bash}
# Via API
curl -X POST http://localhost:8411/api/database/backup

# Via WebUI
# Navigate to Settings > Database > Create Backup
{code}

h3. Restore Backup

{code:language=bash}
curl -X POST http://localhost:8411/api/database/restore \
  -H "Content-Type: application/json" \
  -d '{"backup_path": "backups/exstreamtv_backup_20260131.db.gz"}'
{code}

----

h2. Troubleshooting

h3. Cloud AI Issues

*"Invalid API key" Error*
* Verify the key is correct (no extra spaces)
* Check the key hasn't expired
* Ensure you're using the right provider's key

*"Rate limit exceeded"*
* Wait a few minutes and try again
* Consider adding fallback providers
* Switch to a different cloud provider

*"Connection refused"*
* Check your internet connection
* Verify the provider's service status
* Try a different provider

h3. Local AI Issues

*"Ollama not found"*

{code:language=bash}
# Check if Ollama is installed
which ollama

# Install if missing
brew install ollama
{code}

*"Model not found"*

{code:language=bash}
# List installed models
ollama list

# Pull the required model
ollama pull qwen2.5:7b
{code}

*"Connection refused to localhost:11434"*

{code:language=bash}
# Start Ollama service
ollama serve

# Or check if already running
pgrep -f ollama
{code}

*Slow performance with local AI*
* Choose a smaller model appropriate for your RAM
* Close other memory-intensive applications
* Consider using cloud AI for better performance

h3. General Issues

*AI features not working*
# Check that {{ai_agent.enabled: true}} in config.yaml
# Verify at least one provider is configured
# Check the logs: *Settings* > *Logs*

*"AI configuration incomplete"*
* Ensure you've entered an API key (cloud) or installed a model (local)
* Run the onboarding wizard again from Settings

----

h2. Related Documentation

* [Quick Start Guide|EXStreamTV:Quick Start] - Create your first channel
* [Onboarding Guide|EXStreamTV:Onboarding] - Complete setup wizard
* [macOS App Guide|EXStreamTV:macOS App] - Use the menu bar app
* [Tunarr/dizqueTV Integration|EXStreamTV:Tunarr Integration] - v2.6.0 technical details
