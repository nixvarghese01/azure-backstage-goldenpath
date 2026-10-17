# ADR-0009: PostgreSQL inside the cluster for the dev platform

- **Status:** Accepted
- **Date:** 2026-10-15

## Context

Backstage and the provisioning orchestrator keep their state in PostgreSQL. The platform uses Azure
Database for PostgreSQL Flexible Server with Entra authentication (ADR-0001).

On the first real provisioning (Azure Free Trial in a CAF landing zone that allows only Sweden Central),
the Flexible Server failed with `RegionalAllocationFailed` in every zone tried, on several days. The
landing zone policy rules out other regions. The dev platform must still come up, at low cost, within the
platform's security rules: no secrets in the repository, Terraform state or Kubernetes Secret objects;
secrets live in Key Vault and reach pods through the CSI driver with Workload Identity.

## Decision

1. **`20-shared-dev` makes Azure PostgreSQL optional** (`postgres.enabled`, default `true`). Dev sets it
   to `false`. test and prod keep Azure PostgreSQL with Entra authentication.
2. **A single-instance PostgreSQL runs in `idp-platform`** (`deploy/charts/postgres`): a StatefulSet with
   an 8 GiB disk, non-root, read-only root filesystem, seccomp `RuntimeDefault`, all capabilities
   dropped, and a NetworkPolicy that admits only Backstage and the orchestrator on 5432.
3. **Passwords live in Key Vault**, never in Kubernetes Secrets. `scripts/create-platform-secrets.sh`
   generates `postgres-password`, `backstage-db-password` and `orchestrator-db-password`. A dedicated
   identity `id-idp-postgres-<env>` (Workload Identity) reads all three to create the login roles;
   Backstage and the orchestrator each read only their own (per-secret RBAC in `10-identities`).
4. **Services read the password from the CSI mount.** Backstage uses its existing
   `/mnt/secrets/backstage-db-password` and a small config overlay (host `postgres`, no TLS on the pod
   network). The orchestrator reads `ORCHESTRATOR_DATABASE_PASSWORD_FILE` on every new connection, so a
   rotated Key Vault secret applies without a restart.
5. `platform-release` installs `postgres` before the services when `PLATFORM_POSTGRES_IN_CLUSTER` is
   `true` (set by `scripts/bootstrap-platform.sh github` from the `20-shared-dev` inputs).

## Consequences

- The dev platform no longer depends on PostgreSQL Flexible Server capacity, and costs less
  (about 0.25 vCPU and 256 MiB on the node, plus an 8 GiB disk).
- **No high availability or point-in-time restore in dev:** one pod and one zonal disk. Teardown deletes
  the disk with the cluster, so dev data is temporary. That is acceptable for a dev platform with a
  time-to-live; it is not for test or prod, which keep Azure PostgreSQL.
- Traffic between the services and PostgreSQL stays on the pod network without TLS, limited by the
  NetworkPolicy.
- Trivy's KSV-0109 flags the `PASSWORD` keyword in the init script's SQL. It is a false positive (the
  values come from Key Vault at runtime) and is accepted in `.trivyignore.yaml`, scoped to that file,
  with an expiry.
