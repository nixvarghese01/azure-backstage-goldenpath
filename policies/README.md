# Policies

| Path | Purpose | Used by |
|---|---|---|
| `allowlist.yaml` | Approved subscriptions, regions, shared resources, create-new switches, SKUs, roles, naming, stacks, HA rules | `azure-discovery` (filtering, capabilities, validation) and Conftest (as data) |
| `terraform/common.rego` | Regions, required tags, no changes to unmanaged resources, storage and ACR hardening | all Terraform plans |
| `terraform/app.rego` | Resource-type allowlist, assignable roles, deployer-only RoleBindings | application repository plans |
| `helm/chart.rego` | No `Secret` objects, no secret-like literal env values, non-root, no privilege escalation, drop ALL, limits, probes | rendered application and platform charts |

```bash
# unit tests for the policies
conftest verify -p policies/terraform
# check a plan
terraform show -json dev.tfplan > plan.json
conftest test plan.json -p policies/terraform -d policies/allowlist.yaml --namespace main --namespace app
# check a rendered chart
helm template app deploy/helm/application -f deploy/helm/application/values-dev.yaml > rendered.yaml
conftest test rendered.yaml -p policies/helm
```

Policies use Rego v1 syntax (OPA 1.x, bundled with Conftest 0.71).
