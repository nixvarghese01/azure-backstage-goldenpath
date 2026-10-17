# ADR-0007: Shared deployment contract across application technologies

- Status: implemented; NestJS verified on AKS (v1.0.0), the other stacks await target-system validation ([#26](https://github.com/nixvarghese01/azure-backstage-goldenpath/issues/26))
- Date: 2026-10-13
- Related: [ADR-0006](0006-container-delivery.md), [technology inventory](../developer-guide/technology-stacks.md)

## Decision

Add FastAPI, Go HTTP, ASP.NET Core, Spring Boot, Next.js, React/Vite and Vue/Vite alongside NestJS.
Keep one Backstage request form, one orchestrator, and the existing Terraform and Helm contract.
The new starters remain disabled until validation on the target system, as local execution is deferred.

Share common generated assets under `_shared` and overlay each stack's files after rendering.
Keep the new demos stateless and support runtime capability None only. Azure SDK/persistence and
Key Vault application integrations are separate work, enforced by per-stack capability policy.
Production platform secret management continues to use Azure Key Vault.

Use the same reusable CI workflow for every language so the trusted OIDC workflow reference does
not change. Node checks use npm scripts; other languages use a `verify` Docker target. Runtime
images exclude compiler/test tooling. React and Vue use a static Nginx runtime; Next.js uses
standalone Node output. Go uses the standard library to avoid unnecessary framework dependencies.
Do not deploy a frontend/backend pair automatically; each generated project is one deployable service.

## Consequences

The worker image includes all templates. Shared CI validates eight render/build/deploy paths, which
increases CI work but preserves common security and operational controls. Defaults and memory
ceilings remain provisional. The new starters provide demonstrable project structure, not production
domain functionality. Locks, vulnerability scans, image digests and runtime checks are pending.
