# Cloud Cost & Infrastructure Dashboard

A full-stack web application for managing and visualizing cloud infrastructure resources, costs, and deployments.

## Architecture

```
Browser → Flask Frontend (:5002) → Go API (:8080) → PostgreSQL (:5432)
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Python + Flask (Jinja2, Chart.js) |
| Backend API | Go 1.24 (stdlib `net/http`, pgx) |
| Database | PostgreSQL 16 |
| Containers | Docker Compose |
| Orchestration | Kubernetes (manifests included) |
| Infrastructure | Terraform (AWS) |
| CI/CD | GitHub Actions |

## Quick Start

```bash
docker compose up --build -d
```

Open **http://localhost:5002** and register an account.

## Features

- **User authentication** — Register/login with bcrypt + session tokens
- **Infrastructure inventory** — Add, edit, delete cloud resources (7 types)
- **Cost tracking** — Auto-costed per resource type, hourly/monthly totals, cost breakdown by type
- **Cost trend chart** — 30-day daily cost line chart with auto-seeded history
- **Charts** — Pie chart (cost by type), bar chart (monthly costs), status breakdown
- **Resource tags** — Key:value tagging system with inline display
- **Deployments** — Select resources, trigger simulated async deployment, view history
- **Health monitoring** — Per-resource health status (healthy/degraded/offline) with animated status dots
- **Budget tracker** — Configurable monthly budget with progress bar (green/amber/red) and inline editing
- **Type filter pills** — One-click filtering by resource type
- **Bulk actions** — Multi-select checkboxes for batch stop/terminate/delete
- **Resource detail panel** — Click any row for a slide-out panel with full metadata + deployment history
- **Professional dark theme** — Navy/gunmetal palette with indigo accent (always dark)
- **CSV export** — Download inventory and cost data
- **Search/filter** — Real-time table filtering

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/register` | No | Create account |
| POST | `/api/login` | No | Authenticate |
| GET | `/api/resources` | Yes | List resources |
| POST | `/api/resources` | Yes | Create resource |
| PUT | `/api/resources/{id}` | Yes | Update resource |
| DELETE | `/api/resources/{id}` | Yes | Delete resource |
| GET | `/api/cost-summary` | Yes | Cost aggregation |
| GET | `/api/cost-history` | Yes | 30-day cost trend data |
| GET | `/api/resources/{id}` | Yes | Resource detail with deployment history |
| POST | `/api/resources/batch` | Yes | Bulk stop/terminate/delete |
| POST | `/api/deployments` | Yes | Trigger deployment |
| GET | `/api/deployments` | Yes | List deployments |

## Default Costs Per Hour

| Type | Cost/hr |
|------|---------|
| Virtual Machine | $0.0860 |
| Kubernetes Cluster | $0.1000 |
| Load Balancer | $0.0250 |
| Storage Account | $0.0180 |
| Database | $0.0150 |
| CDN Profile | $0.0100 |
| Serverless Function | $0.0000 |

## Project Structure

```
cloud-dashboard/
├── docker-compose.yml         # PostgreSQL + Go + Flask
├── backend/
│   ├── main.go                # Server setup, routes, CORS, auth middleware
│   ├── database.go            # PostgreSQL schema, queries, cost logic
│   ├── handlers.go            # HTTP request handlers
│   ├── go.mod / go.sum        # Go 1.24 + pgx + bcrypt
│   └── Dockerfile
├── frontend/
│   ├── app.py                 # Flask app (all routes, templates, CSV export)
│   ├── requirements.txt
│   └── Dockerfile
├── kubernetes/                # K8s manifests (namespace, postgres, backend, frontend)
├── terraform/                 # AWS IaC (VPC, RDS, EKS, ECR)
└── .github/workflows/
    ├── ci.yml                 # Build, vet, syntax check
    └── deploy.yml             # Build & push Docker images, deploy to K8s
```

## Deploying to Kubernetes

```bash
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/
```

## Provisioning with Terraform

```bash
cd terraform
terraform init
terraform apply -var="db_username=admin" -var="db_password=supersecret"
```
