#!/bin/bash
set -e

# Wait for PostgreSQL
until nc -z -v -w30 db 5432
do
  echo "Waiting for PostgreSQL database..."
  sleep 1
done
echo "PostgreSQL database is up!"

# Wait for Redis
until nc -z -v -w30 redis 6379
do
  echo "Waiting for Redis..."
  sleep 1
done
echo "Redis is up!"

# Run database migrations
flask db upgrade

# Start Gunicorn
exec gunicorn --bind 0.0.0.0:5000 \
    --workers 4 \
    --threads 2 \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    "forensic_econ_app:create_app()" 