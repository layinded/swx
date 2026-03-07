#!/usr/bin/env bash

set -e  # Exit on error
set -x  # Print commands before execution

echo "Waiting for database to start..."

# Run database setup (includes check_db_ready, alembic upgrade head, superuser, seed)
python swx_core/database/db_setup.py

echo "Database setup complete!"
