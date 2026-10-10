# Cleanup and teardown

How to remove what the golden path created, for example after recording a demo. Steps are listed in dependency order.

> **Status:** design. Commands are given as the intended procedure. The platform-driven cleanup (`POST /v1/requests/{id}/cleanup`) is planned for Phase 5.

## Rules

- The platform deletes **only resources it created** for the request. These are identified by the tag `managed-by: sportify-platform` and the `request-id` tag.
- Resources selected through **Select existing** are never deleted. Only the role assignments the platform added to them are removed.
- Shared platform infrastructure (AKS, ACR, state storage) is never removed by an application cleanup. It has its own teardown below.

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

Manual fallback, if the platform is unavailable. Run it from the application repository with the provisioning identity:

```bash
helm uninstall orders-api -n orders-api
cd infra/terraform/environments/dev
terraform init        # uses the Azure Storage backend
terraform plan -destroy -out destroy.tfplan
terraform apply destroy.tfplan
```

## 2. Tear down shared demo infrastructure

Only do this when no applications remain on the cluster. Run it from `iac/examples/` in the platform repository:

1. Remove every application first (section 1).
2. Destroy the shared AKS cluster, ingress controller, DNS records and container registry.
3. Remove the platform identities and federated credentials.
4. **Last:** export anything you want to keep from the Terraform state storage account, then delete it.

## 3. Verify nothing is left running

```bash
az resource list --tag managed-by=sportify-platform -o table
az group list --query "[?tags.\"managed-by\"=='sportify-platform']" -o table
```

Also check the subscription's **Cost Management** view a day later to confirm no charges remain.
