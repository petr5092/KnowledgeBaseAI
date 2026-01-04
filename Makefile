ENV_FILE ?= .env.prod

.PHONY: up-prod
up-prod:
	docker compose --env-file $(ENV_FILE) up -d traefik fastapi frontend

.PHONY: up-dev
up-dev:
	docker compose --env-file .env.dev --profile dev up -d traefik fastapi-dev frontend-dev frontend-prod-hot

.PHONY: restart-backend
restart-backend:
	docker restart knowledgebase-fastapi-1

.PHONY: restart-frontend
restart-frontend:
	docker compose --env-file $(ENV_FILE) build frontend && docker compose --env-file $(ENV_FILE) up -d frontend

.PHONY: logs
logs:
	docker logs knowledgebase-traefik-1 --tail 200 || true
	docker logs knowledgebase-fastapi-1 --tail 200 || true
	docker logs knowledgebase-frontend-1 --tail 200 || true
