# Demo environment: free Azure subscription

How the first demo runs on a **free Azure subscription**, what that subscription limits, and how the platform behaves within those limits.

> **Status:** plan for the first demo. Related documents: [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md) (Phase 0 and demo script), [cleanup.md](cleanup.md), [COMPATIBILITY.md](../../COMPATIBILITY.md).

## 1. Approach

- **Create new and Select existing are both implemented** for every resource. The first demo uses **Select existing** throughout: the shared AKS cluster, registry and data resources are created once by the platform stacks, and the golden-path request reuses them.
- Everything is sized to the smallest workable setup and **torn down after the demo** ([cleanup.md](cleanup.md)).
- This document doesn't claim that any resource is free. Free-account offers change, and they depend on the region and the account. Check the current offer and your own usage in the portal (Subscriptions → your subscription → free services).

## 2. What a free subscription gives and limits

Checked on 2026-10-10 against Microsoft's documentation ([avoid charges with your free account](https://learn.microsoft.com/azure/cost-management-billing/manage/avoid-charges-free-account)):

| Aspect | What applies |
|---|---|
| Credit | A one-off credit (USD 200 or the equivalent) for the **first 30 days** |
| After the credit ends or 30 days pass | The subscription and its services are **disabled** unless you **upgrade to pay-as-you-go**. After upgrading, you're charged for usage beyond the free-service amounts |
| Free services | A limited monthly quantity of selected services for **12 months**, plus a set of always-free services |
| vCPU quota | Default regional vCPU quota on new or free subscriptions is **low, and in some regions zero**. Request an increase under *Usage + quotas* |
| AKS clusters | Free-trial subscriptions are limited to a small number of AKS clusters per region |
| Billing account type | Microsoft Online Subscription Program (MOSP), **not** EA or MCA |

## 3. How the platform behaves on this subscription

Options the subscription can't support are **disabled in the form, with the reason**. Discovery reports them through `GET /v1/subscriptions/{id}/capabilities`, and `/v1/validate` enforces them on the server.

| Feature | Behaviour on a free subscription | Demo value |
|---|---|---|
| Create new **subscription** | Disabled: *"Subscription vending needs an EA or MCA billing account."* | Shows capability-based guardrails |
| Create new **AKS cluster** | Allowed only if the regional vCPU quota can fit it; otherwise disabled with the quota numbers | Shows quota-aware validation |
| Create new **ACR**, resource group, namespace, Storage, Key Vault | Available | — |
| **High availability = Yes** | Usually **rejected**: the demo cluster has a single small node pool and doesn't span 2 zones | Shows the HA justification flow and server-side rejection |
| Select existing (all) | Available. **Used for the demo request** | The golden path |

## 4. Demo sizing

| Resource | Demo choice | Why |
|---|---|---|
| Region | One allowlisted region with AKS 1.36 and enough quota, for example `uksouth` | Single region keeps cost and quota simple |
| AKS | **Free tier** control plane (no uptime SLA), **1 system node pool, 1–2 small nodes** (at least 2 vCPU / 4 GiB per node, as AKS requires for system pools), Azure CNI Overlay | Fits a small vCPU quota. The platform and the demo app share the pool |
| Ingress | App Routing Gateway API with **one** shared Gateway, so one public IP and load balancer | [ADR-0003](../adr/0003-ingress-gateway-api.md) |
| ACR | **Basic** | Enough for a few images |
| PostgreSQL | Azure Database for PostgreSQL flexible server, **smallest Burstable** size, no HA, minimum storage | Platform state for Backstage and the orchestrator |
| Key Vault | Standard, RBAC, purge protection with the **minimum 7-day retention** | Short retention so the name is freed soon after teardown |
| Storage | `Standard_LRS` for Terraform state and the demo app | No ZRS needed without HA |
| DNS | One Azure DNS zone, or the Gateway's IP address with a `nip.io`-style hostname if you don't own a domain | Avoids buying a domain for the demo |
| Not used | NAT gateway, Azure Firewall, Application Gateway, private endpoints, Log Analytics retention beyond the default | Not needed for the demo, and they add cost |

## 5. Preparation checklist

1. Create the free account and subscription. **Set a budget with alerts** at low thresholds (*Cost Management → Budgets*).
2. Register the resource providers: `Microsoft.ContainerService`, `Microsoft.ContainerRegistry`, `Microsoft.KeyVault`, `Microsoft.DBforPostgreSQL`, `Microsoft.Network`, `Microsoft.Storage`, `Microsoft.ManagedIdentity`. Also register the `EncryptionAtHost` feature, which AKS node pools use for host encryption: `az feature register --namespace Microsoft.Compute --name EncryptionAtHost`, wait until `az feature show` reports `Registered`, then run `az provider register -n Microsoft.Compute`.
3. Check the quota in the chosen region:
   ```bash
   az vm list-usage --location uksouth -o table | grep -i -E "total regional vcpus|standard.*family"
   ```
   If needed, request an increase for *Total Regional vCPUs* and the VM family you'll use. Free-trial subscriptions may need an upgrade to pay-as-you-go before quota increases are approved.
4. Allowlist the region, the free subscription ID and the shared resource names in `policies/`.
5. Apply the platform stacks in order: `00-bootstrap` → `10-identities` → `20-shared-dev`.
6. Run the golden-path demo ([IMPLEMENTATION_PLAN.md §6](../../IMPLEMENTATION_PLAN.md#6-demo-script)). Record evidence.
7. **Tear down the same day** ([cleanup.md](cleanup.md)), then check *Cost Management* the next day.

## Reaching an application without your own domain

Applications are named `<name>.dev.xycorp.local` (the cluster's `gateway.base_domain` in
`policies/allowlist.yaml`). You don't need to own a domain or run DNS:

- **Pipelines need nothing.** The deploy smoke test reads the shared Gateway's IP and calls the app with
  `curl --resolve <host>:80:<gateway-ip>`, so the name never has to resolve.
- **Your browser** needs one hosts entry per application. Find the IP with
  `kubectl get gateway sportify-gateway -n sportify-gateway -o jsonpath='{.status.addresses[0].value}'`,
  then add `<gateway-ip>  orders-api.dev.xycorp.local` to `/etc/hosts` or
  `C:\Windows\System32\drivers\etc\hosts`.
- **No hosts file at all:** set `base_domain` to `<gateway-ip>.nip.io`. Public wildcard DNS then resolves
  `orders-api.<gateway-ip>.nip.io` to the Gateway, with nothing to configure.
- **A team network** can serve `dev.xycorp.local` from an Azure Private DNS zone linked to the network your
  users resolve from, with a wildcard record pointing at the Gateway.

`.local` is reserved for multicast DNS (RFC 6762). Public DNS can't serve it, `20-shared-dev` refuses a
public `.local` zone, and macOS and many Linux desktops send `.local` lookups to mDNS first, so hosts
entries are the most reliable option there. Use a domain you own (and a public zone) when applications must
be reachable from the internet.

## 6. Timing

- Plan to **build and record the demo within the 30-day credit window**. Most development (Phases 2–4) runs locally with mocked Azure adapters and uses no Azure resources at all.
- If you need Azure after day 30, upgrade to pay-as-you-go **with the budget alerts already in place**. Keep the shared resources up only while you're actively using them.
