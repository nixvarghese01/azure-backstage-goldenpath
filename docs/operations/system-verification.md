# System verification — 2026-10-13

Local verification of the checkout at `E:\Github\azure-backstage-goldenpath` on Windows 11.
Checks mirror the CI workflows as closely as the machine allows. No infrastructure was
provisioned and nothing was published.

## Pipeline coverage

| Pipeline | Lint and static checks | Security scans | Plan / build | Deploy gate |
|---|---|---|---|---|
| Platform IaC (`ci-iac`, `platform-plan`, `platform-apply`) | fmt, validate, `terraform test`, TFLint | Checkov on code and on the plan JSON, Conftest plan policies | Plan per changed stack, summary on the PR | Static gate → plan → policy and scan → apply that saved plan, behind environment reviewers |
| Platform charts (`ci-iac`) | `helm lint`, render | Conftest, Trivy config | — | — |
| Platform services and portal (`ci-python`, `ci-portal`, `platform-release`) | ruff, ruff format, strict mypy; tsc and ESLint | CodeQL, Trivy (lockfiles, image), dependency review | Images with CycloneDX SBOMs | Push, build provenance attestation, deploy by digest |
| Generated app IaC (`reusable-terraform`) | fmt, validate, TFLint, Helm lint | gitleaks, Checkov on code and plan, Conftest, Trivy config | Plan gated on validate | Apply only the approved plan, verified by hash |
| Generated app code (`reusable-application-ci`, `-deploy`) | Language lint and tests | CodeQL, gitleaks, Trivy (lockfiles, Dockerfile, image) | Image with SBOM | Provenance attestation; Conftest on the exact release manifests |
| Repository (`ci-security`, `codeql`) | actionlint with shellcheck | zizmor, gitleaks (full history), Trivy SARIF, CodeQL for all languages | — | — |

## Passed checks

| CI job | Check | Result |
|---|---|---|
| ci-python | `uv sync --all-packages` (Python 3.14.8, uv 0.13.0, lockfile committed) | Pass |
| ci-python | `ruff check`, `ruff format --check`, `mypy --strict` (36 files) | Pass |
| ci-python | Unit and API tests: sportify-common / azure-discovery / orchestrator | 10 / 23 / 46 passed |
| ci-e2e | `pytest e2e` (golden path against mock GitHub and Azure) | 10 passed |
| ci-iac | fmt, `init -backend=false` + `validate` for all 17 modules and stacks | Pass |
| ci-iac | `terraform test` | 8 passed |
| ci-iac | `tflint --recursive` (0.64.0) | Pass |
| ci-iac | Checkov 3.3.26 on `iac/` | 73 passed, 0 failed, 45 waived |
| ci-iac | `conftest verify` for Terraform / Helm policies (0.71.1) | 9 / 6 passed |
| ci-iac | Platform charts: lint, render, Conftest, Trivy config | Pass |
| ci-templates | All 8 stacks: render, Checkov, Terraform fmt/validate, Helm lint, Conftest and Trivy on standard and HA renders, actionlint on generated workflows, Trivy on Dockerfiles and lockfiles | Pass |
| ci-security | gitleaks 8.30.1 over full history | No leaks |
| ci-security | actionlint 1.7.12 with shellcheck 0.11.0 | Pass |
| ci-security | zizmor 1.30.1, medium and above (offline audits) | No findings |
| ci-security | Trivy 0.75.0: lockfile vulnerabilities and secrets; Dockerfile and manifest misconfiguration (HIGH, CRITICAL) | None |
| ci-portal | `yarn install --immutable` (Node 24.21.0, Yarn 4.13.0, Backstage 1.55.3, lockfile committed) | Pass |
| ci-portal | `yarn tsc`, `yarn lint:all` | Pass |
| ci-portal | `yarn test:all` | 10 passed |
| ci-portal | `yarn build:backend --config ../../app-config.container.yaml` | Pass |
| — | Every action SHA pin matches its release tag | 11 / 11 |

Checkov on a plan JSON was verified with a constructed plan: enrichment applies the module
waivers from the repository root (platform stacks) and from `.terraform/modules` (generated
repositories, whose modules come from git).

Terraform 1.16.4 and Helm 3.15.4 were used; CI pins 1.16.5 and 4.3.0. Helm renders used
`--kube-version 1.36.0` because Helm 3 defaults to an older version than the charts allow.
Tools not on PATH were installed into the git-ignored `.tools/` directory, from release pages after
checksum verification or from PyPI through uv.

## Defects found and fixed

- **azurerm 5 schema breaks.** `azurerm_federated_identity_credential` now takes
  `user_assigned_identity_id`, and `azurerm_kubernetes_cluster` requires a
  `node_provisioning_profile` block (`mode = "Manual"`). This broke validation for the AKS and
  app-identity modules, `20-shared-dev` and every generated application.
- **Checkov would fail `ci-iac`.** It reported 56 failures. Fixes: the AKS Azure Policy add-on,
  host encryption, explicit `max_pods`, optional API server authorized IP ranges, and GZRS for
  the Terraform state account. The remaining checks need Premium SKUs, private networking or
  paid add-ons that the demo subscription cannot use. Each is waived inline on its resource with
  a reason.
- **Workflow hardening (zizmor).** There were 31 high-severity template injections. Inputs,
  matrix values and variables now reach scripts only through `env:`, and are validated where
  they name resources. Every checkout drops persisted credentials, `platform-plan` scopes
  `pull-requests: write` to one job, and Dependabot has a 7-day cooldown.
- **shellcheck findings** in four workflow scripts would have failed actionlint.
- **Helm policy flagged Jobs for missing readiness probes.** The rule now applies to long-running
  workloads only, and the Helm policies have their first unit tests.
- **Generated Terraform failed `fmt -check`.** Fixed in the skeleton's `variables.tf`.
- **Python CI would have failed** with 65 ruff findings, 30 unformatted files and 16 mypy errors.
- **Policy test never exercised its rule.** `test_missing_tags_denied` merged rather than
  replaced the tags.
- **gitleaks false positive in history** on `idempotency_key=`.
- **Uniform app sizing.** Every stack had the same 256Mi limit, below what Spring Boot needs locally.
  Each stack now has a single runtime profile used by both Kubernetes and Compose
  ([technology-stacks.md](../developer-guide/technology-stacks.md#runtime-sizing)), plus a startup probe.

- **The portal had never been installed or compiled.** Fixes:
  - Added the Backstage Yarn plugin and committed `yarn.lock`.
  - Pinned `@yarnpkg/core` to 4.9.1, because 4.9.2 was published with an unresolvable `got` patch.
  - Added the Jest, jsdom and type packages that Backstage CLI 0.36 expects the project to provide.
  - Added ESLint configs to every package.
  - Fixed 15 type errors from API drift: the sign-in page, entity card props, the permission policy
    (now reads groups through the user-info service), and `FieldValidation` (now from `@rjsf/utils`).
  - Built with the container config, because the default config `$include`s a credentials file that
    isn't present at build time. The Dockerfile's relative `--config` path was also wrong.
- **Portal dependency vulnerabilities.** Yarn resolutions force the patch fixes for `adm-zip` and `undici`.
  Two HIGH findings that need breaking majors under upstream Backstage pins (`@graphql-tools/utils`,
  `basic-ftp`) are accepted in `.trivyignore.yaml` with reasons until 2026-12-15.

## Not verified on this machine

| Area | Blocker |
|---|---|
| Generated application builds and tests, Docker images, Compose | Node.js, Docker, Maven, Go not installed; Java is 17 (Spring targets 21) |
| PostgreSQL integration tests (Testcontainers), kind install | Docker not installed |
| zizmor online audits, CodeQL, SARIF upload, attestations | Run only on GitHub |
| Live Azure plans and applies, GitHub Apps, deployment | Out of scope for local verification |

## Before the first real run

- Create and protect the module release tags (`<module>/vX.Y.Z`) that generated repositories pin.
- Register the `EncryptionAtHost` feature on the subscription
  ([demo-environment.md](demo-environment.md)).
- Run [validation-checklist.md](validation-checklist.md) with Docker Desktop for images, Compose,
  the PostgreSQL integration tests and the kind install.
- Revisit the `.trivyignore.yaml` acceptances before they expire on 2026-12-15.
- Keep the seven additional starters disabled until their application builds pass.
