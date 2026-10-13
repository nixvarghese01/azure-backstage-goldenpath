# Portal (Backstage)

Self-hosted Backstage 1.55 for Sportify Azure Backstage. Custom TypeScript is limited to three thin plugins:

| Package | Purpose |
|---|---|
| `plugins/sportify-platform-common` | Shared types and the `sportify.request.approve` permission |
| `plugins/sportify-platform-backend` | Bridge to the Python services (`/api/sportify/*`) with the user's verified identity; scaffolder actions `sportify:request:submit` and `sportify:request:repository-created` |
| `plugins/sportify-platform` | Scaffolder fields (resource picker, availability, stack), the **Provisioning** entity tab and the **Approvals** page |

Everything else is built-in: catalog, scaffolder (`fetch:template`, `publish:github`, `github:environment:create`, `catalog:register`), TechDocs, GitHub auth, permissions and notifications.

## Run locally (WSL2 / Linux / macOS)

```bash
cd portal
corepack enable
yarn install
# PostgreSQL and the Python services: see deploy/local and services/
export SPORTIFY_DEV_SERVICE_TOKEN=dev-only-change-me   # same value as the services
yarn dev   # http://localhost:3000
```

Put GitHub App credentials in `app-config.local.yaml` (git-ignored) or point `GITHUB_APP_BACKSTAGE_CREDENTIALS_FILE` at the file fetched by `scripts/dev-secrets.sh`.

## Notes for validation

This workspace was written by hand against Backstage 1.55 (not generated). If package versions or APIs have moved, generate a fresh app with `npx @backstage/create-app@latest`, then copy in `plugins/`, `app-config*.yaml`, `catalog/` and the plugin wiring from `packages/app/src/App.tsx` and `packages/backend/src/index.ts`.
