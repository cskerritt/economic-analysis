# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
        netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p instance uploads

# Copy application code
COPY . .

# Create health check endpoint
RUN echo 'from flask import Blueprint\nbp = Blueprint("health", __name__)\n\n@bp.route("/health")\ndef health_check():\n    return "healthy", 200' > forensic_econ_app/routes/health.py

# Create startup script
COPY scripts/start.sh /start.sh
RUN chmod +x /start.sh

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Start the application
CMD ["/start.sh"] 