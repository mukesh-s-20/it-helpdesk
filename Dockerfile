# ============================================================
# IT Helpdesk Incident Triage — OpenEnv
# Compatible with: Docker, Hugging Face Spaces (Docker SDK)
# ============================================================

FROM python:3.11-slim

# Metadata
LABEL maintainer="openenv-hackathon"
LABEL description="IT Helpdesk Incident Triage OpenEnv"
LABEL version="1.0.0"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (required by Hugging Face Spaces)
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Install Python dependencies first (layer cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port (7860 is required by Hugging Face Spaces)
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:7860/ || exit 1

# Environment defaults
ENV HOST=0.0.0.0
ENV PORT=7860
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Entry point
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
