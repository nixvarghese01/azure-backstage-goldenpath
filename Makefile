# Run inside Ubuntu (WSL2) from the repo root: `wsl -d Ubuntu-26.04`, then
# `cd /mnt/e/Github/azure-backstage-goldenpath`. From Windows use scripts/local/platform.ps1 instead.
# Needs Docker Engine in Ubuntu; every check runs in a throwaway container, caches kept in volumes.

.PHONY: help up down restart status logs reset images e2e test test-integration portal-test check

UV_IMAGE   := ghcr.io/astral-sh/uv:0.13.0-python3.14-trixie-slim
NODE_IMAGE := node:24-trixie-slim
NETWORK    := sportify-platform_platform

help:      ## list the targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-17s %s\n", $$1, $$2}'

up:        ## start the local platform (mock Azure + GitHub) and wait until healthy
	bash scripts/local/platform.sh up

down:      ## stop the local platform; data stays in the postgres volume
	bash scripts/local/platform.sh down

restart:   ## down, then up
	bash scripts/local/platform.sh restart

status:    ## containers, health and the Backstage URL
	bash scripts/local/platform.sh status

logs:      ## follow logs: make logs (all) or make logs S=orchestrator-worker
	bash scripts/local/platform.sh logs $(S)

reset:     ## stop and delete the local database volume; asks first
	bash scripts/local/platform.sh reset

images:    ## (re)build the platform images
	docker compose -f deploy/local/docker-compose.yml build

e2e:       ## golden-path check through the running platform's real APIs (make up first)
	docker run --rm --network $(NETWORK) -v "$(CURDIR)/scripts/local":/e2e:ro python:3.14-alpine python /e2e/e2e.py

test:      ## Python lint, types, unit/API and e2e tests (no Docker services needed)
	docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -e UV_PROJECT_ENVIRONMENT=/tmp/venv -e UV_LINK_MODE=copy \
	  -v "$(CURDIR)":/src:ro -v sportify-uv-cache:/root/.cache/uv -w /src/services $(UV_IMAGE) sh -c '\
	  uv sync --all-packages --frozen -q && \
	  uv run ruff check --no-cache . && uv run ruff format --check --no-cache . && \
	  uv run mypy --cache-dir /tmp/mypy libs/sportify-common/src azure-discovery/src provisioning-orchestrator/src && \
	  uv run pytest -q -p no:cacheprovider libs/sportify-common/tests && \
	  (cd azure-discovery && uv run pytest -q -p no:cacheprovider -m "not integration and not live_azure") && \
	  (cd provisioning-orchestrator && uv run pytest -q -p no:cacheprovider -m "not integration and not live_azure") && \
	  uv run pytest -q -p no:cacheprovider e2e'

test-integration: ## orchestrator PostgreSQL tests (Testcontainers, uses this Docker Engine)
	docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -e UV_PROJECT_ENVIRONMENT=/tmp/venv -e UV_LINK_MODE=copy \
	  --network host -v /var/run/docker.sock:/var/run/docker.sock \
	  -v "$(CURDIR)":/src:ro -v sportify-uv-cache:/root/.cache/uv -w /src/services/provisioning-orchestrator $(UV_IMAGE) sh -c '\
	  uv sync --all-packages --frozen -q && uv run pytest -q -p no:cacheprovider -m integration'

portal-test: ## portal install (immutable), typecheck, lint and tests on a Linux copy of portal/
	docker run --rm -v "$(CURDIR)/portal":/src:ro -v sportify-yarn-cache:/yarn-cache \
	  -e YARN_CACHE_FOLDER=/yarn-cache -e CI=true -e COREPACK_ENABLE_DOWNLOAD_PROMPT=0 $(NODE_IMAGE) sh -c '\
	  mkdir /work && cd /src && tar --exclude=./node_modules --exclude="./*/*/node_modules" --exclude="./*/*/dist" -cf - . | tar -C /work -xf - && \
	  cd /work && corepack enable && yarn install --immutable && yarn tsc && yarn lint:all && yarn test:all'

check: test portal-test ## the checks that need no running platform
