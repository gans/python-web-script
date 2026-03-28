#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
until python - <<'EOF'
import psycopg2, os
psycopg2.connect(os.environ["DATABASE_URL"])
EOF
do
  sleep 1
done

echo "Running DB init..."
python - <<'EOF'
import os
from app import app, db, User
with app.app_context():
    db.create_all()
    admin_user = os.environ.get("ADMIN_USER", "admin")
    admin_pass = os.environ.get("ADMIN_PASS", "admin123")
    if not User.query.filter_by(username=admin_user).first():
        u = User(username=admin_user)
        u.set_password(admin_pass)
        db.session.add(u)
        db.session.commit()
        print(f"Created admin user: {admin_user}")
    else:
        print("Admin user already exists.")
EOF

echo "Starting Gunicorn..."
exec gunicorn -c gunicorn.conf.py app:app
