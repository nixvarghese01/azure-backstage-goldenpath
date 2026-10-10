# ADR-0001: Self-hosted Backstage with Python platform services

- **Status:** Accepted
- **Date:** 2026-10-10

## Context

Sportify Azure Backstage is a public portfolio project that demonstrates Backstage platform engineering on Azure. It needs:

- a developer portal with a catalog, templates, docs, sign-in and permissions
- read-only Azure discovery to fill the **Create new / Select existing** pickers
- a durable, asynchronous orchestrator for the golden-path workflow, with idempotency, restart recovery, approvals and audit

Backstage's backend is Node.js. Any discovery or orchestration logic built as Backstage plugins would have to be written in TypeScript. The team prefers Python for platform logic, and the Azure SDKs for Python are mature.

## Options considered

1. **Everything in Backstage plugins (TypeScript).** This is the most "Backstage-native" option. However, all business logic would be in TypeScript and tied to the Backstage release cycle.
2. **Hosted Backstage (Roadie) or another portal (Port, Cortex, Microsoft Dev Center).** Nobody has to run the portal backend, but the project would no longer demonstrate self-hosted Backstage. Port, Cortex and Dev Center are also not open source.
3. **A custom React + FastAPI portal.** Everything is in Python, but the catalog, templates, docs and auth would have to be rebuilt from scratch.
4. **Self-hosted Backstage for portal features, with Python services for platform logic.** *(chosen)*

## Decision

- Run **self-hosted Backstage** and use its built-in catalog, scaffolder (`fetch:template`, `publish:github`, `catalog:register`), TechDocs, auth, permissions and GitHub integration.
- Keep custom TypeScript to **one thin backend bridge plugin** (forwarding calls with the user's identity, plus two scaffolder actions) and **one thin frontend plugin** (the resource picker field and the status card). Neither contains business logic.
- Put all platform logic in **Python FastAPI services**:
  - `azure-discovery-service`: read-only, with the `Reader` identity only.
  - `provisioning-orchestrator-service`: an API plus a worker, with state in PostgreSQL. It uses a GitHub App token and has no Azure access.

### Orchestration engine

For milestone 1, the orchestrator uses a **PostgreSQL-backed state machine and job table** (`SELECT ... FOR UPDATE SKIP LOCKED`). The workflow is mostly event-driven: it dispatches a GitHub workflow and then waits for a webhook. An explicit state table fits this well and adds no infrastructure beyond PostgreSQL.

Because this is a model project meant to showcase the design, the state table is also the more readable choice. States, idempotency keys and locking are visible in a small amount of code, and the whole demo runs with `docker compose up`. A production rollout with many workflow types, long-running timers or high volume should move to Temporal (see below).

Alternatives for this engine:

| Engine | Why not now |
|---|---|
| Temporal (Python SDK) | It provides durable timers, retries and replay out of the box, but adds a Temporal cluster to run and secure. It's a strong option if workflows grow more complex. The state-transition code is written so a Temporal worker could replace the job table later. |
| Azure Durable Functions (Python) | Azure-native and serverless, but it splits the runtime between AKS and Functions and is harder to run locally. |
| GitHub Actions only (no orchestrator) | Least code, but state, idempotency, cross-workflow status and audit would be spread across workflow runs, so Backstage could not report reliable per-stage status. |

## Consequences

- There are two runtimes to build, test and secure: Node.js for Backstage and Python for the services. Service-to-service authentication between the bridge and the Python services is required.
- Discovery and orchestration run under separate identities and deployments, which matches the least-privilege model.
- The Python services can be tested on their own with pytest, mocked Azure SDKs and PostgreSQL in Testcontainers.
- Backstage upgrades touch only the thin bridge, which keeps upgrade effort low.
