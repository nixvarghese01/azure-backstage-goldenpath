# ADR-0006: Container delivery for the platform services

- Status: accepted for implementation; execution validation pending
- Date: 2026-10-13
- Related: [ADR-0001](0001-python-platform-services.md), [microservices architecture](../architecture/microservices.md)

## Context

The platform already separates portal, discovery and orchestration responsibilities, but its local
Compose definition starts only PostgreSQL. Backstage requires a prepared host bundle, and the Python
Dockerfiles move the virtualenv to a different runtime path. Local and release builds need consistent
build contexts and explicit startup ordering.

## Decision

Use three images and four application processes. Backstage remains one service serving its frontend
bundle and built-in backend plugins. Azure discovery runs independently. The orchestrator API and
worker use one image and own one database; Alembic migrations run in a separate one-shot container.
Keep the existing Helm releases for AKS.

Build every image from the repository root. The new Backstage multi-stage build creates the standard
skeleton/bundle artifacts and assembles production dependencies. Python builds include all workspace
members for dependency resolution and install the selected package into `/opt/venv` in both stages.
Existing lockfiles are enforced; initial dependency resolution is allowed only when the lockfile is
absent. Release lockfiles and base-image digest pinning are still required follow-up work.

Local Compose runs discovery and orchestrator GitHub clients in mock mode. Guest sign-in is explicitly
enabled in the local Backstage config and backend environment; production uses the separate production
config with GitHub sign-in. Local guest access maps to the existing catalog developer and owning team,
not the approval group. Python services stay inside the bridge network; published ports bind to
loopback. Static service auth and the public webhook placeholder are restricted to local use.

Application containers use non-root users, read-only root filesystems, temporary writable mounts,
and dropped capabilities. Startup depends on readiness and successful database migrations. Worker
and migration containers disable the image's HTTP health check. Worker heartbeat instrumentation
is deferred.

Local Compose defaults to the `runtime-lite` Backstage target, with external/prebuilt TechDocs and
no Python/MkDocs runtime tooling. A matching Compose override selects the full target and on-demand
generation. The release image still defaults to the full target. Runtime dependencies are focused
on the backend workspace, and only the portal's infrastructure scaffold is copied into its base
image; application rendering remains the worker's responsibility.

Local CPU/memory ceilings and rotated logs bound resource growth. PostgreSQL memory settings and
worker polling intervals are reduced for the development workload. Python HTTP services depend on
base FastAPI/Uvicorn packages rather than their optional standard extras; trace exporter imports
are deferred until tracing is enabled. These choices are starting points, not measured savings or
production sizing. They require later build, startup and load validation.

## Consequences

Developers can build and start the service topology without preparing Node or Python dependencies
on the host. Docker builds still require network access and resolvable dependency versions.
Mock integration mode does not replace real GitHub App setup, Actions, Terraform or AKS validation.
No builds, startup commands, tests, pushes or deployments were executed for this implementation.

## References

- [Backstage Docker image guidance](https://backstage.io/docs/deployment/docker/)
- [Backstage guest authentication provider](https://backstage.io/docs/next/auth/guest/provider/)
- [Backstage external TechDocs builder](https://backstage.io/docs/features/techdocs/getting-started/)
- [Docker Compose service resource settings](https://docs.docker.com/reference/compose-file/services/)
- [Local setup and deferred execution](../../deploy/local/README.md)
