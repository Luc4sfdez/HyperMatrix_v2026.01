#!/bin/bash
# HyperMatrix v2026.01 - Entrypoint Script

set -e

echo "=============================================="
echo "  HyperMatrix v2026.01"
echo "  AI-Powered Code Analysis Dashboard"
echo "=============================================="

# Create data directories if they don't exist
mkdir -p /app/data /app/logs /app/output /app/reports /app/data/workspace

# Create /projects directory if possible (may fail without root)
mkdir -p /projects 2>/dev/null || echo "[HyperMatrix] Note: /projects not created (no root permission)"

# Initialize database if it doesn't exist
if [ ! -f /app/data/hypermatrix.db ]; then
    echo "[HyperMatrix] Initializing database..."
    touch /app/data/hypermatrix.db
fi

# Wait for Ollama to be available (if configured)
if [ -n "$OLLAMA_HOST" ]; then
    echo "[HyperMatrix] Waiting for Ollama at $OLLAMA_HOST..."
    max_retries=30
    retry_count=0
    while ! curl -s "http://$OLLAMA_HOST/api/tags" > /dev/null 2>&1; do
        retry_count=$((retry_count + 1))
        if [ $retry_count -ge $max_retries ]; then
            echo "[HyperMatrix] Warning: Ollama not available, AI features will be disabled"
            break
        fi
        echo "[HyperMatrix] Ollama not ready, retrying in 2s... ($retry_count/$max_retries)"
        sleep 2
    done
    if [ $retry_count -lt $max_retries ]; then
        echo "[HyperMatrix] Ollama connected successfully!"
    fi
fi

# Display configuration
echo ""
echo "[HyperMatrix] Configuration:"
echo "  - Host: ${HYPERMATRIX_HOST:-0.0.0.0}"
echo "  - Port: ${HYPERMATRIX_PORT:-26020}"
echo "  - Data Dir: ${DATA_DIR:-/app/data}"
echo "  - Ollama: ${OLLAMA_HOST:-disabled}"
echo "  - Model: ${OLLAMA_MODEL:-qwen2:7b}"
echo ""

# Execute the main command
echo "[HyperMatrix] Starting server..."
exec "$@"
