# Changelog

Notable changes, newest first. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions: [Semantic Versioning](https://semver.org/). The newest `## [X.Y.Z]` section is the version a
merge into `main` releases (CONTRIBUTING.md "Releases").

## [Unreleased]

### Added
- **Portal:** Backstage 1.55 Internal Developer Portal with a golden-path template for a NestJS API
  (more starters behind switches), a minimal form with prefilled default-or-custom choices and examples,
  and an Azure resource picker that follows the Cloud Adoption Framework hierarchy (tenant, management
  group, subscription, resource group, resources). Works in a landing zone and on a free subscription.
- **Services:** azure-discovery (allowlisted Azure inventory through Resource Graph, or a mock) and the
  provisioning orchestrator (requests, approvals, GitHub App automation, Terraform plan and apply through
  Actions, opt-in self-approval for single-person dev demos).
- **Infrastructure:** Terraform stacks for state (00), identities and Key Vault (10), the shared dev
  platform with AKS, ACR and optional Azure PostgreSQL (20) and in-cluster configuration (30); versioned
  modules released as immutable `<module>/vX.Y.Z` tags.
- **Pipelines:** plan on pull requests with Checkov and Conftest, approved apply, provision and teardown,
  image release with scans, SBOM and build provenance, time-to-live teardown and a free-subscription
  cost guard. Identifiers are GitHub secrets; Azure sign-in is OIDC with immutable subjects.
- **Dev platform:** one AKS node, App Routing (Istio) Gateway API, Workload Identity, Secrets Store CSI,
  PostgreSQL in the cluster with passwords in Key Vault.
- **Local:** the whole platform in WSL Ubuntu with make targets.
- **Docs:** ADRs 0001-0009, operations guides (bootstrap record, Terraform state, demo environment,
  troubleshooting, validation checklist) and this changelog with a release workflow.

### Added
- **Retry a failed request** (Provisioning tab → Retry; `POST /v1/requests/{id}/retry`): continues where it
  stopped instead of requesting again. An orchestrator step that ran out of attempts runs again (e.g. after a
  missing GitHub App permission is granted); validation runs again; a failed plan or apply starts from a fresh
  plan that needs approval again; a failed application CI or deploy run re-runs its failed jobs. Runs a retry
  replaced no longer count for the reconciler; plan, apply and approval-release keys include the triggering run,
  so a re-plan with the same hash is applied and approved again.

### Changed
- **Starter application in the first commit:** a generated repository now holds the stack's source, tests,
  Dockerfile, Compose file and README from the start (new scaffolder action `idp:request:starter`, rendered
  by the orchestrator's `GET /v1/requests/{id}/starter` from the same stack templates). The application pull
  request after apply adds only the CI/CD workflows and the Helm values filled with the infrastructure outputs.
- **HTTPS for the portal and GitHub hooks:** cert-manager (v1.21.2) issues a Let's Encrypt certificate for the
  Gateway's stable Azure DNS name (HTTP-01 through the Gateway) and the Gateway serves it on an HTTPS listener.
  The certificate is kept in a dedicated Key Vault (10-identities) by a `tls-sync` Workload Identity: restored
  before cert-manager runs on a re-provision (Let's Encrypt allows 5 per week per name), backed up after
  issuance and renewals. The charts switch to https automatically once the listener has its certificate
  (`dns.tls: auto`) and redirect plain HTTP for the portal. Requests fit the 4-vCPU node (~30m CPU). The platform
  identity may manage federated credentials on the `tls-sync` identity (as on the service identities).
- **Pipelines:** `platform-provision` has a 48 h time-to-live and an `extend` action that keeps the
  running platform for `ttl_hours` from now without running Terraform.

### Fixed
- **Pipelines:** teardown of an already empty stack no longer fails the plan check (a plan with no
  resource changes), and a destroy that stops part-way (an AKS delete that times out) retries what is left.
- **Platform charts:** public hostnames are picked up automatically. `dns.mode: auto` (default) reads
  the Gateway at deploy time: its Azure DNS name (`<label>.<region>.cloudapp.azure.com`, the same across
  re-provisions, so the GitHub App URLs never change), else `<name>.<gateway-ip>.nip.io`. `domain` and
  `host` set an own name; `dns.tls` gives https URLs. Application hostnames in the allowlist follow the
  current Gateway IP at release.
- **Identities:** the read-only plan identity may fetch the AKS user kubeconfig (Cluster User Role on
  the AKS resource group), so the preview plan works once the cluster exists.
- **Portal:** served over plain HTTP (`dns.tls: false`), Backstage no longer sends the CSP directive
  `upgrade-insecure-requests`, which made browsers load its scripts over https and left a blank page.
- **Portal:** signed-in pages no longer crash over plain HTTP (`crypto.randomUUID is not a function`): the
  frontend polyfills `crypto.randomUUID`, which browsers offer only in secure contexts.
- **Portal:** the golden-path template is read from the branch that deployed the portal (develop for the
  dev platform) instead of `main`, which has no release yet, so the Create page lists it.
- **Portal:** the template form no longer crashes on open (`Cannot read properties of undefined (reading
  'mode')`): the Azure resource and availability pickers fill their defaults when the form starts them as `{}`.
- **Discovery:** the Azure resource picker lists the real tenant, subscription and resources again. On Python
  3.11+ `str()` of an Azure SDK enum gave `SubscriptionState.ENABLED`, so every subscription looked disabled and
  the form found no tenant. Form validation no longer throws on the picker's initial `{}`.
- **Golden path:** works with a personal GitHub account or an organization (`idp.githubOwnerType`: `user` or
  `organization`). For a personal account the repository is created with the signed-in user's GitHub token
  (new `IdpGithubAccess` field, kept as a template secret): a GitHub App installation can create repositories
  only in organizations, and GitHub answered `POST /user/repos` with "Rate Limit Exceeded". For an
  organization the platform's GitHub App creates it, as before. `idp.githubOwnerType` is declared in the frontend plugin's
  config schema, so the browser receives it.
- **Golden path:** generated repositories call the platform's reusable workflows at the platform ref (the
  branch that deployed the portal: develop for dev, main for releases) instead of `@main`, which has no release
  yet ("workflow was not found"). The same ref is the orchestrator's platform PR base. New `idp:workflow-refs`
  action for the untemplated skeleton workflows.
- **Golden path:** generated `terraform-validate`/`terraform-plan` grant `actions: read`: GitHub checks every job of a
  called workflow, so they failed at startup on the apply job's need. `scripts/ci/check-reusable-permissions.py`
  checks every generated caller against the reusable workflows in template CI.
- **Orchestrator:** sets each generated repository's OIDC subject template (`repository_owner_id`, `environment`,
  `job_workflow_ref`) before its first workflow, so Azure federation works in personal accounts too, where there
  is no organization-wide template.
- **Golden path:** the Terraform validate job runs in a `<env>-validate` environment (no Azure trust): with the
  environment in the OIDC subject, its orchestrator callback token was refused ("the claim 'environment' cannot be
  null"). The template creates it, and the reusable-permissions check now flags token requests without an environment.
- **Golden path (end-to-end review):** generated repositories get the variables the reusable workflows read
  (`AZURE_TENANT_ID`, `PROVISIONING_CLIENT_ID`, `DEPLOYMENT_CLIENT_ID`, `IDP_CALLBACK_URL`), which a personal
  account can't inherit from an organization; the state backend uses the real (suffixed) state account; the
  reusable workflows check out the platform's scripts and policies at the ref they are called at
  (`platform_ref`); `main` needs no review so the orchestrator can merge the application PR after CI;
  `CODEOWNERS` names the owner of a personal account; the provisioning identity may read the shared registries
  and the deployment identity; the form's unused "sample endpoint" and "OpenAPI" switches are gone.
- **Provisioning tab and cleanup:** repository and workflow links open GitHub (no `.git`), the Backstage link is
  the public URL (not the in-cluster `http://backstage:7007`), application links use the platform's scheme, and
  a cleanup explains its stage (with a link to Approvals when the destroy waits there). A cleanup whose run fails
  before reporting is now marked failed (webhook and reconcile), and **Retry clean up** restarts it.
  Reconciliation judges only a request's latest run, so a failed attempt that was re-run doesn't fail it.
- **Cleanup removes the app from the catalog for good:** the orchestrator deletes the location the scaffolder
  registered, then the entity (before, Backstage read the entity back from its location).
- **New repositories' workflows:** GitHub can skip registering the workflows of a repository's first push (the
  first dispatch then failed with 404). "Start provisioning" waits for them and, if any is still missing,
  re-commits that file with the requester's token so GitHub registers it.
- **Orchestrator:** a requester's retry supersedes their earlier request for the same application while it has
  no repository yet (a scaffolder run that failed after submitting), instead of failing as a duplicate.

### Security
- Pod Security `restricted` for platform workloads, network policies, no Kubernetes Secrets in charts,
  per-secret Key Vault access, Actions pinned to commit SHAs, secret scanning and push protection.
