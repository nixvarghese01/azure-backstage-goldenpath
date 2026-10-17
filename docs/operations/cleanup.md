# Cleanup and teardown

How to remove what the golden path created, for example after recording a demo. Steps are listed in dependency order.

> **Status:** implemented and verified. **Clean up** on the request's Provisioning tab (`POST /v1/requests/{id}/cleanup`) uninstalls the release, plans the destroy, waits for approval in Backstage, applies it and removes the catalog entry. A failed request can also be resumed with **Retry** instead. The manual commands below are for the shared platform and for recovery.

## Rules

- The platform deletes **only resources it created** for the request. These are identified by the tag `managed-by: idp-platform` and the `request-id` tag.
- Resources selected through **Select existing** are never deleted. Only the role assignments the platform added to them are removed.
- Shared platform infrastructure (AKS, ACR, PostgreSQL, Key Vault, state storage) is never removed by an application cleanup. It has its own teardown below.

## 1. Remove one application

1. **Start cleanup in Backstage** from the request's *Provisioning* tab, or call `POST /v1/requests/{id}/cleanup`. The state becomes `CLEANUP_PENDING`.
2. The orchestrator:
   - runs `helm uninstall` for the release in the application namespace
   - dispatches `terraform-apply.yml` with a **destroy plan**, which needs approval in Backstage like any other apply. It removes the managed identity, the federated credential, the namespace (if created new), the role assignments and any data resources created new.
   - removes the entity from the Backstage catalog
3. When the destroy succeeds, the state becomes `CLEANED_UP`. If it fails part-way, the request lists which resources still exist and the destroy can be retried safely.
4. **Repository.** Choose one of the following:
   - **Archive** it (*Settings → Archive this repository*) to keep it as a read-only reference example.
   - **Make it private.** Note that environments and protection rules stop being enforced on free plans.
   - **Delete** it.

Manual fallback, if the platform is unavailable. Run it from the application repository. `helm uninstall` uses the **deployment** identity, and the Terraform steps use the **provisioning** identity:

```bash
helm uninstall orders-api -n orders-api          # deployment identity
cd infra/terraform                               # provisioning identity from here
terraform init -backend-config=environments/dev/backend.hcl
terraform plan -destroy -var-file=environments/dev/terraform.tfvars -out=destroy.tfplan
terraform apply destroy.tfplan
```

## 2. Tear down shared demo infrastructure

Only do this when no applications remain on the cluster. Destroy the stacks in `iac/platform/` of the platform repository in **reverse order**:

1. Remove every application first (section 1).
2. `iac/platform/30-cluster-config`: destroy the in-cluster configuration (namespaces, Gateway, RBAC, platform Workload Identity federation).
3. `iac/platform/20-shared-dev`: destroy the shared AKS cluster, shared Gateway, DNS zone, container registry and PostgreSQL flexible server. Export anything you want to keep from PostgreSQL first.
4. `iac/platform/10-identities`: remove the platform identities, federated credentials and the platform Key Vault. With purge protection on, the vault stays **soft-deleted and its name stays reserved** until the retention period ends. The demo uses the minimum 7-day retention for this reason ([demo-environment.md](demo-environment.md)).
5. `iac/platform/05-subscriptions`, if used: vended subscriptions are cancelled through the billing process, not destroyed directly.
6. `iac/platform/00-bootstrap`, **last**: export anything you want to keep from the state storage account, remove its `CanNotDelete` lock, migrate this stack's state back to local, then destroy it.

## 3. Verify nothing is left running

```bash
az resource list --tag managed-by=idp-platform -o table
az group list --query "[?tags.\"managed-by\"=='idp-platform']" -o table
```

Also check the subscription's **Cost Management** view a day later to confirm no charges remain.
