# ADR-0003: Ingress through the AKS App Routing Gateway API

- **Status:** Accepted
- **Date:** 2026-10-10

## Context

The golden path exposes every application at a URL such as `https://orders-api.dev.xycorp.local`, through a shared ingress on the AKS cluster.

- Upstream **ingress-nginx** stopped maintenance in March 2026. It gets no more releases or security fixes.
- Azure supports managed NGINX in the **AKS application routing add-on** only until **November 2026**. Microsoft states that users must migrate to the App Routing **Gateway API** implementation, or to another supported implementation, by then.
- The App Routing Gateway API implementation (`gatewayClassName: approuting-istio`) is Microsoft's recommended successor. It is the default ingress on new AKS Automatic clusters from Kubernetes 1.36 onwards.

## Decision

- Enable the AKS-managed Gateway API CRDs and the App Routing Gateway API implementation on the shared cluster. Terraform does this in `iac/platform/20-shared-dev`, using `azapi_update_resource` for the `ingressProfile` settings.
- The platform owns **one shared `Gateway` per environment** in a platform namespace. Its listeners allow routes from labelled application namespaces, and it handles DNS and TLS through the App Routing DNS and TLS integration.
- Each application's Helm chart creates an **`HTTPRoute`** (not an `Ingress`) that attaches to the shared Gateway, with the requested hostname.
- The ingress-nginx and NGINX `Ingress` resources are not used anywhere.

## Alternatives considered

| Option | Why not |
|---|---|
| Self-managed ingress-nginx | Retired upstream, with no security fixes |
| App Routing add-on with managed NGINX | Azure support ends in 2026-11, before this project would be complete |
| Istio service mesh add-on with Gateway API | Supports `EnvoyFilter` and the mesh, but needs manual canary upgrades. That's more than one golden path needs. |
| Application Gateway for Containers | Fully managed and supports both Ingress and Gateway API, but adds a separately billed Azure resource. It's a valid production upgrade. |

## Consequences

- The application chart's template set is `Deployment`, `Service`, `ServiceAccount` and `HTTPRoute`, plus a `HorizontalPodAutoscaler` and `PodDisruptionBudget` when the HA tier is selected ([ADR-0004](0004-availability-tier-option.md)).
- Request size limits, rate limiting and custom Envoy filters are not available through this implementation. They're documented as production gaps.
- Istio control-plane versions follow the AKS version automatically, and AKS upgrades are the only upgrade path for ingress.
