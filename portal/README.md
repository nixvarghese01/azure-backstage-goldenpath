# Portal (Backstage)

Self-hosted Backstage 1.55 for Internal Developer Portal. Custom TypeScript is limited to three thin plugins:

| Package | Purpose |
|---|---|
| `plugins/idp-platform-common` | Shared types and the `idp.request.approve` permission |
| `plugins/idp-platform-backend` | Bridge to the Python services (`/api/idp/*`) with the user's verified identity; scaffolder actions `idp:request:submit` and `idp:request:repository-created` |
| `plugins/idp-platform` | Scaffolder fields (resource picker, availability, stack), the **Provisioning** entity tab and the **Approvals** page |

Everything else is built-in: catalog, scaffolder (`fetch:template`, `publish:github`, `github:environment:create`, `catalog:register`), TechDocs, GitHub auth, permissions and notifications.

## Container deployment

[`Dockerfile`](Dockerfile) builds the frontend/backend bundle in a Node build stage and assembles
a non-root runtime with production dependencies. The default `runtime` includes TechDocs tooling;
the local `runtime-lite` target omits Python and MkDocs. Build it from the repository
root, which supplies the catalog, local templates and documentation:

```bash
docker build -f portal/Dockerfile -t idp/backstage:local .
```

The default command loads `app-config.container.yaml` followed by `app-config.production.yaml`.
The [local Compose stack](../deploy/local/README.md) selects `app-config.docker.yaml` instead,
uses `runtime-lite` with prebuilt TechDocs and applies adjustable resource ceilings. It serves
the UI and backend together at `http://localhost:7007` and enables guest sign-in for the demo
developer. Python services communicate through container DNS names; the browser uses
only Backstage. GitHub and Azure actions require their own integration configuration.

The older `packages/backend/Dockerfile` remains available for a prepared host-built bundle.
Compose and the platform release workflow use the new repository-root build. Image builds and
startup have not been executed; dependency lockfiles and runtime validation remain pending.

## Run locally (WSL2 / Linux / macOS)

```bash
cd portal
corepack enable
yarn install
# PostgreSQL and the Python services: see deploy/local and services/
export IDP_DEV_SERVICE_TOKEN=dev-only-change-me   # same value as the services
yarn dev   # http://localhost:3000
```

Put GitHub App credentials in `app-config.local.yaml` (git-ignored) or point `GITHUB_APP_BACKSTAGE_CREDENTIALS_FILE` at the file fetched by `scripts/dev-secrets.sh`.

## Notes for validation

This workspace was written by hand against Backstage 1.55 (not generated). If package versions or APIs have moved, generate a fresh app with `npx @backstage/create-app@latest`, then copy in `plugins/`, `app-config*.yaml`, `catalog/` and the plugin wiring from `packages/app/src/App.tsx` and `packages/backend/src/index.ts`.
