# Local code review — 2026-10-13 (historical)

> **Kept for reference.** A dated review note from before milestone 1 was verified; it is not updated.

Milestone 1 remains unverified end to end. The maintainer requested completion of coding first,
with local testing and other execution deferred. No repository was published, no remote CI was
triggered, and no Azure resources were provisioned during this review.

## Changes

- Keep API route annotations evaluable inside both FastAPI application factories so their local
  authentication and database dependency aliases can resolve. Correct the database generator type.
- Serialize application descriptions with Jinja's JSON filter in generated package metadata and
  Swagger setup, preserving quotes, backslashes and control characters. Use JSON serialization in
  the fixture renderer's `dump` handling too.
- Require an Actions callback's run ID to match its verified OIDC token and scope callback
  deduplication to the request, allowing one platform run to report to multiple requests.
- Run cross-service CI on `develop` and `main` pull requests and relevant pushes. Include the
  generated application's API end-to-end tests in template CI.
- Add regression cases for callback identity/deduplication and generated descriptions, for later
  execution. Correct the documented Terraform loop so init/validation failures stop the check.
- Update the README status, contribution guidance and catalog cleanup permission inventory.

## Verification status

The later multi-technology implementation adds FastAPI, Go, ASP.NET Core, Spring Boot, Next.js,
React/Vite and Vue/Vite starters. Shared rendering, runtime selection in CI, the worker image,
per-stack Azure capability policy and an eight-stack template CI matrix are written. New choices
remain disabled pending validation. Source/whitespace review does not establish successful dependency
resolution, builds, framework tests, container startup or deployment. See the
[technology inventory](../developer-guide/technology-stacks.md) for the precise scope and limitations.

Subsequent source review covered the container topology, lightweight image targets and generated
developer starter. The renderer's inputs supply the Dockerfile, Compose and README templates;
generated output names match the existing CI and application pull-request path. An empty
`AZURE_STORAGE_ACCOUNT` from Compose previously failed the starter's name validation. The config now
normalizes that empty value to an unset capability, preserving the local in-memory mode and validation
of malformed nonempty names. Regression cases are written for later execution. The platform README
now distinguishes the initial infrastructure-only repository from the final Docker-ready starter.

Before testing was deferred, the four existing Helm charts passed basic lint with their defaults.
The platform charts emitted missing-value warnings; this does not establish deployment readiness.
The cross-service pytest attempt stopped during collection because SQLAlchemy was unavailable.
Dependency setup was declined. No test suite or validation command was run after the maintainer
requested coding only, and the changes above have not been executed.

Follow [validation-checklist.md](../operations/validation-checklist.md) when execution is authorized. Prioritize
Python API construction and regression tests, the cross-service golden path, portal type checking,
generated NestJS lint/unit/API tests, Terraform mock-provider tests, and Helm rendering/policies.
PostgreSQL restart/concurrency and kind deployment checks require their own prepared environments.

## Suggested next improvements

1. Commit dependency lockfiles after resolving and validating Python, portal and generated
   application dependencies. Replace first-install fallbacks with reproducible installs.
2. Replace the scaffold's hardcoded `nixvarghese01` workflow references with the configured
   organization while preserving GitHub expressions. Pin reusable workflow/module references
   to a tested release before using them outside the model project.
3. Extend cross-service coverage to the new subscription/cluster/registry path: wait for all
   platform stacks, revalidate created resources, and pass their resolved IDs/resource groups
   into the scaffold rather than relying on the original form selections.
4. Exercise callback reordering and retries across approval, deployment and cleanup, plus worker
   lease recovery under PostgreSQL. Existing delivery deduplication alone does not establish
   safety for a new run attempt or an event arriving in a different order.
5. Verify cleanup against a real Backstage catalog location so a deleted entity is not later
   rediscovered from a still-registered repository. Confirm the production JWKS restrictions
   and catalog permission policy permit the intended cleanup operations.

These are follow-up recommendations. Live GitHub/Azure validation and publishing remain deferred.
