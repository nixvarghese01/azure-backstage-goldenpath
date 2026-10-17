# Terraform state

How platform and application Terraform state is stored, protected, locked and recovered. Losing or
corrupting state means Terraform no longer knows what it manages, so treat these procedures as
production operations even in `dev`.

## Where state lives

`iac/platform/00-bootstrap` creates one storage account per environment (`stidptfstate<env>`, in
`rg-idp-tfstate-<env>`). Every stack has its own state file, so a mistake in one can't damage another:

| Container | Key | Written by |
|---|---|---|
| `platform` | `platform/00-bootstrap.tfstate` | The bootstrap stack itself, after it migrates into the account it created |
| `platform` | `platform/10-identities.tfstate` | An admin (first run), then `platform-apply` |
| `platform` | `platform/20-shared-dev.tfstate`, `platform/30-cluster-config.tfstate` | `platform-apply` (`platform` identity) |
| `platform` | `platform/05-subscriptions.tfstate` | `platform-apply` (`vending` identity) |
| `apps` | `<application>/<environment>.tfstate` | Generated repositories (`reusable-terraform.yml`, `provisioning` identity) |

Platform and application state are in separate containers with separate role assignments. An
application pipeline can't read or change platform state.

## Protection

| Control | Setting | Protects against |
|---|---|---|
| Geo-zone-redundant storage (GZRS) | `account_replication_type = "GZRS"` | Zone or region outage |
| Blob versioning | Every write keeps the previous version | A bad apply or corrupted state |
| Soft delete | Blobs and containers for 30 days | Accidental deletion |
| Delete lock | `CanNotDelete` on the account | Deleting the account, including by a teardown |
| Entra ID only | Shared keys disabled; `use_azuread_auth = true` | Leaked storage keys or SAS tokens |
| Least privilege | `Storage Blob Data Contributor` on one container per writer; `Reader` for plan | One identity damaging another's state |
| No secrets in state inputs | Pipelines pass IDs only; secret values are set in Key Vault out of band | Secrets leaking through state |

## Locking

Terraform takes a **blob lease** on the state file for every `plan` and `apply` that writes, so two runs
can't change the same stack at once. The pipelines add a second guard: `platform-apply` has one
concurrency group per stack and `platform-provision` runs one at a time. Read-only plans (pull requests
and drift detection) use `-lock=false`, so they never block an apply.

**A stuck lock** (a run was cancelled mid-apply) shows `Error acquiring the state lock` with a lock ID.
Make sure no run is still active for that stack, then either:

```bash
terraform force-unlock <lock id>            # in the stack directory, after terraform init
# or break the lease directly
az storage blob lease break --account-name stidptfstatedev --container-name platform \
  --blob-name platform/20-shared-dev.tfstate --auth-mode login
```

## Drift detection

`platform-plan` runs every Monday and plans the stacks in `PLATFORM_DRIFT_STACKS` (default
`["20-shared-dev"]`) with the read-only plan identity. If Azure differs from the code, for example after
a change in the portal, the run fails and lists the affected resources. Fix it by reverting the manual
change, or by codifying it in a pull request.

## Recovery

**Restore a previous state version** (state corrupted, or an apply recorded something wrong):

```bash
az storage blob list --account-name stidptfstatedev --container-name platform --auth-mode login \
  --prefix platform/20-shared-dev.tfstate --include v --query "[].{version:versionId, modified:properties.lastModified}" -o table
az storage blob copy start --account-name stidptfstatedev --destination-container platform \
  --destination-blob platform/20-shared-dev.tfstate --auth-mode login \
  --source-uri "https://stidptfstatedev.blob.core.windows.net/platform/platform/20-shared-dev.tfstate?versionId=<version>"
```

Then run a plan and check it shows only the changes you expect before any apply.

**Undelete** a deleted state file (within 30 days): `az storage blob undelete` with the same names.

**Import or move resources** only in a reviewed pull request: add an `import {}` or `moved {}` block to
the stack, so the change goes through `platform-plan` and approval like any other.

## Bootstrap and teardown

The state account can't be created by a stack that already keeps its state there.
`scripts/bootstrap-platform.sh state` applies `00-bootstrap` with local state, grants you data access,
then migrates the state into the new account and deletes the local copy.

`platform-provision` with `action: teardown` destroys `30-cluster-config` and `20-shared-dev` only. The
state account and identities stay, so you can provision again. Removing everything is a manual step in
[cleanup.md](cleanup.md): lift the delete lock last, after you've checked that no state is still needed.
