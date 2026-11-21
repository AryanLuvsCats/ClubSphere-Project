#!/bin/sh
set -e

echo "==> Running database migrations"
if alembic upgrade head; then
    echo "==> Migrations applied successfully"
else
    echo "==> WARNING: Database migrations failed or database is not reachable yet. Proceeding with application startup..."
fi

echo "==> Starting Uvicorn"
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips=*
