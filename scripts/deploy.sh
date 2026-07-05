#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../terraform"

echo "==> Initializing Terraform..."
terraform init

echo ""
echo "==> Applying Terraform..."
terraform apply -auto-approve

echo ""
echo "==> Done! Resources deployed."
