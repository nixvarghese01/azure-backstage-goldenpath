# ADR-0005: Reusable workflows, CI identity trust and Helm release storage

- **Status:** Accepted
- **Date:** 2026-10-13

## Context

Every generated repository needs Azure access from GitHub Actions: the **provisioning** identity for Terraform, and the **deployment** identity to push images and deploy. Azure OIDC federation trusts a token's `subject` claim, which by default is `repo:<org>/<repo>:environment:<env>`. Two problems follow:

1. **A federated credential per repository doesn't scale and can't be bootstrapped.** Each new repository would need new credentials on the shared identities *before* its first plan. Nothing in the golden path can create them safely: the orchestrator deliberately has no Azure access, and a managed identity supports at most 20 credentials.
2. **The repository controls its own workflows.** Anyone with write access to a generated repository could change a workflow to use the identity differently. `CODEOWNERS` helps, but it is a review control, not an enforcement control.

Separately, Helm stores release state in Kubernetes `Secret` objects by default. That conflicts with the secret-management rule that no `Secret` objects exist in application or platform namespaces.

## Decision

### 1. All privileged CI runs in the platform's reviewed reusable workflows

- The platform repository provides `reusable-terraform.yml`, `reusable-application-ci.yml` and `reusable-application-deploy.yml`.
- A generated repository contains only **thin callers** (`terraform-validate.yml`, `terraform-plan.yml`, `terraform-apply.yml`, `application-ci.yml`, `application-deploy.yml`) that pass inputs.

### 2. The GitHub organisation customises the OIDC subject claim

`scripts/configure-github-oidc.sh` runs once and sets the organisation's subject template to include `repository_owner_id`, `environment` and `job_workflow_ref`. Each identity then has **one credential per environment**, and that credential trusts only the platform's reusable workflow:

```
repository_owner_id:<org-id>:environment:dev-infra:job_workflow_ref:<org>/sportify-azure-backstage/.github/workflows/reusable-terraform.yml@refs/heads/main
```

| Identity | Environment | Workflow trusted |
|---|---|---|
| provisioning | `<env>-infra-plan`, `<env>-infra` | `reusable-terraform.yml` |
| deployment | `<env>-build`, `<env>` | `reusable-application-ci.yml`, `reusable-application-deploy.yml` |

The platform repository's own workflows keep repository-based subjects (`repo:<org>/sportify-azure-backstage:environment:platform…`). Organisation customisation applies to repositories that opt in; generated repositories inherit the organisation default.

**Effect:** a new repository works immediately with no new credentials. A changed caller workflow in a generated repository can't obtain Azure tokens, because its `job_workflow_ref` would differ. Only a reviewed change to the platform repository can change what runs with these identities.

### 3. Environments per stage

| Environment | Purpose | Protection |
|---|---|---|
| `<env>-infra-plan` | Terraform plan | Branch policy |
| `<env>-infra` | Terraform apply | **Custom deployment protection rule** owned by the orchestrator (approval in Backstage) |
| `<env>-build` | Image push | Protected branches only |
| `<env>` | Deploy | Protected branches only |

The scaffolder creates these environments (`github:environment:create`). The bridge action attaches the protection rule.

### 4. Helm stores releases in ConfigMaps

All deploys set `HELM_DRIVER=configmap`, and the `sportify-app-deployer` ClusterRole has **no access to Secrets**. Release metadata isn't sensitive, so ConfigMaps are acceptable.

### 5. The provisioning identity's Azure scope

The provisioning identity creates application resources: resource groups (for "Create new"), managed identities with federated credentials, Storage and Key Vault. It needs:

- **`Sportify App Provisioner`**, a custom role at subscription scope, limited to those resource types. No compute, network or key-listing actions.
- **`Role Based Access Control Administrator`** with an ABAC condition that allows assigning only the allowlisted data roles (Storage Blob Data Contributor and Reader, Key Vault Secrets User).

This is broader than "per resource group", because "Create new resource group" can't be pre-scoped. The plan policies (`policies/terraform/app.rego`), the resource-type allowlist and approval in Backstage compensate. A production platform would add Azure Policy assignments that restrict regions, SKUs and tags at subscription scope.

## Consequences

- Workflow fixes roll out to every application at once, through the platform repository's review.
- The platform repository must be public, or the organisation must allow reusable-workflow access from internal or private repositories.
- Pinning callers to `@main` means a platform change affects every application immediately. A production setup would pin to release tags (for example `@workflows/v1`) and update `reusable_workflow_ref` in `10-identities`.
- Kubernetes release history is visible to namespace readers as ConfigMaps. This is acceptable because it contains no secrets.
