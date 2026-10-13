# Validation checklist

The code for milestone 1 was written without being run. Work through this list, in order, to validate it. Record results in the README's *Implementation status* table.

## 1. Python services (no Azure needed)

```bash
cd services
uv sync --all-packages
uv run ruff check . && uv run ruff format --check .
uv run mypy libs/sportify-common/src azure-discovery/src provisioning-orchestrator/src
uv run pytest libs/sportify-common/tests
(cd azure-discovery && uv run pytest)
(cd provisioning-orchestrator && uv run pytest -m "not integration")
(cd provisioning-orchestrator && uv run pytest -m integration)   # needs Docker
uv run pytest e2e                     # cross-service golden path, renders the real NestJS template
# opt-in, read-only, real Azure:
RUN_LIVE_AZURE_TESTS=1 LIVE_SUBSCRIPTION_ID=<id> uv run pytest azure-discovery -m live_azure
```

Things most likely to need adjustment:
- SQLAlchemy JSON path filters on SQLite in `engine._request_for_repo`.
- FastAPI's yielding dependency in `main.db`.
- The test fixtures' environment handling.

## 2. Local stack

```bash
cd deploy/local && cp .env.example .env && docker compose up -d postgres
cd ../../services
DISCOVERY_AZURE_MODE=mock SPORTIFY_AUTH_MODE=static SPORTIFY_DEV_SERVICE_TOKEN=dev-only-change-me \
  DISCOVERY_POLICY_FILE=../policies/allowlist.yaml uv run uvicorn azure_discovery.main:create_app --factory --port 8001
ORCHESTRATOR_DATABASE_URL=postgresql+psycopg://orchestrator:dev-only-not-a-secret@localhost:5432/orchestrator \
  uv run --package provisioning-orchestrator alembic -c provisioning-orchestrator/alembic.ini upgrade head
# then run the API (port 8002) and the worker (orchestrator-worker) with ORCHESTRATOR_GITHUB_MODE=mock
```

## 3. Policies, Terraform and Helm (no Azure needed)

```bash
conftest verify -p policies/terraform
for d in iac/modules/*; do
  (
    cd "$d" || exit 1
    terraform init -backend=false && terraform validate || exit 1
    if [ -d tests ]; then terraform test; fi
  ) || exit 1
done
uv run --project services python templates/applications/nestjs/render_fixture.py /tmp/orders-api
helm lint /tmp/orders-api/deploy/helm/application -f /tmp/orders-api/deploy/helm/application/values-dev.yaml
```

Most likely to need adjustment: attribute names that changed between azurerm 4.x and 5.x, and `kubernetes_*_v1` resource names in provider 3.x.

## 4. Generated NestJS application

```bash
cd /tmp/orders-api && npm install && npm run lint && npm test && npm run test:e2e && npm run build && docker build -t orders-api .
```

Then commit the generated `package-lock.json` to the template, and switch CI back to `npm ci` with caching.

## 5. Portal (WSL2)

```bash
cd portal
corepack enable
yarn plugin import https://versions.backstage.io/v1/tags/main/yarn-plugin
yarn install && yarn tsc && yarn test:all && yarn dev
```

If APIs moved, generate a fresh app (`npx @backstage/create-app@latest`) and port `plugins/`, `App.tsx`, `EntityPage.tsx`, `backend/src/*` and `app-config*.yaml` into it. Check these first:
- `scaffolderActionsExtensionPoint` import path
- `ctx.checkpoint`
- `createTemplateAction` schema style
- `github:environment:create` inputs

## 6. GitHub organisation

1. Create the organisation, make the platform repository public, and push.
2. Run `scripts/configure-github-oidc.sh <org>` (ADR-0005).
3. Register GitHub App #1 (Backstage) and #2 (orchestrator, including the custom deployment protection rule), then install both.
4. Set organisation variables:
   - `AZURE_TENANT_ID`
   - `PROVISIONING_CLIENT_ID`
   - `DEPLOYMENT_CLIENT_ID`
   - `SPORTIFY_CALLBACK_URL`
5. Set platform repository variables:
   - client IDs, `ACR_NAME`, `AKS_NAME`, `AKS_RESOURCE_GROUP`
   - `PLATFORM_BACKEND_HCL`, `PLATFORM_TFVARS_JSON`, `PLATFORM_CHART_VALUES_JSON`
6. Create environments in the platform repository: `platform` (with required reviewers), `platform-plan`, `platform-deploy` and `platform-vending`.

## 7. Azure (free subscription, Phase 4-5)

Follow [demo-environment.md](demo-environment.md):
1. Apply the stacks `00` → `10` → `20` → `30`.
2. Run `scripts/postgres-grant-identities.sql`.
3. Set the Key Vault secret values out of band.
4. Run `platform-release`.
5. Run the golden path ([IMPLEMENTATION_PLAN.md §6](../../IMPLEMENTATION_PLAN.md#6-demo-script)).
