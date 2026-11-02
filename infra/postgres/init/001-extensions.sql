-- Habilita PostGIS no banco local criado pelo container.
-- A migração inicial do Alembic permanece vazia; extensões são infraestrutura.
CREATE EXTENSION IF NOT EXISTS postgis;
