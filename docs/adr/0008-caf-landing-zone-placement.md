# ADR-0008: Place applications in the Cloud Adoption Framework hierarchy

- **Status:** Accepted
- **Date:** 2026-10-14

## Context

Enterprises that run Azure at scale organise their tenant with the Microsoft Cloud Adoption Framework
(CAF), usually as **Azure landing zones**: a management group hierarchy under the Tenant Root Group,
with policies and role assignments inherited downwards.

```text
Tenant Root Group
└── <organisation> (intermediate root)
    ├── Platform         Management, Connectivity, Identity subscriptions (platform team)
    ├── Landing zones    Corp (internal), Online (internet-facing): application subscriptions
    ├── Sandbox          experiments, disconnected from corporate networks
    └── Decommissioned   subscriptions being retired
```

The request form previously started at **subscription** and listed every allowlisted subscription as a
flat list. That doesn't match how an enterprise tenant is organised: developers couldn't see which
landing zone they were deploying into, and nothing stopped a subscription that had moved to Sandbox or
Decommissioned from being offered.

The IDP has to fit into a tenant the enterprise already governs. It must also still work on a single
free-tier subscription with no management groups at all.

## Decision

### 1. The form walks the hierarchy top-down

The Azure resources step asks, in order, each list depending on the one above:

| Level | Source | Notes |
|---|---|---|
| **Tenant** | Subscriptions API (`tenants.list`) | Preselected when there is only one |
| **Management group** | Resource Graph (`resourcecontainers`, management groups) | Shown as a tree, pruned to groups that contain an approved subscription. Default: the deepest such group (for example *Landing zones / Corp*) |
| **Subscription** | Subscriptions API + each subscription's `managementGroupAncestorsChain` | Only approved subscriptions below the selected group |
| **Resource group** | Resource Graph | As before |
| **Application resources** | Resource Graph | Storage account or Key Vault **inside the selected resource group** |
| **Shared runtime** | Resource Graph | AKS cluster and container registry from the same subscription, labelled with their own resource group |

The form groups these into three outlined sections (*Azure location*, *Application resources*,
*Shared runtime*), shows a breadcrumb of the current selection, and gives an example value for every
field using CAF naming (`rg-<workload>-<env>`, `st…`, `kv-…`, `acr…`).

### 2. The IDP reads the hierarchy; it never changes it

Management groups and their policies belong to the platform or cloud centre of excellence team. The
form has no *Create new* for tenants or management groups. Subscription vending (ADR-0002) places a new
subscription in `subscription_vending.management_group`.

### 3. The allowlist says where applications may land

`policies/allowlist.yaml` gains an optional `hierarchy` section:

```yaml
hierarchy:
  tenant_id: <tenant id>                           # null = any tenant the identity can see
  application_management_groups: [xycorp-landingzones]  # [] = anywhere in the tenant
```

A subscription is offered only if it is allowlisted **and** in the approved tenant **and** below one of
the application management groups. `azure-discovery` re-checks all three, plus the tenant and
management group the form submitted, when it validates the request. Browser values are never trusted.

### 4. It degrades instead of failing

| Situation | Behaviour |
|---|---|
| Free tier or no management groups | The management group level shows only *Tenant Root Group*; leave `application_management_groups` empty |
| Discovery identity can't read management groups | Same as above, with a warning in the service log |
| Local development | `DISCOVERY_AZURE_MODE=mock` serves a full Azure landing zones tenant |

The mode is always explicit. There is no automatic fallback from live Azure to mock data, so
production never shows invented resources.

## Consequences

- The discovery identity needs **Management Group Reader** on the intermediate root
  (`discovery_management_group_ids` in `iac/platform/10-identities`) to show the tree. Without it the
  form still works from the Tenant Root Group.
- Moving a subscription out of the landing zones (for example to Decommissioned) removes it from the
  form and makes validation fail, with no allowlist change needed.
- Reusing an existing Storage account or Key Vault now means choosing its resource group first.
- The orchestrator stores `tenant_id` and `management_group` with the request and sends them back to
  discovery on every validation. Showing them on the approval card is a follow-up.
