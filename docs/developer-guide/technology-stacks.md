# Backend and frontend starters

The platform now contains eight application templates sharing one infrastructure, approval and
deployment workflow. This selection covers several ecosystems; it is not a popularity ranking.
NestJS remains the enabled reference path. The seven new starters are implemented but disabled in
the portal and discovery policy until their target-system checks pass. No builds or tests were run
during this implementation.

| Stack ID | Kind | Runtime/build | Runtime image | Current Azure application capability |
|---|---|---|---|---|
| `nestjs` | Backend API | Node 24 / TypeScript | Node Alpine | Existing reference path |
| `fastapi` | Backend API | Python 3.14 / FastAPI | Python slim | None |
| `go` | Backend API | Go 1.26 / standard HTTP library | Alpine + compiled binary | None |
| `dotnet` | Backend API | .NET 10 / ASP.NET Core | ASP.NET runtime | None |
| `springboot` | Backend API | Java 21 / Spring Boot 4.0.8 / Maven | Java JRE | None |
| `nextjs` | Frontend + server routes | Next.js 16 / React 19 / Node 24 | Node standalone output | None |
| `react` | Frontend SPA | React 19 / TypeScript / Vite 8 | Nginx static assets | None |
| `vue` | Frontend SPA | Vue 3 / TypeScript / Vite 8 | Nginx static assets | None |

Each new project includes demo source, tests, a Dockerfile, local Compose configuration, a README,
and CI/deploy callers. They expose port 3000, `/health/live`, `/health/ready`, `/v1/orders`, and `/docs`.
The new demo orders are read-only. FastAPI exposes Swagger; other starters provide endpoint
documentation. React/Vue serve static JSON from Nginx, not a separate backend service. Next.js
includes server routes. These apps have no production business logic, persistence or user auth.

`templates/applications/_shared` holds default Git/Docker ignore rules, Compose, README, workflow
callers and Helm values. The renderer overlays a stack's `application` files on those defaults;
stack-specific files take precedence. Existing NestJS overrides remain intact. The worker image
includes all stack directories, so selecting a technology does not require a different orchestrator.

Node projects use npm scripts in the existing reusable application CI workflow. Python, Go, .NET
and Java use their Dockerfile's `verify` target for language checks. Image build, scanning, push,
OIDC identity trust, approval and Helm deployment remain in the same reviewed platform workflows.
The template CI matrix renders every stack, checks Compose/Terraform/Helm, runs language checks,
builds images and smoke-checks kind deployments when CI is later executed.

The fixture renderer accepts `--stack`; the existing NestJS directory contains the shared
infrastructure skeleton. New technologies use the None runtime capability in fixtures and policy.
The server rejects unsupported Azure capabilities rather than granting access an app cannot use.
Enable a validated stack consistently in `policies/allowlist.yaml`, `portal/app-config.yaml` and
`portal/app-config.container.yaml`. Dependency locks, image digests, security results and load-based
resource sizing must be checked on the target system before release.

## Runtime sizing

Each application runs as **one pod** on the shared cluster (standard availability tier), sized at
the minimum its runtime needs to start and serve the demo endpoints. The sizes are defined once in
`RUNTIME_PROFILES` in the orchestrator's `templating.py`. The renderer writes them into the
generated `values-dev.yaml` and `docker-compose.yml`, so a local run has the same limits as the pod.

| Stack | CPU request / limit | Memory request = limit | Startup allowance | Runtime setting |
|---|---|---|---|---|
| `nestjs`, `nextjs` | 50m / 500m | 384Mi | 30 s | `NODE_OPTIONS=--max-old-space-size=256` |
| `fastapi` | 50m / 500m | 256Mi | 30 s | — |
| `go` | 25m / 250m | 128Mi | 30 s | `GOMEMLIMIT=100MiB` |
| `dotnet` | 50m / 1000m | 384Mi | 60 s | `DOTNET_gcServer=0` (workstation GC) |
| `springboot` | 100m / 1000m | 512Mi | 60 s | `JAVA_TOOL_OPTIONS=-XX:MaxRAMPercentage=65` |
| `react`, `vue` | 10m / 100m | 64Mi | 30 s | — (Nginx static files) |

- **Memory request equals the limit.** The scheduler reserves exactly what the pod may use, and the
  pod is never evicted for node memory pressure. Runtime heap settings keep the heap below the limit
  so the process doesn't get OOM-killed.
- **CPU requests are small** so many demo apps fit on the single small node. The CPU limit gives
  headroom for startup; the JVM and .NET get a full core because they start slowly when throttled.
- **A startup probe** (every 2 s, for the allowance above) holds the liveness probe back until the
  app has started, so a slow start isn't mistaken for a hung process.
- **The `ha` tier** keeps the same pod size and adds replicas, an HPA, a PDB and zone spreading
  ([ADR-0004](../adr/0004-availability-tier-option.md)).

These are starting points for empty starters. Resize an application in its own `values-dev.yaml` and
`docker-compose.yml` once it has real load; change a profile in `templating.py` to change the default
for every new application of that stack.

## Upstream design references

- [FastAPI container guidance](https://fastapi.tiangolo.com/deployment/docker/)
- [Next.js deployment and standalone output](https://nextjs.org/docs/app/getting-started/deploying)
- [Go 1.26](https://go.dev/doc/go1.26)
- [ASP.NET Core containers](https://learn.microsoft.com/en-us/aspnet/core/host-and-deploy/docker/building-net-docker-images?view=aspnetcore-10.0)
- [Spring Boot 4 requirements](https://docs.spring.io/spring-boot/4.0/system-requirements.html)
- [Vite 8](https://vite.dev/blog/announcing-vite8.html), [Vue tooling](https://vuejs.org/guide/quick-start)
