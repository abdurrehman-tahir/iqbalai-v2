-- IqbalAI dual-schema initialization
-- Runs once on first Postgres container start

-- Authentik IdP (separate database; see docker-compose authentik-server)
CREATE DATABASE authentik OWNER iqbalai;

CREATE SCHEMA IF NOT EXISTS school;
CREATE SCHEMA IF NOT EXISTS independent;

-- Grant the app user access to both schemas
GRANT ALL PRIVILEGES ON SCHEMA school TO iqbalai;
GRANT ALL PRIVILEGES ON SCHEMA independent TO iqbalai;

-- Set default search path
ALTER ROLE iqbalai SET search_path TO school, independent, public;
