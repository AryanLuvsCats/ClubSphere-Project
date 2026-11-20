FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Startup script runs Alembic migrations, then hands off to Uvicorn.
# Keeping this in the image avoids relying on Render's dockerCommand quoting.
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Create non-root system user and ensure directory ownership
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    mkdir -p /app/uploads && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port for container networking
EXPOSE 8000

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run migrations, then start Uvicorn production server with proxy headers enabled
CMD ["/app/start.sh"]
