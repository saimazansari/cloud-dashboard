.PHONY: up down rebuild logs restart-backend deploy plan destroy clean

# ─── Docker ────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

rebuild:
	docker compose up --build -d

logs:
	docker compose logs -f

restart-backend:
	docker compose restart backend

# ─── Terraform ─────────────────────────────────────────────
deploy:
	scripts/deploy.sh

plan:
	cd terraform && terraform plan

destroy:
	cd terraform && terraform destroy -auto-approve

# ─── Development ───────────────────────────────────────────
run-backend:
	scripts/run-backend.sh

# ─── Cleanup ───────────────────────────────────────────────
clean:
	docker compose down -v
	rm -rf terraform/.terraform terraform/terraform.tfstate*
