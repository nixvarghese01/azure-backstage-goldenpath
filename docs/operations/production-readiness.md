# Production readiness gaps

Installing successfully doesn't make this production-ready. This model project deliberately stops short of the items below. Each one says what a production rollout should add.

| Area | Model project | Production |
|---|---|---|
| Network | Public endpoints with Entra-only auth (state storage, Key Vault, PostgreSQL); GitHub-hosted runners | Private endpoints, VNet-integrated PostgreSQL, self-hosted runners in the VNet, Azure Firewall egress control |
| Ingress | HTTP smoke tests, optional TLS, App Routing Gateway API | TLS everywhere (Key Vault certificates or cert-manager), WAF and rate limiting (Application Gateway for Containers or the Istio add-on) |
| Cluster | AKS Free tier, one small node pool | Standard tier (SLA), zonal system and user pools, Azure Policy for Kubernetes, Defender for Containers, image signing and admission (Ratify) |
| Subscription guardrails | Plan policies (Conftest) and the allowlist | Azure Policy assignments at management-group scope: allowed locations, SKUs, required tags, deny public network access |
| Identity | Provisioning identity with subscription-level custom role + ABAC | Per-landing-zone provisioning identities, PIM for the platform identity, conditional access for operators |
| Workflows | Callers pin reusable workflows to `@main` | Pin to release tags (`@workflows/v1`) and update `reusable_workflow_ref` |
| Observability | Structured logs, optional OTLP traces | Azure Monitor / Managed Prometheus and Grafana dashboards, SLO alerting, audit log export to a SIEM |
| Orchestration | PostgreSQL job table | Temporal (ADR-0001) once workflow types and volumes grow |
| Data | Burstable PostgreSQL, 7-day backups | HA PostgreSQL (zone-redundant), longer retention, tested restore |
| Environments | `dev` only | `test`/`prod` with two approvers, HA default in prod, deploy approvals |
| Supply chain | SHA-pinned actions, checksum-verified tools, Trivy/gitleaks/CodeQL | SBOMs, image signing (cosign/Notation), provenance attestations, private registry mirrors |
| Cost | Manual teardown, budget alerts | Cost estimates on the approval card (configured pricing), budgets per team, automatic idle-resource cleanup |
