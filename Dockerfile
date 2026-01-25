# HyperMatrix v2026.01 - Multi-stage Dockerfile
# Includes FastAPI backend + React frontend + Ollama integration

# =============================================================================
# Stage 1: Build Frontend
# =============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --only=production=false

# Copy frontend source
COPY frontend/ ./

# Build production bundle
RUN npm run build

# =============================================================================
# Stage 2: Production Runtime
# =============================================================================
FROM python:3.11-slim AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HYPERMATRIX_PORT=26020 \
    HYPERMATRIX_HOST=0.0.0.0 \
    OLLAMA_HOST=ollama:11434 \
    DATA_DIR=/app/data

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user for security
RUN useradd --create-home --shell /bin/bash hypermatrix

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
COPY requirements-embeddings.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir httpx aiofiles

# Install ML dependencies for semantic search (adds ~2GB)
# Using CPU-only torch to keep image smaller
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    torch>=2.0.0 \
    sentence-transformers>=2.2.2 \
    chromadb>=0.4.22

# Copy application code
COPY --chown=hypermatrix:hypermatrix src/ ./src/
COPY --chown=hypermatrix:hypermatrix main.py config.py run_web.py ./
COPY --chown=hypermatrix:hypermatrix docs/ ./docs/
COPY --chown=hypermatrix:hypermatrix tools/ ./tools/
COPY --chown=hypermatrix:hypermatrix utils/ ./utils/
COPY --chown=hypermatrix:hypermatrix config/ ./config/

# Copy built frontend from builder stage
COPY --from=frontend-builder --chown=hypermatrix:hypermatrix /app/frontend/dist ./frontend/dist

# Create data directories and projects mount point
RUN mkdir -p /app/data /app/logs /app/output /app/reports /projects && \
    chown -R hypermatrix:hypermatrix /app /projects

# Copy entrypoint script
COPY --chown=hypermatrix:hypermatrix entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Switch to non-root user
USER hypermatrix

# Expose port
EXPOSE 26020

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:26020/api/health || exit 1

# Entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["python", "-c", "import uvicorn; uvicorn.run('src.web.app:app', host='0.0.0.0', port=26020, timeout_keep_alive=300)"]
