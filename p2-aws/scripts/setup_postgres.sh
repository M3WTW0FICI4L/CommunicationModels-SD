#!/bin/bash
# Run this script ON the PostgreSQL EC2 after launch (via SSH or SSM).
# Handles the DB/schema creation that's awkward in CDK user_data.

set -e

echo "=== Setting up PostgreSQL ==="

# Wait for PostgreSQL to be ready
until sudo -u postgres psql -c '\l' > /dev/null 2>&1; do
  echo "Waiting for PostgreSQL..."
  sleep 3
done

# Create user and database
sudo -u postgres psql <<'EOF'
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ticket_user') THEN
    CREATE USER ticket_user WITH PASSWORD 'ticket_pass';
  END IF;
END$$;
EOF

sudo -u postgres psql -c "CREATE DATABASE tickets OWNER ticket_user;" 2>/dev/null || true

# Create schema
sudo -u postgres psql -d tickets <<'EOF'
CREATE TABLE IF NOT EXISTS tickets (
  id           SERIAL PRIMARY KEY,
  request_id   VARCHAR(64) UNIQUE NOT NULL,
  ticket_type  VARCHAR(16) NOT NULL,
  seat_number  INTEGER,
  status       VARCHAR(16) NOT NULL DEFAULT 'pending',
  processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Partial unique index: each seat can be sold exactly once
CREATE UNIQUE INDEX IF NOT EXISTS idx_seat_unique
  ON tickets(seat_number)
  WHERE ticket_type = 'numbered' AND status = 'success';

CREATE INDEX IF NOT EXISTS idx_processed_at ON tickets(processed_at);

CREATE TABLE IF NOT EXISTS ticket_counter (
  id   INTEGER PRIMARY KEY DEFAULT 1,
  sold INTEGER NOT NULL DEFAULT 0
);

INSERT INTO ticket_counter(id, sold) VALUES(1, 0) ON CONFLICT DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ticket_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ticket_user;
EOF

# Allow remote connections (edit postgresql.conf and pg_hba.conf)
PG_CONF=$(sudo -u postgres psql -t -c "SHOW config_file;" | tr -d ' ')
PG_HBA=$(sudo -u postgres psql -t -c "SHOW hba_file;" | tr -d ' ')

sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" "$PG_CONF"
grep -q "0.0.0.0/0" "$PG_HBA" || echo "host all all 0.0.0.0/0 md5" | sudo tee -a "$PG_HBA"

sudo systemctl restart postgresql
echo "=== PostgreSQL setup complete ==="
