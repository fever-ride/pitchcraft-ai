COMPOSE := docker compose -f infrastructure/docker/docker-compose.yml

.PHONY: up down restart logs ps build rebuild shell-backend shell-frontend

## Start all services (detached)
up:
	@# Stop any stale local MongoDB that would conflict on port 27017
	@docker stop pitchcraft-mongo-local 2>/dev/null || true
	$(COMPOSE) up -d

## Stop all services
down:
	$(COMPOSE) down

## Restart a single service: make restart s=backend
restart:
	$(COMPOSE) restart $(s)

## Tail logs (all services, or: make logs s=backend)
logs:
	$(COMPOSE) logs -f $(s)

## Show container status
ps:
	$(COMPOSE) ps

## Build images without cache (slow, use after requirements change)
rebuild:
	$(COMPOSE) build --no-cache $(s)

## Build images (incremental, uses cache)
build:
	$(COMPOSE) build $(s)

## Open a shell in the backend container
shell-backend:
	$(COMPOSE) exec backend bash

## Open a shell in the frontend container
shell-frontend:
	$(COMPOSE) exec frontend sh
