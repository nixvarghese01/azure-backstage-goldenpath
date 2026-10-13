# ${{ values.name }}

${{ values.description }}

Created by **Sportify Azure Backstage** (request `${{ values.requestId }}`). Owned by `${{ values.owner }}`.

## How this repository is built

1. **Infrastructure first.** This repository starts with Terraform (`infra/terraform`), the Helm chart (`deploy/helm/application`) and the infrastructure workflows. The platform validates, plans and, after **approval in Backstage**, applies the infrastructure.
2. **Application second.** Once the infrastructure is ready, the platform opens a pull request adding the NestJS application, tests, Dockerfile and CI/CD. It merges when checks pass.
3. **Deploy.** CI builds, scans and pushes the image; the deploy workflow installs the Helm chart on the shared AKS cluster and smoke-tests the endpoint.

Status, URLs and history: see this component's **Provisioning** tab in Backstage.

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
