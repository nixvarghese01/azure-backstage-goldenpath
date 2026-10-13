# System verification — 2026-10-13

Local verification of the checkout at `E:\Github\azure-backstage-goldenpath` on Windows 11.
Checks mirror the CI workflows as closely as the machine allows. No infrastructure was
provisioned and nothing was published.

## Passed checks

| CI job | Check | Result |
|---|---|---|
| ci-python | `uv sync --all-packages` (Python 3.14.8, uv 0.13.0, lockfile committed) | Pass |
| ci-python | `ruff check`, `ruff format --check` | Pass |
| ci-python | `mypy --strict` on all three service packages | Pass (36 files) |
| ci-python | Unit and API tests: sportify-common / azure-discovery / orchestrator | 10 / 23 / 36 passed |
| ci-e2e | `pytest e2e` (golden path against mock GitHub and Azure) | 10 passed |
| ci-iac | `terraform fmt -check -recursive iac` | Pass |
| ci-iac | `terraform init -backend=false` + `validate`, every module and platform stack | Pass (17 directories) |
| ci-iac | `terraform test` (naming, app-identity, role-assignment, storage-account) | 8 passed |
| ci-iac | `tflint --recursive` (0.64.0) | Pass |
| ci-iac | `conftest verify -p policies/terraform` (0.71.1) | 9 passed |
| ci-templates | All 8 stacks: fixture render, generated Terraform fmt/init/validate, Helm lint, conftest on standard and HA renders | Pass (35 + 49 policy tests per stack) |
| ci-secrets | `gitleaks` 8.30.1 over full history and the tracked tree | No leaks |

Terraform 1.16.4 and Helm 3.15.4 were used; CI pins 1.16.5 and 4.3.0. Helm renders used
`--kube-version 1.36.0` because Helm 3 defaults to an older version than the charts allow.
Tools not on PATH (uv, conftest, tflint, gitleaks) were installed into the git-ignored
`.tools/` directory from their release pages after checksum verification.

## Defects found and fixed

- **azurerm 5 schema breaks.** `azurerm_federated_identity_credential` now takes
  `user_assigned_identity_id` instead of `resource_group_name` and `parent_id`, and
  `azurerm_kubernetes_cluster` requires a `node_provisioning_profile` block. This broke
  `terraform validate` for the `aks-cluster` and `app-identity` modules, the
  `20-shared-dev` stack and every generated application repository. Fixed in
  `app-identity`, `github-oidc-identity`, `30-cluster-config` and `aks-cluster`, which
  sets `mode = "Manual"` because node pools are managed explicitly.
- **Generated Terraform failed `fmt -check`.** Fixed the comment alignment in the
  skeleton's `variables.tf`.
- **Python CI would have failed.** There were 65 ruff findings, 30 unformatted files and
  16 mypy errors. Fixed through formatting, a generic allowlist lookup in place of
  `type: ignore`, typed `read_secret_file` overloads, explicit handling of nullable
  Azure SDK fields, and logging of swallowed `list_runs` failures in the reconciler.
- **Policy test never exercised its rule.** `test_missing_tags_denied` used
  `object.union`, which merges nested objects, so no tags were missing. The tags are now
  replaced before the test runs.
- **gitleaks false positive in history.** The `generic-api-key` rule matched
  `idempotency_key=` in an orchestrator test. That keyword is now allowlisted.
- **.NET build caches broke rendering** (earlier pass). The renderer now skips `bin` and
  `obj` directories.

## Open finding: checkov

`checkov==3.3.26 -d iac --framework terraform` reports 62 passed and 56 failed across
28 checks, and `ci-iac` runs it without `--soft-fail`, so that step fails. There is no
skip configuration. Most findings reflect deliberate choices for the free subscription:
the Free AKS tier, public API server and registry endpoints, no private endpoints,
no customer-managed keys, single-region and non-zonal ACR, and LRS storage. Others are
candidates to fix, such as AKS Azure Policy and Monitor add-ons, ACR untagged-manifest
retention, and storage logging. Each check needs to be either fixed or waived with a
documented `checkov:skip` reason. This is a security-posture decision and is still open.

## Not verified on this machine

| Area | Blocker |
|---|---|
| Portal (Backstage) install, typecheck, lint, tests, build | Node.js / Yarn not installed |
| Generated application builds and tests, Docker images, Compose | Node.js, Docker, Maven, Go not installed; Java is 17 (Spring targets 21) |
| PostgreSQL integration tests (Testcontainers), kind install | Docker not installed |
| Live Azure, GitHub Apps, deployment | Out of scope for local verification |

## Next validation

Run [validation-checklist.md](validation-checklist.md) on a machine with Node 24,
Yarn 4.13 and Docker Desktop. Start with portal dependency resolution, then the
integration tests and the kind install from `ci-templates.yml`. Keep the seven additional
starters disabled until their application builds pass.
