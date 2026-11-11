# Digital Hub: everyday commands. Run `make` to list them.
#
# Local targets use compose.yaml; `prod-*` targets run on the server and use
# deploy/compose.production.yaml (see docs/deploy.md).

COMPOSE      := docker compose
PROD_COMPOSE := docker compose --file deploy/compose.production.yaml
MANAGE       := $(COMPOSE) exec web python manage.py
PROD_MANAGE  := $(PROD_COMPOSE) exec web python manage.py

.DEFAULT_GOAL := help
.PHONY: help env up start down stop restart build rebuild ps logs shell dbshell manage migrate \
        migrations adopt-migrations superuser test check lint ci sync-catalog eval-ai ask-ai lock clean \
        prod-deploy prod-rollback prod-restart prod-ps prod-logs prod-shell prod-manage prod-adopt-migrations prod-sync-catalog

help: ## List the commands
	@awk 'BEGIN {FS = ":.*##"} /^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5)} \
	  /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo
	@echo "  Arguments: make manage cmd=\"showmigrations AI\"   make ask-ai q=\"What is GDP growth?\""
	@echo "             make logs s=worker                      make test app=ai"

##@ Local development

env: ## Create .env from .env.example (keeps an existing .env)
	@if [ -f .env ]; then echo ".env already exists"; else cp .env.example .env && echo "Created .env: set DEBUG=True and fill in the keys"; fi

up: env ## Build and start the stack in the background (http://localhost:8000)
	$(COMPOSE) up --build --detach
	@echo "Running on http://localhost:8000  (make logs to follow)"

start: env ## Start the stack in the foreground, with logs
	$(COMPOSE) up --build

down: ## Stop and remove the containers (the database is kept)
	$(COMPOSE) down

stop: ## Stop the containers without removing them
	$(COMPOSE) stop

restart: ## Restart web, worker and beat (e.g. after editing .env)
	$(COMPOSE) up --detach --force-recreate web worker beat

build: ## Build the image
	$(COMPOSE) build

rebuild: ## Build the image from scratch, without cache
	$(COMPOSE) build --no-cache

ps: ## Show container status
	$(COMPOSE) ps

logs: ## Follow logs (s=web|worker|beat|db|redis, default the three app services)
	$(COMPOSE) logs --follow --tail 100 $(or $(s),web worker beat)

shell: ## Django shell in the web container
	$(MANAGE) shell

dbshell: ## psql in the database container
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" "$$POSTGRES_DB"'

manage: ## Any manage.py command: make manage cmd="..."
	$(MANAGE) $(cmd)

migrate: ## Apply migrations
	$(MANAGE) migrate

migrations: ## Create migrations for model changes (review and commit them)
	$(MANAGE) makemigrations

adopt-migrations: ## One-time: move an old database to the committed migrations (apply=1 to change)
	$(MANAGE) adopt_migrations $(if $(apply),--apply)

superuser: ## Create an admin user
	$(MANAGE) createsuperuser

test: ## Run the tests (app=ai to run one app)
	$(MANAGE) test $(app)

check: ## Django checks plus a check for missing migrations
	$(MANAGE) check
	$(MANAGE) makemigrations --check --dry-run

lint: ## Lint the code with ruff (fix=1 applies the safe fixes)
	docker run --rm -v "$(CURDIR)":/src -w /src ghcr.io/astral-sh/ruff:0.8.4 check core $(if $(fix),--fix)

ci: lint check test ## Everything CI runs: lint, checks, tests

##@ AI

sync-catalog: ## Build or refresh the AI catalog (needed once before data questions)
	$(MANAGE) sync_ai_catalog

eval-ai: ## Score planning on the evaluation questions (full=1 to also answer them)
	$(MANAGE) eval_ai $(if $(full),--full)

ask-ai: ## Ask one question and show its trace: make ask-ai q="..."
	@test -n "$(q)" || { echo 'Usage: make ask-ai q="What is GDP growth?"'; exit 1; }
	$(MANAGE) ask_ai "$(q)"

##@ Maintenance

lock: ## Regenerate poetry.lock after editing pyproject.toml, then rebuild
	docker run --rm -v "$(CURDIR)/pyproject.toml:/src/pyproject.toml" -v "$(CURDIR)/poetry.lock:/src/poetry.lock" \
	  -w /src python:3.12-slim sh -c "pip install -q --root-user-action=ignore poetry==2.3.2 && poetry lock"
	$(COMPOSE) build

clean: ## Remove containers AND the local database volume (asks first)
	@printf "This deletes the local Docker database. Continue? [y/N] " && read answer && [ "$$answer" = y ]
	$(COMPOSE) down --volumes --remove-orphans

##@ Production (run on the server, see docs/deploy.md)

prod-deploy: ## Pull origin/production, build, migrate, restart
	bash deploy/deploy.sh

prod-rollback: ## Go back to the previous image
	bash deploy/deploy.sh --rollback

prod-restart: ## Restart production containers (e.g. after editing .env)
	$(PROD_COMPOSE) restart

prod-ps: ## Show production container status
	$(PROD_COMPOSE) ps

prod-logs: ## Follow production logs (s=web|worker|beat)
	$(PROD_COMPOSE) logs --follow --tail 100 $(or $(s),web worker beat)

prod-shell: ## Django shell in production
	$(PROD_MANAGE) shell

prod-manage: ## Any manage.py command in production: make prod-manage cmd="..."
	$(PROD_MANAGE) $(cmd)

prod-adopt-migrations: ## One-time, after a backup: adopt committed migrations (apply=1 to change)
	$(PROD_COMPOSE) run --rm --no-deps web python manage.py adopt_migrations $(if $(apply),--apply)

prod-sync-catalog: ## Refresh the AI catalog in production
	$(PROD_COMPOSE) run --rm --no-deps web python manage.py sync_ai_catalog
