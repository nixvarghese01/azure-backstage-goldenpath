# Best practice vs. this free-tier project

This is a hands-on portfolio project that has to run on an **Azure Free Trial subscription** and a
**single 4-vCPU test cluster**. Enterprise best practice often costs more than that allows. This page
lists, area by area, **what best practice is**, **what this project does**, **why it deviates** and **how
to switch** when you have a real budget. Use it to run the project effectively, and to explain the
trade-offs when you present it.

Legend: ✅ follows best practice · ⚠️ deliberate free-tier deviation · 🔜 planned

## The constraints that drive every deviation

| Constraint | Free Trial reality | Consequence here |
|---|---|---|
| Credit | USD 200 for 30 days; the spending limit disables the subscription, not bills it | Everything is sized for about **USD 0.25 per hour** and torn down by a timer |
| vCPU quota | **4 vCPU per region** (all families together) | One 4-vCPU AKS node runs everything; no second node, no zones |
| Regional capacity | Small SKUs are often out of stock (`AllocationFailed`, `RegionalAllocationFailed`) | Alternative sizes are allowlisted; PostgreSQL runs in the cluster |
| Billing account | No EA or MCA billing scope | Subscription vending is built but disabled |
| Tenant | Usually no management groups; you are the only admin | The CAF hierarchy works, and degrades to "subscription under Tenant Root Group" |
| GitHub Free (public repo) | Environments, reviewers, wait timers and OIDC are free; scheduled runs are best-effort | Approvals are real; the TTL uses an environment wait timer rather than relying on cron |

## Landing zone and governance

| Area | Best practice | This project | Why | To switch |
|---|---|---|---|---|
| Placement | ✅ Subscriptions in CAF management groups (Landing zones → Corp/Online) | The picker walks tenant → management group → subscription; the allowlist limits groups | Same design either way | `scripts/bootstrap-platform.sh allowlist --management-groups <groups>` |
| Resource organisation | ✅ Resource groups per function and lifecycle | `rg-idp-{aks,registry,data,network,apps,identities,tfstate}-dev` | n/a | n/a |
| Tags | ✅ Required tags enforced by Azure Policy, inherited from the group | Tags on every resource (including node pools and CSI disks); works under a "require tags" policy | n/a | n/a |
| Policy | Azure Policy at management-group scope (locations, SKUs, tags, deny public access) | ⚠️ Plan-time policy (Conftest, Checkov) plus whatever the landing zone assigns | You can't assign management-group policy without management groups | Assign the policies in your landing zone; the plan checks stay |
| Subscription vending | Automated subscriptions per workload (EA/MCA alias API) | ⚠️ Module and form exist; `billing_scope: null` disables the option | A Free Trial has no billing scope | Set `subscription_vending.billing_scope` in the allowlist |

## Identity and access

| Area | Best practice | This project | Why | To switch |
|---|---|---|---|---|
| CI to Azure | ✅ OIDC federation, no client secrets, immutable subjects | Same | n/a | n/a |
| Workloads to Azure | ✅ Workload Identity, one identity per service | Same | n/a | n/a |
| Least privilege | ✅ Rights scoped to the workload's resource groups; custom roles | Same; no identity can write outside the IDP's groups | n/a | n/a |
| Operator access | PIM (just-in-time) and conditional access | ⚠️ Standing access for the single admin | PIM needs Entra ID P2 | Enable PIM for the platform roles |
| Approvals | Two people (four-eyes) | ⚠️ One reviewer; opt-in self-approval in `dev` only, recorded as `self_approved` | One-person project | `approvers_required: 2` and remove `selfApprovalEnvironments` |
| Portal sign-in | Entra ID single sign-on with users and groups synced from Microsoft Graph | ⚠️ GitHub sign-in; users and groups from a catalog file | Simplest for a public demo | 🔜 Microsoft Graph org provider and Entra sign-in |

## Network

| Area | Best practice | This project | Why | To switch |
|---|---|---|---|---|
| PaaS endpoints | Private endpoints (Key Vault, Storage, PostgreSQL, ACR) | ⚠️ Public endpoints with Entra-only auth (no keys, no passwords) | Private endpoints and DNS need a VNet design, and GitHub-hosted runners can't reach them | Private endpoints plus self-hosted runners in the VNet; `public_network_access_enabled = false` |
| AKS API server | Private cluster or authorised IP ranges | ⚠️ Public API with Entra auth, local accounts off | GitHub-hosted runner IPs aren't stable | `api_server_authorized_ip_ranges` or a private cluster with self-hosted runners |
| Egress | Azure Firewall / NAT Gateway with allowlists | ⚠️ Default load balancer egress | Azure Firewall costs USD 0.40-1.25/hour | Add a firewall and a user-defined route |
| In-cluster | ✅ Network policies (Cilium), default deny per workload | Same | n/a | n/a |

## Compute (AKS)

| Area | Best practice | This project | Why | To switch |
|---|---|---|---|---|
| Tier | Standard tier (uptime SLA) | ⚠️ Free tier | The SLA costs about USD 0.10/hour | `sku_tier = "Standard"` |
| Node pools | System pool (critical add-ons only) plus a user pool, both across 3 zones | ⚠️ **One** `Standard_B4s_v2` node runs everything | 4-vCPU quota | `user_pool = {...}` and zones (ADR-0004) |
| Node size | General purpose (D-series) | ⚠️ Burstable B-series v2, 30 GB OS disk | Cheapest size that fits the platform | `system_pool.vm_size` |
| Ingress controller | One controller | ✅ Gateway API (App Routing Istio); the default nginx controller is **off** | It would reserve about 1 vCPU for nothing | n/a |
| Security | ✅ Pod Security `restricted`, Azure Policy add-on, host encryption, Workload Identity | Same; the gateway namespace is `baseline` (managed Istio proxies) | n/a | n/a |
| Monitoring | Container Insights / Managed Prometheus | ⚠️ Off | Log Analytics ingestion is charged per GB | 🔜 Managed Prometheus + Grafana (see Observability) |

### What fits in 4 vCPU (measured on the dev node)

| | CPU reserved (requests) | CPU used | Memory used |
|---|---|---|---|
| AKS add-ons (Cilium, Istio, Gatekeeper, CSI, Konnectivity, metrics) | about 2.9 vCPU | about 0.2 vCPU | about 2 GiB |
| IDP platform (Backstage, discovery, orchestrator API and worker, PostgreSQL) | 0.35 vCPU | 0.03 vCPU | about 0.45 GiB |
| **Free for applications** (of 3.86 vCPU and about 13.7 GiB allocatable) | **about 0.6 vCPU** | | **about 5.6 GiB** (by requests) |

Requests, not usage, decide what can be scheduled, so the platform's requests are set close to what it
uses. A golden-path app requests 100m by default: **3-5 small apps fit**.

## Data and secrets

| Area | Best practice | This project | Why | To switch |
|---|---|---|---|---|
| Platform database | Managed PostgreSQL, zone-redundant HA, tested restore | ⚠️ PostgreSQL 17 **in the cluster** (StatefulSet, 8 GiB disk, no backup) | Free Trial capacity failures, and cost (ADR-0009) | `postgres = { enabled = true }` in `20-shared-dev`: Azure PostgreSQL, Entra-only |
| Database auth | ✅ Entra-only (no passwords) | ⚠️ In-cluster: passwords, but generated, stored in Key Vault and mounted by CSI; never in Kubernetes Secrets or the repo | In-cluster PostgreSQL can't use Entra | The managed option is Entra-only |
| Secrets | ✅ Key Vault, RBAC per secret, 90-day expiry, CSI driver, no Kubernetes Secrets | Same | n/a | n/a |
| Key Vault retention | 90-day soft delete | ⚠️ 7 days, purge protection on | Teardown and rebuild reuse the name sooner | `soft_delete_retention_days = 90` |
| Terraform state | ✅ Remote, Entra-only, versioning, soft delete, lock, GZRS | Same | n/a | n/a |

## Ingress and TLS

| Area | Best practice | This project | Why | To switch |
|---|---|---|---|---|
| DNS | Your own domain and an Azure DNS zone | ⚠️ Backstage and the GitHub hooks on the Gateway's Azure DNS label (`<label>.<region>.cloudapp.azure.com`, the same across provisions); apps on `<app>.<gateway-ip>.nip.io`, rewritten to the current IP at release | No domain to buy; works instantly; no static IP to pay for between provisions | `--base-domain` and `dns_zone_name`; `public_dns_label` names the label |
| TLS | HTTPS everywhere (Key Vault certificates or cert-manager), WAF | ⚠️ HTTP | nip.io can't get a public certificate | `gateway_tls_secret` and cert-manager; Application Gateway for Containers for WAF |

## Delivery and supply chain

| Area | Best practice | This project | Why | To switch |
|---|---|---|---|---|
| Pipelines | ✅ Plan on PR; policy checks on the plan; approved apply of the exact plan; preview before approval | Same | n/a | n/a |
| Actions | ✅ Pinned to commit SHAs, zizmor, least-privilege tokens | Same | n/a | n/a |
| Images | ✅ Trivy scan, SBOM, signed build provenance, deploy by digest | Same | n/a | n/a |
| Image admission | Signature verification at admission (Ratify) | ⚠️ Not enforced | Extra controller on a full node | Add Ratify or Kyverno image verification |
| Registry | Premium (private endpoint, retention, geo-replication) | ⚠️ Basic, admin user off | Premium costs about USD 1.70/day | `sku = "Premium"` |
| Runners | Self-hosted in the VNet | ⚠️ GitHub-hosted | Free for public repositories | Self-hosted runners, then private endpoints |
| Releases | ✅ SemVer, changelog, tagged releases, immutable module tags | Same | n/a | n/a |

## Observability

| Area | Best practice | This project | Why | To switch |
|---|---|---|---|---|
| Metrics and dashboards | Managed Prometheus + Grafana, SLO alerts | ⚠️ `kubectl top` and `/healthz` | Ingestion and Grafana cost money | 🔜 Managed Prometheus (low volume) |
| Logs and audit | Log Analytics, audit export to a SIEM | ⚠️ Pod logs only; Actions logs and Git history are the audit trail | Ingestion cost | Container Insights with a daily cap |
| Platform metrics | DORA metrics, template usage, developer feedback | 🔜 Not collected | Next maturity step | Planned |

## Reliability and environments

| Area | Best practice | This project | Why | To switch |
|---|---|---|---|---|
| Availability | Zones, replicas ≥ 2, pod disruption budgets | ⚠️ One node, one replica each (PDBs exist) | Quota | HA option in the form (ADR-0004) plus a user pool |
| Disaster recovery | Backups, tested restore, infrastructure rebuild | ⚠️ Rebuild only: `platform-provision` recreates everything in about 30 minutes; in-cluster data is lost | The platform is disposable by design | Managed PostgreSQL with backups |
| Environments | dev → test → prod with stricter approvals | ⚠️ `dev` only (test/prod are defined but disabled) | One subscription, one cluster | Enable them in the allowlist |

## Cost controls (best practice everywhere, stricter here)

| Control | What it does |
|---|---|
| Spending-limit guard | Bootstrap and `platform-provision` refuse a subscription that can be billed |
| Estimate first | Sizes are chosen against the price list before anything is created (`demo-environment.md`) |
| Time-to-live | Every provision has a 2-24 hour TTL; `platform-ttl-timer` tears down on time; the hourly cron is a backup |
| Teardown keeps the foundation | State, identities, Key Vault and GitHub settings stay; re-provisioning is one pipeline run |

## AI guidance (planned) within the same limits

Any AI assistant must fit this project's constraints: **no model runs in the cluster** (a CPU-only
language model would need several vCPU and many GiB on its own) and **no new Azure resources**. The
planned design:

- **Deterministic guidance first:** explain each form field, the policy that applies and why a
  choice is rejected, from the allowlist and the ADRs. No model, near-zero CPU.
- **Optional language model through an external API:** for example GitHub Models (free, rate-limited,
  authenticated with a GitHub token) or a key you bring. It is off by default, the call goes from the
  existing Backstage backend, and the cluster footprint stays at about 50m CPU.

## How to talk about these trade-offs

Each deviation is **deliberate, documented and reversible**: the switch is an input, not a rewrite.
That is the point of the project: the same code fits a Free Trial and an enterprise landing zone,
and this page says exactly what changes between them. For per-decision detail, see the
[ADRs](adr/) and [production-readiness.md](operations/production-readiness.md).
