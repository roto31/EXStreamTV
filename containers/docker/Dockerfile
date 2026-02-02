#
# EXStreamTV Docker Image
#
# Multi-stage build for optimized image size
#

# ============================================
# Stage 1: Build stage
# ============================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================
# Stage 2: Runtime stage
# ============================================
FROM python:3.11-slim

LABEL maintainer="EXStreamTV"
LABEL description="EXStreamTV - Personal TV Streaming Server"
LABEL version="1.4.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    EXSTREAMTV_HOST=0.0.0.0 \
    EXSTREAMTV_PORT=8411 \
    EXSTREAMTV_DATA_DIR=/data \
    EXSTREAMTV_LOG_DIR=/logs

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r exstreamtv && useradd -r -g exstreamtv exstreamtv

# Create application directories
RUN mkdir -p /app /data /logs && \
    chown -R exstreamtv:exstreamtv /app /data /logs

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=exstreamtv:exstreamtv exstreamtv/ ./exstreamtv/
COPY --chown=exstreamtv:exstreamtv templates/ ./templates/
COPY --chown=exstreamtv:exstreamtv static/ ./static/
COPY --chown=exstreamtv:exstreamtv config.example.yaml ./config.example.yaml
COPY --chown=exstreamtv:exstreamtv start.sh ./start.sh

# Make start script executable
RUN chmod +x start.sh

# Switch to non-root user
USER exstreamtv

# Expose port
EXPOSE 8411

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8411/health || exit 1

# Volumes for persistent data
VOLUME ["/data", "/logs"]

# Default command
CMD ["./start.sh"]
