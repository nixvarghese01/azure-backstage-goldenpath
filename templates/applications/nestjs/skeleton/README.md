# ${{ values.name }}

${{ values.description }}

Created by **Internal Developer Portal** (request `${{ values.requestId }}`). Owned by `${{ values.owner }}`.

## How this repository is built

1. **Infrastructure and starter.** This repository starts with Terraform (`infra/terraform`), the Helm chart (`deploy/helm/application`), the infrastructure workflows and the `${{ values.stack }}` starter (source, tests, Dockerfile, Compose). The platform validates, plans and, after **approval in Backstage**, applies the infrastructure.
2. **CI/CD second.** Once the infrastructure is ready, the platform opens a pull request adding the CI/CD workflows and the Helm values filled with the infrastructure outputs. It merges when checks pass.
3. **Deploy.** CI builds, scans and pushes the image; the deploy workflow installs the Helm chart on the shared AKS cluster and smoke-tests the endpoint.

Status, URLs and history: see this component's **Provisioning** tab in Backstage.

Run the starter locally with `docker compose up --build -d`. The generated
README then describes the local dummy API, which uses in-memory data and does not need Azure credentials.

## Layout

| Path | What |
|---|---|
| `infra/terraform/` | Application infrastructure. The `.tf` files are the platform's standard root module; your choices are in `environments/${{ values.environment }}/terraform.tfvars` |
| `deploy/helm/application/` | Helm chart (Deployment, Service, ServiceAccount, HTTPRoute; HPA + PDB when HA) |
| `.github/workflows/` | Thin callers of the platform's reviewed reusable workflows |
| `docs/` | TechDocs for this service |

## Working on it

- Change infrastructure through a pull request to `infra/terraform/environments/...`; the platform plans it and asks for approval.
- Never add secrets to this repository. Azure access uses Workload Identity; if you need a secret, use the Key Vault capability (see the platform's secret-management guide).
