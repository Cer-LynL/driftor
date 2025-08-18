FROM python:3.11-slim

# Security: Create non-root user
RUN groupadd --gid 1000 driftor && \
    useradd --uid 1000 --gid driftor --shell /bin/bash --create-home driftor

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Poetry
RUN pip install poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/secrets && \
    chown -R driftor:driftor /app

# Switch to non-root user
USER driftor

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "driftor.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]