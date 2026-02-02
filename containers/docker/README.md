# EXStreamTV Docker Deployment

Run EXStreamTV in Docker for easy deployment on any platform.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/roto31/EXStreamTV.git
cd EXStreamTV/containers/docker

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys

# Start EXStreamTV
docker-compose up -d

# View logs
docker-compose logs -f
```

Access the web UI at: http://localhost:8411

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TZ` | Timezone | America/New_York |
| `EXSTREAMTV_PORT` | Web UI port | 8411 |
| `GROQ_API_KEY` | Groq Cloud API key (free) | - |
| `PLEX_URL` | Plex server URL | - |
| `PLEX_TOKEN` | Plex authentication token | - |

### Volumes

| Volume | Purpose |
|--------|---------|
| `exstreamtv_data` | Database, channels, configuration |
| `exstreamtv_logs` | Application logs |

### Custom Configuration

Create a `config.yaml` file based on `config.example.yaml`:

```yaml
server:
  port: 8411
  
ai_agent:
  enabled: true
  provider_type: cloud
  cloud:
    provider: groq
```

## Profiles

### Local AI with Ollama

Run EXStreamTV with a local Ollama instance:

```bash
docker-compose --profile ai-local up -d
```

This starts an Ollama container alongside EXStreamTV. Pull your preferred model:

```bash
docker exec exstreamtv_ollama ollama pull qwen2.5:7b
```

### Auto-Updates with Watchtower

Keep EXStreamTV updated automatically:

```bash
docker-compose --profile auto-update up -d
```

## Media Mounting

To access media files, mount your directories in `docker-compose.yml`:

```yaml
volumes:
  - /path/to/movies:/media/movies:ro
  - /path/to/tv:/media/tv:ro
```

## GPU Support (for Local AI)

For NVIDIA GPU acceleration with Ollama, uncomment the GPU section in `docker-compose.yml`:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

## Building from Source

```bash
docker build -t exstreamtv:custom -f Dockerfile ../..
```

## Troubleshooting

### Check container status
```bash
docker-compose ps
```

### View logs
```bash
docker-compose logs exstreamtv
```

### Restart services
```bash
docker-compose restart
```

### Reset everything
```bash
docker-compose down -v  # Warning: removes all data
docker-compose up -d
```

## Network

By default, EXStreamTV creates a bridge network `exstreamtv_network`. To access Plex on the same machine:

```yaml
environment:
  - PLEX_URL=http://host.docker.internal:32400
```

## Ports

| Port | Service |
|------|---------|
| 8411 | Web UI / API |
| 5004 | HDHomeRun discovery (optional) |
| 11434 | Ollama API (if enabled) |
