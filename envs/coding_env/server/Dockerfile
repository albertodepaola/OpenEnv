# Dockerfile for Coding Environment
# Build from repo root:
#   docker build -t coding-env:latest -f envs/coding_env/server/Dockerfile .
#
# With screenshot capture support:
#   The image includes Xvfb and ImageMagick for capturing screenshots
#   from UI code (tkinter, matplotlib, pygame, etc.)

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including:
# - git, curl: basic tools
# - python3-tk, tk-dev, tcl-dev: tkinter support for UI
# - xvfb, x11-utils: virtual framebuffer for headless UI
# - imagemagick: screenshot capture
RUN apt-get update && apt-get install -y \
    git \
    curl \
    python3-tk \
    tk-dev \
    tcl-dev \
    xvfb \
    x11-utils \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Copy openenv-core package (root pyproject.toml + src/)
COPY pyproject.toml ./
COPY src/ ./src/

# Copy coding_env package
COPY envs/coding_env/ ./envs/coding_env/

# Install openenv-core first (from root), then coding_env
RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir ./envs/coding_env/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV ENABLE_WEB_INTERFACE=true
ENV DISPLAY=:99

# Copy and install entrypoint script with dynamic package installation support
COPY envs/coding_env/server/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the server with Xvfb and dynamic package installation
# The entrypoint script handles:
# 1. Installing packages from ADDITIONAL_IMPORTS (filtering out stdlib)
# 2. Starting Xvfb virtual display
# 3. Launching uvicorn
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "coding_env.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
