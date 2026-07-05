# Cloudash — Cloud Cost & Infrastructure Dashboard

A full-stack web application for managing and visualizing Azure infrastructure resources, costs, and VM stop/start actions. Features a modern glassmorphism UI with dark/light theme.

## Architecture

```
Browser → Flask (:5002) → Go API (:8080) ── PostgreSQL (:5432)
                                    │
                                    └── Azure SDK (Resource Graph, Compute)
```

## Quick Start

```bash
# Start everything
make up

# Or manually
docker compose up --build -d
```

Open **http://localhost:5002** and register an account.

## Makefile Reference

| Command | Description |
|---------|-------------|
| `make up` | Start all services |
| `make down` | Stop all services |
| `make rebuild` | Rebuild and start |
| `make logs` | Follow container logs |
| `make restart-backend` | Restart backend container |
| `make deploy` | Deploy infrastructure via Terraform |
| `make plan` | Preview Terraform changes |
| `make destroy` | Destroy all Terraform resources |
| `make run-backend` | Run Go backend locally (dev) |
| `make clean` | Full cleanup (volumes + terraform cache) |

## Project Structure

```
cloud-dashboard/
├── Makefile                   # Common commands
├── docker-compose.yml         # PostgreSQL + Go + Flask
├── .env                       # Azure & OAuth credentials (gitignored)
├── .env.example               # Credential template
├── scripts/                   # Helper scripts
│   ├── deploy.sh              # Terraform deploy
│   └── run-backend.sh         # Local backend dev
├── backend/                   # Go API
│   ├── main.go                # Server, routes, auth, CORS
│   ├── handlers.go            # HTTP handlers
│   ├── azure.go               # Azure SDK integration
│   ├── database.go            # PostgreSQL queries & types
│   └── Dockerfile
├── frontend/                  # Flask UI (single-file app)
│   ├── app.py                 # All routes + inline CSS/HTML/JS
│   ├── requirements.txt
│   └── Dockerfile
└── terraform/                 # Azure IaC (minimal)
    └── main.tf                # 1 VM, 1 KV, 1 storage, VNet, NSG, PIP, NIC, disk
```

## Features

- **Real-time dashboard** with auto-refresh (30s) and skeleton loaders
- **6 stat cards** — total resources, healthy count, monthly cost (USD/INR), cost this month
- **Dark/Light theme** with system preference detection and localStorage persistence
- **Glassmorphism UI** with backdrop blur, gradient accents, and subtle animations
- **Resource table** with sorting, filtering, pagination, and inline copy
- **Cost tracking** with server-side monthly accrued cost calculation
- **Login page** with animated background, password reveal toggle, remember me, and loading spinner
- **VM management** — start/stop individual VMs or batch all
- **Slide panel** — click any resource row for full details

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/register` | No | Create account |
| POST | `/api/login` | No | Login |
| POST | `/api/auth/google` | No | Google OAuth |
| POST | `/api/auth/github` | No | GitHub OAuth |
| GET | `/api/resources` | Yes | List resources |
| GET | `/api/resources/{id}` | Yes | Resource detail |
| POST | `/api/resources/{id}/stop` | Yes | Stop VM |
| POST | `/api/resources/{id}/start` | Yes | Start VM |
| POST | `/api/resources/batch` | Yes | Batch stop/start |
| GET | `/api/cost-summary` | Yes | Cost aggregation |
| GET | `/api/cost-history` | Yes | 30-day cost trend |
| GET | `/api/subscriptions` | Yes | List Azure subscriptions |
| PUT | `/api/user/password` | Yes | Change password |
| GET/PUT | `/api/user/preferences` | Yes | User preferences |

## Terraform

```bash
make deploy    # terraform init + apply
make plan      # terraform plan
make destroy   # terraform destroy
```

All resources are defined in `terraform/main.tf`. Current deployment:
- 1 Virtual Machine (Standard_D2ds_v6, Ubuntu 22.04)
- 1 Key Vault
- 1 Storage Account
- 1 Virtual Network
- 1 Network Security Group
- 1 Public IP
- 1 Network Interface
- 1 Managed Disk

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_SUBSCRIPTION_ID` | For Azure | Azure subscription ID |
| `AZURE_TENANT_ID` | For Azure | Azure AD tenant ID |
| `AZURE_CLIENT_ID` | For Azure | Service principal client ID |
| `AZURE_CLIENT_SECRET` | For Azure | Service principal secret |
| `GOOGLE_CLIENT_ID` | Optional | Google OAuth client ID |
| `GITHUB_CLIENT_ID` | Optional | GitHub OAuth client ID |
| `GITHUB_CLIENT_SECRET` | Optional | GitHub OAuth secret |
| `SECRET_KEY` | Optional | Flask session secret (auto-generated) |
| `BACKEND_URL` | Optional | Backend API URL (default: `http://localhost:8080`) |
