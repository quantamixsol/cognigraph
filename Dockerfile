FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY pyproject.toml README.md LICENSE ./
COPY cognigraph/ cognigraph/

# Install cognigraph with server extras
RUN pip install --no-cache-dir ".[server,api]"

# Default config and graph placeholders
COPY cognigraph.example.yaml /app/cognigraph.yaml

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["kogni", "serve", "--host", "0.0.0.0", "--port", "8000"]
