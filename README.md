# Internal Developer Portal (IDP), powered by Backstage

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![ci-security](https://github.com/nixvarghese01/azure-backstage-goldenpath/actions/workflows/ci-security.yml/badge.svg?branch=develop)](https://github.com/nixvarghese01/azure-backstage-goldenpath/actions/workflows/ci-security.yml)
[![codeql](https://github.com/nixvarghese01/azure-backstage-goldenpath/actions/workflows/codeql.yml/badge.svg?branch=develop)](https://github.com/nixvarghese01/azure-backstage-goldenpath/actions/workflows/codeql.yml)
[![Release](https://img.shields.io/github/v/release/nixvarghese01/azure-backstage-goldenpath)](https://github.com/nixvarghese01/azure-backstage-goldenpath/releases)

An Internal Developer Platform (IDP) built on [Backstage](https://backstage.io), Microsoft Azure, Azure Kubernetes Service (AKS), Terraform, Helm and GitHub Actions.

The IDP lets developers request a production-shaped service through a self-service portal. The platform then validates the request, creates a dedicated repository, provisions or reuses approved Azure infrastructure behind an approval gate, and deploys the application to a shared AKS cluster. Backstage reports the status of each stage.

> **This is a model project.** It is a reference design that shows how an enterprise-grade IDP on Backstage and Azure can be structured, secured and operated. The implementation is deliberately scoped to one golden path, to demonstrate the design end to end. It is not intended for wide production rollout as-is. Where a production platform would make a different trade-off, the [ADRs](docs/adr/) say so, and [Best practice vs. this free-tier project](docs/best-practice-vs-free-tier.md) lists every deviation with its reason and the switch.

> **Status: v1.0.0.** The golden path works end to end on AKS in a free Azure subscription: one
> Backstage form produced the `orders-api` repository (NestJS starter in its first commit), Terraform
> validate and plan, approval in Backstage, apply, the application pull request, CI (build, scan, push)
> and a Helm deploy to its own namespace, with each stage reported on the Provisioning tab. The portal
> is served over HTTPS (Let's Encrypt), failed requests can be retried or cleaned up, and CI runs on every
> pull request. The full platform also runs locally with `make up` and passes `make e2e`.
> What comes next is on the [roadmap board](https://github.com/users/nixvarghese01/projects/4); the
> [Implementation status](#implementation-status) table separates verified behaviour from code written.

> **Runs on an Azure Free Trial.** The whole platform (AKS, Backstage, the platform services, PostgreSQL,
> HTTPS, the golden path and the deployed apps) fits on **one 4-vCPU node** in a Free Trial subscription
> with the spending limit on, so usage comes out of the trial credit and is never billed to a card.
> Running costs about **USD 0.18 per hour** (almost all of it the node); a timer tears the platform down
> after 2–48 hours, and `make`/`platform-provision` refuse to create anything while the spending limit is
> off. v1.0.0 was built and verified this way. Every free-tier compromise is listed with its enterprise
> switch in [Best practice vs. this free-tier project](docs/best-practice-vs-free-tier.md); setup steps are
> in [demo-environment.md](docs/operations/demo-environment.md).

Application starters now cover **NestJS, FastAPI, Go, ASP.NET Core, Spring Boot, Next.js, React/Vite
and Vue/Vite**. NestJS remains enabled; the seven new starters are disabled pending target-system
validation. See the [technology inventory](docs/developer-guide/technology-stacks.md) for runtimes,
container design, CI coverage and current capability limits.

---

## Contents

- [Why Backstage](#why-backstage)
- [Why this project](#why-this-project)
- [The first golden path](#the-first-golden-path)
- [Architecture](#architecture)
- [Features](#features)
- [Workflow lifecycle](#workflow-lifecycle)
- [Repository visibility](#repository-visibility)
- [Identity and security model](#identity-and-security-model)
- [Repository layout](#repository-layout)
- [Generated application repository](#generated-application-repository)
- [Prerequisites](#prerequisites)
- [Local development](#local-development)
- [Testing strategy](#testing-strategy)
- [Implementation status](#implementation-status)
- [Roadmap](#roadmap)
- [Documentation](#documentation)
- [Contributing and security](#contributing-and-security)

---

## Why Backstage

**Where it comes from.** [Backstage](https://backstage.io) was built inside Spotify to tame the sprawl of
thousands of services, pipelines and docs owned by hundreds of squads: one portal with a software
catalog, templates for new services ("golden paths") and docs next to the code. Spotify open-sourced it
in **March 2020** under the Apache 2.0 licence.

**Open-source status.** Backstage was accepted into the Cloud Native Computing Foundation (CNCF) as a
Sandbox project in **September 2020** and moved to **Incubating** in **March 2022**, the year it reached
1.0. It is governed in the open by maintainers from Spotify and other companies, with monthly releases
(this project uses **1.55**). Spotify also sells commercial add-ons (Spotify Portal and plugins); the
core framework stays free and vendor-neutral.

**Adoption.** It has become the most widely used open-source framework for internal developer portals:
thousands of organisations use it, with public adopters across retail, finance, travel, gaming and
government (for example Expedia, American Airlines, Zalando, Booking.com, HelloFresh and Siemens), and
it is the reference portal in the CNCF platform engineering community.

**Why it fits this project.** Backstage is a framework, not a finished product, which is exactly what an
enterprise platform needs: its scaffolder runs templates with custom actions and form fields (used here
for the Azure resource picker and the approval flow), its catalog tracks what each golden path creates,
and plugins connect it to GitHub, Kubernetes and Azure. Everything that is not portal logic (Azure
discovery, provisioning, approvals) lives in separate Python services, so the platform doesn't depend
on Backstage internals ([ADR-0001](docs/adr/0001-python-platform-services.md)).

## Why this project

Platform teams often build either a portal with no automation behind it, or a pile of pipelines with no developer-facing interface. This project aims to do both properly for a single use case:

- **Self-service with guardrails.** Developers choose from discovered, allowlisted Azure resources. They never type arbitrary IDs, and the server validates every selection again.
- **Durable, observable workflows.** Long-running Terraform and deployment work runs asynchronously, with persisted state, idempotency, retries and audit events. It never runs inside an HTTP request.
- **Least-privilege identities.** Discovery, provisioning, deployment and application runtime each use a separate identity, federated through OIDC where supported.
- **Honest status.** Repository creation, infrastructure provisioning and application deployment are reported as separate outcomes. A created repository does not count as a successful deployment.

The goal is one complete, enterprise-quality vertical slice rather than many unfinished templates.

## The first golden path

> A developer requests a secure **NestJS REST API** through Backstage. The platform creates a dedicated GitHub repository, provisions or reuses approved Azure infrastructure, and deploys the application to **Azure Kubernetes Service**.

The developer **submits everything in one Backstage form** first. Then the platform:

1. provisions the infrastructure, after **approval in the Backstage UI**
2. generates a dummy starter for the **chosen stack**, with a rendered Dockerfile, local Compose configuration and CI/CD
3. deploys it to the selected AKS cluster
4. **shares the URLs** on the Backstage entity page

The full step-by-step flow, with a sequence diagram, is in **[docs/developer-guide/golden-path.md](docs/developer-guide/golden-path.md)**.

The form collects:

Only the **name** and **owning team** are required. Everything else is a dropdown preselected with the
platform default; choose **Custom…** or **Create new…** only when an application needs something different
([form details](docs/developer-guide/golden-path.md#step-1-submit-everything-in-backstage)).

| Input | Notes |
|---|---|
| Application name and description | Validated against naming rules and checked for duplicates. Description is optional |
| Owner / owning team | Resolved from the Backstage catalog |
| Stack | Chosen from the available stacks. NestJS (TypeScript) is enabled; other stacks are listed as *coming soon* and added later as templates |
| Environment | `dev` initially |
| Azure subscription | **Create new** or **Select existing** |
| Resource group | **Create new** or **Select existing** |
| AKS cluster | **Create new** or **Select existing** |
| Container registry | **Create new** or **Select existing** |
| Kubernetes namespace | **Create new** or **Select existing** namespace owned by the same team |
| Runtime capability | Azure Storage or Key Vault: **Create new** or **Select existing**, accessed through Workload Identity |
| Endpoint host | Defaults to `<name>.<gateway domain>`, e.g. `orders-api.dev.xycorp.local`; served by the cluster's shared Gateway (App Routing Gateway API). No DNS of your own is needed: see [Reaching an application without your own domain](docs/operations/demo-environment.md#reaching-an-application-without-your-own-domain) |
| **High availability** | **Do you need HA?** Yes / No. The default is No in `dev` (Yes in a future `prod`). Choosing the non-default option requires a **reason and justification**, which is shown to the approver. See [High-availability option](#high-availability-option) |
| Repository visibility and deployment options | Limited to permitted values. **Public** is the default (see [Repository visibility](#repository-visibility)) |

Accepting every default completes the path with a single required text field.

### Create new or select existing

For every Azure resource, from the subscription down to the Storage account, the Backstage form shows two options. **Select existing** is the default, because most requests reuse infrastructure that already exists. The first golden path uses **Select existing** throughout.

```
Subscription        ( ) Create new        (•) Select existing
                    [ sub-idp-dev  ▼ ]   ← populated from azure-discovery

Resource group      ( ) Create new        (•) Select existing
                    [ rg-idp-apps-dev  (uksouth)  ▼ ]

AKS cluster         ( ) Create new        (•) Select existing
                    [ aks-idp-shared-dev  ▼ ]

Storage account     (•) Create new        ( ) Select existing
                    Name: storordersapidev           [validated as you type]
```

Each selection narrows the next one: the resource groups listed depend on the chosen subscription, and the clusters depend on the chosen resource group or subscription.

| | **Create new** | **Select existing** |
|---|---|---|
| Form input | Name field, pre-filled with a name that follows the naming convention | Dropdown filled from the discovery service. It shows only resources that are allowlisted, in an approved region and visible to the discovery identity |
| Server-side validation | Naming rules, global name availability (e.g. Storage), region and SKU allowlist, quota | The ID is re-resolved through `POST /v1/validate`, confirming it still exists, its type and region are correct, and it is eligible for this team and environment |
| Terraform | Generated as a `resource` block, tagged with owner, environment, application and `managed-by: idp-platform` | Generated as a `data` block. The platform only adds role assignments and never modifies or destroys the existing resource |
| Plan and approval | Shown as an addition in the plan summary; requires approval before apply | Shown as reuse. Role assignments still appear in the plan and require approval |
| Cleanup on failure or deletion | Can be removed by the controlled cleanup procedure | Never deleted by the platform |

Some resources have stricter rules when **Create new** is chosen:

| Resource | Create new behaviour |
|---|---|
| Subscription | Subscription vending through the `Microsoft.Subscription` alias API, in the platform stack `iac/platform/05-subscriptions`. It needs an Enterprise Agreement or Microsoft Customer Agreement billing scope and a separate vending identity. The new subscription is placed under the configured management group. |
| AKS cluster, container registry | Added to the shared platform stack (`iac/platform/20-shared-<env>`), not the application repository. The new cluster or registry becomes a shared, reusable target for later requests rather than a one-off for this application. |
| Resource group, namespace, Storage, Key Vault, managed identity | Provisioned from the application repository's Terraform, with the normal plan-and-approve flow in Backstage. |

**Platform-level resources follow the platform's own change process.** For a new subscription, AKS cluster or registry, the orchestrator opens a pull request in the platform repository that adds the definition. The platform team reviews it, `platform-plan.yml` plans it, and `platform-apply.yml` applies it behind the `platform` GitHub environment's **required reviewers**. Backstage shows this as the `PLATFORM_PROVISIONING` stage, with links to the pull request and the run, but **doesn't approve it**: the portal never approves changes to its own infrastructure. Once applied, the request continues with the new resource as an existing one.

**Create new is implemented for every resource in milestone 1**, but the form only offers what the selected subscription can support. Discovery reports these capabilities (`GET /v1/subscriptions/{id}/capabilities`), and unsupported options are disabled with the reason, for example:
- *New subscription:* disabled unless the billing account is EA or MCA. A free or pay-as-you-go account can't vend subscriptions.
- *New AKS cluster:* disabled if the regional vCPU quota can't fit it.
- *High availability:* rejected if the cluster doesn't span at least two zones.

The first demo uses **Select existing** on a **free Azure subscription**; see [docs/operations/demo-environment.md](docs/operations/demo-environment.md).

If discovery returns nothing to select, for example because the identity lacks `Reader` or nothing is allowlisted, the form disables **Select existing** and shows the reason instead of an empty dropdown.

### High-availability option

The form asks **"Do you need high availability?"** so the cost and complexity of HA is a deliberate, recorded choice ([ADR-0004](docs/adr/0004-availability-tier-option.md)).

| | Standard | High availability |
|---|---|---|
| Replicas / autoscaling | 1 / off | ≥2 / HPA 2–5 |
| Disruption budget, zone spreading | — | PDB `minAvailable: 1`, spread across availability zones |
| New Storage account | LRS | ZRS |
| When a justification is needed | Opting out where HA is the default (future `prod`) | Opting in where Standard is the default (`dev`) |

- The server checks that the selected cluster has a node pool spanning at least two zones. It rejects missing or placeholder justifications, and it warns when HA is paired with existing LRS storage.
- The approval card shows an HA badge, the reason, the justification, the SLO target and the cost difference, if configured.
- The decision is stored in the audit log and as catalog annotations.

## Architecture

Animated overview of the proposed solution, including Azure Key Vault secret delivery:

![Proposed Internal Developer Portal architecture](docs/assets/proposed-platform.gif)

```mermaid
flowchart LR
    Dev([Developer]) --> Portal

    subgraph Backstage["Backstage · TypeScript (built-ins + thin bridges)"]
        Portal[Frontend<br/>Catalog · Scaffolder · TechDocs<br/>+ resource picker · status card]
        Portal --> API[Backend<br/>built-in plugins]
        API --> Bridge[idp-platform-backend<br/>bridge plugin]
    end

    subgraph Python["Platform services · Python (FastAPI)"]
        Disc[azure-discovery]
        Orch[provisioning-orchestrator<br/>API + worker]
        Orch --> DB[(PostgreSQL<br/>workflow state + audit)]
        Orch -- validate --> Disc
        Disc --> Policy[/policies<br/>allowlists/]
    end

    Bridge -- service token + user --> Disc
    Bridge -- service token + user --> Orch
    API -- publish:github --> GH
    Disc -- read-only --> ARG[Azure Resource Graph / ARM]
    Orch -- GitHub App --> GH[GitHub<br/>repo + Actions]
    GH -- webhooks --> Orch
    GH -- OIDC --> TF[Terraform<br/>plan / apply]
    TF --> Azure[(Azure: RG, UAMI,<br/>Storage / Key Vault, ACR)]
    GH -- OIDC --> AKS[Shared AKS cluster]
    AKS -- Workload Identity --> Azure
```

### Components

| Component | Responsibility |
|---|---|
| **Software Catalog** | Ownership, metadata and discovery of services, including generated applications |
| **Scaffolder + Software Templates** | Self-service request form and repository generation, using the built-in `fetch:template`, `publish:github` and `catalog:register` actions |
| **`idp-platform-backend`** (TypeScript, thin bridge) | One small backend plugin. It forwards discovery and orchestrator calls to the Python services with the signed-in user's identity and a service token. It also adds two scaffolder actions, `idp:request:submit` and `idp:request:repository-created`. It contains no business logic |
| **`idp-platform`** (TypeScript, thin frontend) | A scaffolder field extension that provides the **Create new / Select existing** resource picker, the **Provisioning** entity tab (stage timeline, URLs), and the **Approvals** page. All of them only call the bridge |
| **`azure-discovery`** (Python, FastAPI) | Standalone, read-only REST service. It lists the existing subscriptions visible to the discovery identity (the same ones shown in the Azure portal), then their resource groups, AKS clusters, registries and data services, using ARM and Azure Resource Graph. Results are filtered against the policy allowlists before they are returned |
| **`provisioning-orchestrator`** (Python, FastAPI + worker) | Durable asynchronous workflow engine. It owns request validation, the state machine, idempotency, GitHub workflow dispatch, approval tracking, retries, cleanup and the audit log, with state stored in PostgreSQL |
| **Policies** | Allowlists for subscriptions, regions, environments, clusters, resource types and operations, enforced on the server |
| **TechDocs** | Architecture, onboarding, service and operations documentation |
| **GitHub integration** | Repository creation, workflow dispatch, environment approvals and run status |

**Split between Backstage and Python** (see [ADR-0001](docs/adr/0001-python-platform-services.md); service boundaries, communication, data ownership, deployment and resilience are described in [docs/architecture/microservices.md](docs/architecture/microservices.md)):

- **Backstage (TypeScript)** provides what it already does well: the catalog, scaffolder, TechDocs, sign-in, permissions and the GitHub integration. Custom TypeScript is limited to one bridge backend plugin and one small frontend plugin, built on the new backend system and its extension points.
- **Python (FastAPI)** holds all platform business logic: Azure discovery, policy evaluation and workflow orchestration. It uses the official Azure SDKs for Python and can be tested and released independently of Backstage.
- The browser only ever talks to Backstage. The Python services are reachable only from the Backstage backend and from each other (the orchestrator calls discovery). Two orchestrator paths are reachable from GitHub: webhooks (HMAC-verified) and Actions callbacks (verified with GitHub OIDC tokens).

### Request flow

1. **Submit.** The developer fills in the whole scaffolder form. The resource pickers load their options from the discovery service through the bridge.
2. **Validate.** `idp:request:submit` sends the request to the orchestrator, using the scaffolder task ID as the idempotency key. The orchestrator re-validates every selection through the discovery service and the policies. It then returns a request ID, or rejects the request before any repository exists. If the request asks for a new subscription, AKS cluster or registry, the orchestrator first raises the platform pull request and waits for it to be applied (`PLATFORM_PROVISIONING`).
3. **Repository.** The built-in `publish:github` creates the repository with **infrastructure code only**, and `catalog:register` registers it. `idp:request:repository-created` reports it to the orchestrator, and the scaffolder task finishes.
4. **Infrastructure.** The orchestrator dispatches the validate and plan workflows. The apply job is held until a reviewer **approves in the Backstage UI** (see [Approval in Backstage](#approval-in-backstage)). It then applies the saved plan.
5. **Application.** Once the infrastructure is ready, the orchestrator opens a pull request that adds the starter for the chosen stack: source, tests, a rendered Dockerfile, local Compose configuration, checkout instructions and CI/CD. Developers can run the dummy API without Azure credentials after the pull request merges.
6. **Deploy.** CI builds, scans and pushes the image. The deploy workflow installs the Helm chart on AKS, then smoke-tests the endpoint.
7. **Report.** The orchestrator follows every step through `workflow_run`, `deployment_status`, `deployment_protection_rule` and `pull_request` webhooks, plus Actions callbacks,, with periodic polling to catch lost events. The application, repository, workflow, registry, Azure and Backstage URLs appear on the entity page and in a Backstage notification.

### Approval in Backstage

Reviewers approve infrastructure changes in the Backstage UI. GitHub enforces the decision:

- Each infrastructure environment (for example `dev-infra`) has a **custom deployment protection rule** owned by the orchestrator's GitHub App. GitHub holds the apply job until the orchestrator releases it.
- Approvers get a Backstage notification. On the **Approvals** page or the request's *Provisioning* tab, they see the plan summary (added, changed, destroyed, reused), the policy and security results, and links to the full plan, then click **Approve** or **Reject**.
- Before releasing the job, the orchestrator checks:
  - the `idp.request.approve` permission
  - that the approver is not the requester
  - that the approval matches the **exact plan hash**, so a changed plan needs a new approval
  - that the request has not already been decided
- Re-running the workflow from GitHub does not bypass approval, and every decision is written to the audit log.

### Provisioning orchestrator service

The orchestrator is a FastAPI API plus a separate worker process, both sharing one PostgreSQL database:

- **State machine.** Each request is a row with an explicit state (see [Workflow lifecycle](#workflow-lifecycle)). Every state change goes through one transition function that rejects illegal transitions.
- **Durable jobs.** The worker claims pending steps with `SELECT ... FOR UPDATE SKIP LOCKED`, so several workers or a restarted worker never process the same step twice. In-flight requests resume after a restart.
- **Idempotency.** Each request has an idempotency key and each step has a deduplication key. A duplicate submission returns the existing request. Repeated webhooks for the same run are ignored.
- **Approvals.** Decisions are made in the Backstage UI and enforced through GitHub custom deployment protection rules (see [Approval in Backstage](#approval-in-backstage)). The orchestrator holds the request in `AWAITING_APPROVAL` and binds each approval to a plan hash.
- **No Azure write access.** The orchestrator only uses a GitHub App token. All Azure changes are made by Terraform in GitHub Actions using OIDC identities.
- **Audit.** An append-only `audit_events` table records who requested, who approved, which workflow run produced which result and what changed. Secrets and sensitive Terraform output are never stored.

Endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/requests` | Submit and validate a request (idempotent) |
| `GET` | `/v1/requests/{id}` | Current state, stage history and diagnostics |
| `POST` | `/v1/requests/{id}/repository` | Record the created repository and start the asynchronous workflow |
| `GET` | `/v1/approvals?status=pending` | Pending approvals visible to the caller |
| `POST` | `/v1/requests/{id}/approval` | Approve or reject the current plan (plan hash, comment) |
| `POST` | `/v1/requests/{id}/cancel` | Cancel a request that has not started applying |
| `GET` | `/v1/requests/{id}/starter` | The stack's starter application for the new repository's first commit |
| `POST` | `/v1/requests/{id}/retry` | Continue a failed request from the step where it stopped |
| `POST` | `/v1/requests/{id}/cleanup` | Start controlled cleanup of resources the platform created |
| `POST` | `/v1/webhooks/github` | Receive GitHub events (HMAC-verified) |
| `POST` | `/v1/callbacks/actions` | Receive plan summaries, plan hashes and outputs from workflow runs (GitHub OIDC-verified) |
| `GET` | `/healthz`, `/readyz` | Health checks |

### Azure discovery service

Discovery runs as a separate Python service so it can use the official Azure SDKs for Python (`azure-identity`, `azure-mgmt-resource-subscriptions`, `azure-mgmt-resourcegraph`). It can also be developed, tested and deployed independently of the Backstage release cycle.

Endpoints (all read-only):

| Method | Path | Returns |
|---|---|---|
| `GET` | `/healthz` | Liveness |
| `GET` | `/readyz` | Readiness, including whether an Azure credential can be acquired |
| `GET` | `/v1/subscriptions` | Enabled subscriptions visible to the discovery identity, filtered by the allowlist |
| `GET` | `/v1/subscriptions/{id}/capabilities` | Which **Create new** options this subscription supports, with reasons (billing account type for vending, regional vCPU quota, availability zones) |
| `GET` | `/v1/subscriptions/{id}/resource-groups` | Allowlisted resource groups in an approved region |
| `GET` | `/v1/subscriptions/{id}/aks-clusters` | Approved shared AKS clusters, including whether Workload Identity and the OIDC issuer are enabled, and node pool zones and node counts (for HA eligibility) |
| `GET` | `/v1/subscriptions/{id}/container-registries` | Approved container registries |
| `GET` | `/v1/subscriptions/{id}/resources?type=…` | Allowlisted Storage accounts and Key Vaults available for reuse |
| `POST` | `/v1/validate` | Server-side eligibility check for a full selection set, used by the orchestrator |

Design rules:

- Authentication uses `DefaultAzureCredential`: Workload Identity on AKS, and `az login` or environment credentials for local development. No client secrets are stored in the repository.
- The identity has only the `Reader` role. The service never calls write operations.
- Resource Graph results are paginated using skip tokens. Throttling (`429`) and transient errors are retried with backoff. Permission errors and missing resources produce typed error responses, never empty success responses.
- Only the Backstage bridge and the orchestrator call the service, using service-to-service authentication. Discovery results are suggestions only: the orchestrator re-validates every submitted ID through `/v1/validate` before acting on it.

**Microsoft Graph** is used only for supported Microsoft Entra operations. It does not provision Azure infrastructure; Terraform does.

### Infrastructure lifecycles

- **Shared platform infrastructure** (AKS cluster, container registry, Terraform state storage, platform identities) has its own lifecycle and is managed under `iac/`.
- **Application infrastructure** (namespace, user-assigned managed identity, federated credential, Storage account or Key Vault, role assignments) lives in each application's repository.
- When a request chooses **Create new** for an AKS cluster or registry, the new resource is built through the shared platform lifecycle and becomes reusable. It is never a single-application cluster. The platform never destroys shared resources automatically when an application deployment fails.

## Features

The target feature set for the first milestone:

- Backstage portal with catalog, scaffolder, TechDocs and GitHub integration
- NestJS golden-path template with a real sample business endpoint, validation, health endpoints and tests
- **Create new** or **Select existing** for every Azure resource (subscription, resource group, AKS, ACR, namespace, Storage/Key Vault), with dynamic, server-validated selections. Options the subscription can't support (billing type, quota, zones) are disabled with the reason
- **High-availability option** with a justification when deviating from the environment default
- Durable workflow with explicit states, persistence, restart recovery, idempotency and duplicate detection
- Terraform plan, security and policy checks, and plan review before apply
- Approval in the Backstage UI for infrastructure changes, enforced by GitHub custom deployment protection rules and bound to the exact plan
- Container build, tests, dependency and image vulnerability scanning, and push to an approved registry
- Hardened Helm deployment to a shared AKS namespace
- Microsoft Entra Workload Identity for credential-free access to Azure Storage or Key Vault
- Choice of application stack from a stack registry (NestJS first)
- Per-stage status, workflow history, actionable diagnostics and shared URLs (app, docs, repository, workflows, image, Azure) in Backstage
- Audit events covering who requested, who approved, what changed and which workflow ran

## Workflow lifecycle

The Python orchestrator models each request as a state machine persisted in PostgreSQL:

```mermaid
stateDiagram-v2
    [*] --> REQUESTED
    REQUESTED --> VALIDATING
    VALIDATING --> REPOSITORY_CREATED
    VALIDATING --> PLATFORM_PROVISIONING : new subscription / AKS / ACR
    PLATFORM_PROVISIONING --> REPOSITORY_CREATED
    PLATFORM_PROVISIONING --> FAILED
    VALIDATING --> FAILED
    REPOSITORY_CREATED --> INFRASTRUCTURE_PLANNED
    REPOSITORY_CREATED --> FAILED : validate / plan failed
    REPOSITORY_CREATED --> CANCELLED : cancelled
    INFRASTRUCTURE_PLANNED --> AWAITING_APPROVAL
    INFRASTRUCTURE_PLANNED --> CANCELLED : cancelled
    AWAITING_APPROVAL --> PROVISIONING : approved in Backstage
    AWAITING_APPROVAL --> CANCELLED : rejected / cancelled
    PROVISIONING --> INFRASTRUCTURE_READY
    PROVISIONING --> FAILED
    INFRASTRUCTURE_READY --> APPLICATION_BUILDING
    APPLICATION_BUILDING --> DEPLOYING
    APPLICATION_BUILDING --> FAILED
    DEPLOYING --> SUCCEEDED
    DEPLOYING --> FAILED
    FAILED --> CLEANUP_PENDING : cleanup requested
    CANCELLED --> CLEANUP_PENDING
    CLEANUP_PENDING --> CLEANED_UP
    SUCCEEDED --> CLEANUP_PENDING : cleanup requested
    SUCCEEDED --> [*]
    CLEANED_UP --> [*]
```

| Stage | What happens |
|---|---|
| 1. Validate | Name, owner, environment, subscription, cluster, permissions and allowlisted selections are checked on the server |
| 2. Discover | The Python discovery service uses Azure Resource Graph and ARM to confirm each resource's existence, type, region and eligibility, using a read-only identity |
| 2a. Platform provisioning | *Only for a new subscription, AKS cluster or registry:* a platform pull request, planned and applied behind the `platform` environment reviewers |
| 3. Repository | The built-in scaffolder action `publish:github` creates one GitHub repository per request, initially containing Terraform, the Helm chart, the infrastructure workflows, catalog metadata and docs |
| 4. Validate infra | `terraform fmt`/`init`/`validate`, security scanning, policy checks and Helm linting run; the plan is retained and summarised |
| 5. Provision | After approval in Backstage, the saved plan is applied and resource readiness and identity configuration are verified |
| 6. Generate and build | A pull request adds the application for the chosen stack (source, tests, Dockerfile, CI/CD). Tests run, and the image is built, scanned and pushed to the approved registry |
| 7. Deploy | Helm deploys to the approved namespace, then rollout, health and the endpoint are verified |
| 8. Secure access | The application reaches Storage or Key Vault through a user-assigned managed identity and Workload Identity |
| 9. Register and report | The catalog entity shows the repository, environment, provisioning, deployment, health, history and all shared URLs |

Durability guarantees:

- State and execution metadata are persisted in PostgreSQL. In-flight workflows resume after a restart of Backstage or the orchestrator.
- Idempotency keys prevent duplicate repositories, and repeated callbacks are ignored.
- An approved plan is applied at most once.
- A failed deployment can never be marked as succeeded.
- Partial failures report which resources were created and point to a controlled recovery or cleanup procedure.
- Secrets, tokens and sensitive Terraform output are never written to logs or the audit trail.

## Repository visibility

Generated repositories are created **public** by default. The design depends on GitHub features that work on public repositories on every plan: branch protection, environments and custom deployment protection rules.

If you later make a generated repository private:

| Plan | What happens |
|---|---|
| Enterprise Cloud | Everything keeps working. |
| Team / Pro | Approval in Backstage still works, but GitHub can no longer hold the job. The apply workflow must check the approval with the orchestrator, and the Azure federated credential must trust only the infrastructure environment. This is weaker, documented fallback. |
| Free | Environments and protection rules are not enforced. Don't run the flow again on that repository. It is suitable only as an archived reference. |

For a public demo, keep the platform repository public. Keep one generated example public and **archived** (read-only) so others can browse the generated output. Then follow [docs/operations/cleanup.md](docs/operations/cleanup.md) to remove Azure resources. GitHub plan features change over time, so check GitHub's current plan documentation.

## Identity and security model

| Identity | Scope | Auth |
|---|---|---|
| **Discovery** (used by `azure-discovery`) | Read-only (`Reader`) on approved subscriptions | Workload Identity on AKS, `az login` locally |
| **Backstage** (used by `backstage`) | No Azure resource access. Reads only its own Key Vault secrets, requests tokens to call the platform services, and signs in to PostgreSQL | Workload Identity |
| **Orchestrator** (used by `provisioning-orchestrator`) | GitHub App installation on the generated repositories (Actions and Deployments write, to dispatch workflows and answer protection rules; Contents, Pull requests and Workflows write, for the application pull request, which adds `.github/workflows/` files) and on the platform repository (Pull requests and Contents write, to raise platform change requests). No Azure resource access: it reads only its own Key Vault secrets and signs in to PostgreSQL | Workload Identity, plus the GitHub App private key from Key Vault through the Secrets Store CSI driver |
| **Subscription vending** (only when a new subscription is requested) | Subscription creator on the billing scope, and management group placement | GitHub OIDC federated credential, used by a platform-team-approved workflow |
| **Platform** (used by `platform-plan.yml` and `platform-apply.yml`) | Creates and changes shared platform infrastructure in `iac/platform`: AKS, ACR, Key Vault, PostgreSQL, DNS, identities and their role assignments. Plans on pull requests use a separate read-only plan identity | GitHub OIDC federated credential, `platform` environment with required reviewers |
| **Platform deployment** (used by `images.yml` and `deploy-platform.yml`) | Pushes platform images to ACR and deploys to the `idp-platform` namespace only | GitHub OIDC federated credential |
| **Terraform provisioning** | Custom `IDP App Provisioner` role (resource groups, identities, Storage, Key Vault only) plus RBAC Administrator limited by an ABAC condition to the allowlisted data roles; trusted only through the platform's reusable Terraform workflow ([ADR-0005](docs/adr/0005-reusable-workflows-and-ci-identity.md)) | GitHub OIDC federated credential (customised subject with `job_workflow_ref`) |
| **Deployment** | Push to the approved ACR and deploy to the application's namespace only | GitHub OIDC federated credential |
| **Application runtime** | User-assigned managed identity with access only to its own Storage account or Key Vault | Microsoft Entra Workload Identity |

Security principles:

- No single administrator identity is used for all operations.
- OIDC federation is preferred over long-lived client secrets.
- Credentials, certificates, Terraform state, sensitive plans, kubeconfig files and application secrets are never committed.
- **Secret management:** Workload Identity and OIDC replace most credentials. The few remaining secrets (GitHub App keys, webhook secret, session secret) live in Key Vault, with RBAC per secret, and reach pods through the Secrets Store CSI driver as read-only files, without Kubernetes `Secret` objects. Rotation is documented and scanning is enforced. See [docs/security/secret-management.md](docs/security/secret-management.md).
- Terraform state is stored in an Azure Storage backend with Entra ID-only authentication (no storage account keys), separate `platform` and `apps` containers with separate access, versioning, soft delete, a delete lock and blob-lease locking. Local state is used only for isolated tests and the one-time bootstrap ([ADR-0002](docs/adr/0002-terraform-structure.md)).
- GitHub Actions are pinned to reviewed commit SHAs and use least-privilege `permissions:`. Protected environments gate apply and deploy.
- Untrusted pull request code never runs with privileged credentials.
- The platform never runs user-supplied Terraform, shell scripts or pipeline definitions.
- Containers run as non-root with a read-only root filesystem where possible, drop all capabilities, use the `RuntimeDefault` seccomp profile, and set resource requests and limits.

The secrets design is in [docs/security/secret-management.md](docs/security/secret-management.md). The exact role assignments for each identity will be listed in `docs/security/permissions.md` (Phase 6).

## Repository layout

The platform monorepo, grouped by area (only project-wide files at the root):

```
azure-backstage-goldenpath/
├── README.md  IMPLEMENTATION_PLAN.md  COMPATIBILITY.md
├── .github/
│   ├── workflows/                   # platform CI/CD + reusable golden-path workflows (ADR-0005)
│   └── CODEOWNERS
├── portal/                          # Backstage 1.55 (Node workspace)
│   ├── packages/app/                #   frontend
│   ├── packages/backend/            #   backend (new backend system) + permission policy
│   ├── plugins/idp-platform*/  #   thin bridge, UI and shared types
│   ├── catalog/                     #   org and platform entities
│   └── app-config*.yaml
├── services/                        # Python (uv workspace), all platform logic
│   ├── libs/idp-common/        #   auth, secrets, logging, OTel
│   ├── azure-discovery/src/azure_discovery/
│   └── provisioning-orchestrator/src/provisioning_orchestrator/  (+ migrations/)
├── templates/applications/nestjs/   # golden path: template.yaml, skeleton/, application/
├── iac/
│   ├── modules/                     # reusable, versioned Terraform modules
│   └── platform/                    # 00-bootstrap, 05-subscriptions, 10-identities,
│                                    #   20-shared-dev, 30-cluster-config
├── policies/                        # allowlist.yaml + Rego (terraform/, helm/)
├── deploy/
│   ├── charts/                      # backstage, azure-discovery, provisioning-orchestrator
│   └── local/                       # docker-compose.yml, .env.example, init SQL
├── scripts/                         # ci/, dev-secrets.sh, configure-github-oidc.sh, SQL grants
└── docs/                            # adr/, architecture/, developer-guide/, operations/, security/
```

Generated application repositories are always separate from this platform repository.

## Generated application repository

Each request produces one self-contained repository that the application team owns. The tree below
shows the final layout after the application pull request merges; the first commit already holds
the infrastructure and the starter application (source, tests, Dockerfile, Compose, README), and the
pull request adds the CI/CD workflows and the Helm values filled with the infrastructure outputs. NestJS is the currently enabled technology; additional backend and frontend
templates are implemented and await validation before enablement.

```
<application-name>/
├── src/                     # NestJS app: REST endpoints, config, validation, health
├── test/                    # unit + integration test structure
├── infra/terraform/         # one root module, see ADR-0002
│   ├── main.tf  variables.tf  outputs.tf  providers.tf  versions.tf
│   ├── .terraform.lock.hcl    # pending generation and validation
│   └── environments/dev/
│       ├── backend.hcl      # state location only
│       └── terraform.tfvars # rendered from the Backstage form
├── deploy/helm/application/
│   ├── Chart.yaml  values.yaml  values-dev.yaml
│   └── templates/           # Deployment, Service, ServiceAccount, HTTPRoute; HPA + PDB for HA
├── .github/workflows/
│   ├── terraform-validate.yml
│   ├── terraform-plan.yml
│   ├── terraform-apply.yml
│   ├── application-ci.yml
│   └── application-deploy.yml
├── Dockerfile
├── docker-compose.yml        # local dummy API; no Azure credentials
├── .gitignore  .dockerignore
├── catalog-info.yaml
├── docs/
└── README.md
```

Application code and infrastructure live in the same repository. The infrastructure definitions and workflows are generated before any provisioning runs.

The orchestrator renders the selected stack's application source, tests, Dockerfile, Compose file,
README and workflow callers from `templates/applications/<stack>/application/`. It supplies validated
request metadata and non-sensitive infrastructure outputs. NestJS's local configuration explicitly
uses an in-memory store, with temporary data, loopback-only access and adjustable resource limits.
Deployed Helm values select the approved Azure capability separately. A successful local dummy API
does not establish successful provisioning or deployment.

Python, portal and generated application dependency lockfiles are not committed yet. Image sizes,
memory use and the developer checkout experience require validation on the target system.

The Terraform `.tf` files are the same in every generated repository. The scaffolder renders only `terraform.tfvars`, and the modules come from this repository's `iac/modules/`, pinned to a version tag. Existing resources are read through `data` sources and never modified or destroyed. See [ADR-0002](docs/adr/0002-terraform-structure.md).

## Prerequisites

These are the prerequisites. Versions were checked on 2026-10-10; the full matrix, constraints and risks are in **[COMPATIBILITY.md](COMPATIBILITY.md)**.

**Local development**

- The container path needs Docker Engine/Desktop with Linux containers and Compose v2; Node.js and
  Python are installed inside the build stages. The host-development and validation paths use the
  tools below. None of these environments has been started for the current changes.
- **WSL2 (Ubuntu) or a dev container on Windows.** Backstage needs a Unix-like OS.
- Node.js **24 LTS** and Yarn **4.13** (as pinned by Backstage 1.55)
- Python **3.14** and [uv](https://docs.astral.sh/uv/) **0.13** for the platform services
- PostgreSQL (run through Docker Compose for local development)
- Azure CLI **≥ 2.86** (`az login`) for running discovery locally against real subscriptions
- Docker
- Terraform **1.16**, TFLint **0.64**, Checkov **3.3**, Conftest **0.71** and Trivy **0.75** (checksum-verified)
- Helm **4.3**, kubectl **1.36** and kubelogin **0.2.21**
- kind **0.33** with a `v1.36.x` node image, matching AKS, for chart testing

**Live Azure and GitHub execution**

- An Azure subscription with permission to create role assignments and federated credentials
- A shared AKS **1.36** cluster with the OIDC issuer, Workload Identity, the managed Gateway API CRDs and the App Routing Gateway API implementation enabled, plus a DNS zone for application endpoints ([ADR-0003](docs/adr/0003-ingress-gateway-api.md))
- An Azure Container Registry, a Key Vault (with the AKS Key Vault secrets provider add-on) and an Azure Database for PostgreSQL flexible server
- An Azure Storage account for Terraform state
- For HA requests, a user node pool spanning at least two availability zones
- The first demo runs on a **free Azure subscription**. See [docs/operations/demo-environment.md](docs/operations/demo-environment.md) for its limits, sizing and preparation
- A GitHub organisation, a GitHub App for Backstage (repository creation) and a separate GitHub App for the orchestrator (workflow dispatch, webhooks, application pull requests), registered as a custom deployment protection rule provider
- Microsoft Entra app registrations or managed identities for each identity in the [identity model](#identity-and-security-model)

## Local development

The platform runs locally in Ubuntu (WSL2) with Docker Engine: Backstage, Azure discovery, the
orchestrator API and worker, schema migrations and PostgreSQL, with guest sign-in and mock Azure and
GitHub. It's independent of other projects in the same Ubuntu. Details are in
[deploy/local/README.md](deploy/local/README.md).

```powershell
.\scripts\local\platform.ps1 up     # then open http://localhost:7007
.\scripts\local\platform.ps1 e2e    # golden-path check through the running platform
.\scripts\local\platform.ps1 down
```

Inside Ubuntu the same is `make up`, `make e2e`, `make down`; `make help` lists every target,
including `make test`, `make test-integration` and `make portal-test` in throwaway containers.

For running application processes on the host instead, start only PostgreSQL:

```bash
# PostgreSQL (one database + role per service)
cd deploy/local && cp .env.example .env && docker compose up -d postgres && cd ../..

# Python platform services, local mode: mock Azure + mock GitHub, static dev token (one terminal each)
cd services && uv sync --all-packages
export IDP_AUTH_MODE=static IDP_DEV_SERVICE_TOKEN=dev-only-change-me
DISCOVERY_AZURE_MODE=mock DISCOVERY_POLICY_FILE=../policies/allowlist.yaml \
  uv run uvicorn azure_discovery.main:create_app --factory --port 8001
export ORCHESTRATOR_DATABASE_URL=postgresql+psycopg://orchestrator:dev-only-not-a-secret@localhost:5432/orchestrator
export ORCHESTRATOR_GITHUB_MODE=mock DISCOVERY_BASE_URL=http://localhost:8001
uv run --package provisioning-orchestrator alembic -c provisioning-orchestrator/alembic.ini upgrade head
uv run uvicorn provisioning_orchestrator.main:create_app --factory --port 8002
uv run orchestrator-worker

# Backstage (WSL2), in another terminal
cd portal && corepack enable && yarn install && yarn dev

# Tests
(cd services && uv run pytest)
(cd portal && yarn tsc && yarn test:all)
conftest verify -p policies/terraform
```

Mock adapters are only for local development and isolated tests. Live integrations are real code paths, enabled through configuration in `app-config.local.yaml`, which is never committed.

## Testing strategy

| Level | Coverage |
|---|---|
| Unit (Python) | Request validation, policy decisions, state transitions, error handling |
| Orchestrator integration | FastAPI API and worker against a real PostgreSQL (Testcontainers): idempotency, concurrent workers, restart recovery, webhook replay |
| Bridge (TypeScript) | Backstage bridge plugin and scaffolder actions against a stubbed orchestrator |
| Discovery service | pytest + FastAPI `TestClient` with a mocked Azure SDK: pagination, permission errors, missing resources, throttling, allowlist filtering |
| Infrastructure | `terraform fmt -check`, `init`, `validate`, security scanning, policy tests |
| Helm | `helm lint`, template rendering, schema validation, Conftest rules on the rendered chart (no `Secret` objects, no secret-like env values), kind-based install test |
| Contract | The bridge's generated TypeScript client against the Python services' OpenAPI documents |
| Security | gitleaks and GitHub secret scanning, Trivy image and dependency scans, CodeQL |
| Capabilities and HA | Disabled options and reasons (billing type, quota, zones); HA justification rules and zone checks |
| Application | NestJS unit tests, health checks, container build test |
| End to end | Complete golden path with mocked Azure and GitHub |
| Resilience | Retry safety, duplicate requests, interrupted workflows, unauthorized selections, failed deployments |
| Live (opt-in) | Real Azure integration tests, run only when explicitly configured |

## Implementation status

| Phase | Scope | Status |
|---|---|---|
| 1 | Repository inspection, gap analysis, architecture documentation | ✅ Done (design documents, see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)) |
| 2 | Backstage portal, catalog, scaffolder, local dev environment | ✅ Verified: Backstage 1.55 on AKS over HTTPS with GitHub sign-in; `make up` and `make e2e` locally |
| 3 | NestJS golden path: Python orchestrator, repository generation, Terraform validation, workflow execution, Helm deploy, status reporting | ✅ Verified 2026-10-17: `orders-api` from the Backstage form to a running deployment on AKS |
| 4 | Azure discovery service (Python FastAPI) and secure identity integration | ✅ Verified: runs on AKS with Workload Identity and fills the form's Azure pickers |
| 5 | Real Azure provisioning, approvals, state management, failure recovery, cleanup | ✅ Verified: apply after approval in Backstage, remote state, Retry, and Clean up (destroy after approval) |
| 6 | Full automated testing, security checks, documentation, reproducible demo | 🟡 CI (lint, types, tests, policies, Trivy, CodeQL, gitleaks) runs on every pull request; the demo ([#27](https://github.com/nixvarghese01/azure-backstage-goldenpath/issues/27)) and the other starters ([#26](https://github.com/nixvarghese01/azure-backstage-goldenpath/issues/26)) are next |

The seven other starters (FastAPI, Go, ASP.NET Core, Spring Boot, Next.js, React/Vite, Vue/Vite) render,
build and pass CI; they stay disabled until each has had a run on the target system like `orders-api`.

### Definition of done for milestone 1

✅ Met on 2026-10-17 (`orders-api`). The first milestone is complete when a developer can:

1. Start the workflow in Backstage.
2. Receive a dedicated GitHub repository containing the application and infrastructure code.
3. Validate and approve the infrastructure plan.
4. Provision or reuse the configured infrastructure.
5. Deploy the application to AKS.
6. Reach the application at its configured endpoint.
7. See accurate status for each stage in Backstage.

## Roadmap

Next, now that the NestJS golden path works:

- Enable the other application starters (Next.js, FastAPI, .NET, Go, Spring Boot, React, Vue) after a target-system run each ([#26](https://github.com/nixvarghese01/azure-backstage-goldenpath/issues/26))
- Additional environments (test, prod) with stricter approvals
- **Monitoring and observability:** Prometheus and Grafana in the cluster (dashboards and alerts as code, `/metrics` on every service and generated app), sized for the Free Trial ([#107](https://github.com/nixvarghese01/azure-backstage-goldenpath/issues/107))
- **AI assistance** through an external model API (GitHub Models by default; no model in the cluster), off by default and advisory only: form guidance, failure explanations with Retry/Clean up advice, plan summaries for approvers, docs Q&A ([#109](https://github.com/nixvarghese01/azure-backstage-goldenpath/issues/109))
- HTTPS for generated applications ([#101](https://github.com/nixvarghese01/azure-backstage-goldenpath/issues/101)) and an automated live smoke test of the golden path ([#103](https://github.com/nixvarghese01/azure-backstage-goldenpath/issues/103))
- NetworkPolicies, Gateway hardening (TLS policy, rate limiting through Application Gateway for Containers or the Istio add-on) and environment-specific controls
- Cost estimation integration, with configurable pricing assumptions and no hardcoded "free tier" claims

Installing a Helm chart successfully does not make it production-ready. Remaining production requirements will be tracked in `docs/operations/production-readiness.md`.

## Documentation

Repository documentation (TechDocs publication is unverified):

- [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md): proposed workflow, CI/CD workflow design and the detailed phased plan
- [`COMPATIBILITY.md`](COMPATIBILITY.md): component version compatibility plan
- [`docs/architecture/microservices.md`](docs/architecture/microservices.md): platform microservices architecture (Backstage, discovery, orchestrator)
- [`docs/security/secret-management.md`](docs/security/secret-management.md): secret inventory, Key Vault, delivery, rotation and incident response
- `docs/adr/`: Architecture Decision Records: [0001 Python platform services](docs/adr/0001-python-platform-services.md), [0002 Terraform structure](docs/adr/0002-terraform-structure.md), [0003 Ingress through the Gateway API](docs/adr/0003-ingress-gateway-api.md), [0004 High-availability option](docs/adr/0004-availability-tier-option.md), [0005 Reusable workflows and CI identity](docs/adr/0005-reusable-workflows-and-ci-identity.md)
- [`docs/operations/validation-checklist.md`](docs/operations/validation-checklist.md): how to validate the code, step by step
- [`deploy/local/README.md`](deploy/local/README.md): local microservice topology, lightweight defaults and optional full TechDocs image
- [`docs/adr/0006-container-delivery.md`](docs/adr/0006-container-delivery.md): container delivery and generated developer starter design
- [`docs/developer-guide/technology-stacks.md`](docs/developer-guide/technology-stacks.md): backend/frontend starter inventory and shared contracts
- [`docs/developer-guide/golden-path.md`](docs/developer-guide/golden-path.md): the end-to-end golden path, approval in Backstage and the shared URLs
- [`docs/operations/cleanup.md`](docs/operations/cleanup.md): cleanup and teardown
- [`docs/operations/troubleshooting.md`](docs/operations/troubleshooting.md): symptoms, causes and fixes, including Retry
- [`docs/operations/demo-environment.md`](docs/operations/demo-environment.md): running the first demo on a free Azure subscription
- [`docs/best-practice-vs-free-tier.md`](docs/best-practice-vs-free-tier.md): enterprise best practice vs. what this free-tier project does, why each deviation exists, and how to switch

## Contributing and security

- Contribution guidelines are in [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).
- Questions and help: [SUPPORT.md](SUPPORT.md). Roles and how decisions are made: [GOVERNANCE.md](GOVERNANCE.md).
- Please report vulnerabilities privately as described in [`SECURITY.md`](SECURITY.md). Do not open public issues for security problems.

## License

[MIT](LICENSE) © 2026 Nixon Varghese.
