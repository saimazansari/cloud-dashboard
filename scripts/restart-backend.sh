#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Rebuilding and restarting backend..."
docker compose up -d --build backend
echo "==> Done."
