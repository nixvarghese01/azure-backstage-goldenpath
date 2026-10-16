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

### Fixed
- **Pipelines:** teardown of an already empty stack no longer fails the plan check (a plan with no
  resource changes), and a destroy that stops part-way (an AKS delete that times out) retries what is left.
- **Pipelines:** a re-provisioned platform (new Gateway IP) is reachable without re-running the
  bootstrap: Backstage and the GitHub hooks use the Gateway's Azure DNS label, which stays the same, and
  `<gateway-ip>.nip.io` application hostnames are rewritten to the current IP at release.

### Security
- Pod Security `restricted` for platform workloads, network policies, no Kubernetes Secrets in charts,
  per-secret Key Vault access, Actions pinned to commit SHAs, secret scanning and push protection.
