#!/bin/sh
set -e

# Run Alembic migrations if a database URL is configured
if [ -n "$COGNIFY_DATABASE_URL" ]; then
  echo "Running database migrations..."
  python -m alembic upgrade head
  echo "Migrations complete."
fi

# Start uvicorn — exec replaces the shell for proper signal handling
exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000 "$@"
