#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

echo "==> Starting backend locally on :8080..."
echo "    Make sure PostgreSQL is running (docker compose up -d postgres)"
echo ""

PORT="${PORT:-8080}" \
DATABASE_URL="${DATABASE_URL:-postgres://postgres:postgres@localhost:5432/clouddashboard?sslmode=disable}" \
go run .
