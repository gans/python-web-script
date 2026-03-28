#!/bin/bash
set -e

BACKEND="${DB_BACKEND:-postgres}"

if [ "$BACKEND" = "postgres" ]; then
  echo "Waiting for PostgreSQL..."
  until python - <<'EOF'
import psycopg2, os
psycopg2.connect(os.environ["DATABASE_URL"])
EOF
  do
    sleep 1
  done
  echo "PostgreSQL is ready."
else
  echo "Filesystem backend — skipping PostgreSQL wait."
fi

echo "Starting Gunicorn..."
exec gunicorn -c gunicorn.conf.py app:app
