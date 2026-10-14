# Contributing

Thanks for helping improve Internal Developer Portal. This is a model project, so changes should keep the design consistent and documented.

## Branching model

| Branch | Purpose | Branches from | Merges into |
|---|---|---|---|
| `main` | Released code; every release is a tag `vX.Y.Z` on it | — | — |
| `develop` | Integration branch, the default | `main` | `main` (release) |
| `feature/<issue>-<topic>` | New behaviour | `develop` | `develop` |
| `bugfix/<issue>-<topic>` | A fix for something not yet released | `develop` | `develop` |
| `hotfix/<issue>-<topic>` | An urgent fix for a release | `main` | `main`, then `main` back into `develop` |
| `docs/`, `chore/`, `refactor/`, `test/`, `ci/` | Docs, upkeep, restructuring, tests, pipelines | `develop` | `develop` |

Examples: `feature/12-endpoint-host-picker`, `bugfix/31-namespace-default`, `hotfix/40-plan-hash-check`.
A fix for something only on `develop` is a `bugfix/` branch, not a hotfix.

**Branch protection** (repository rulesets):

- **`develop`:** no deletion or force pushes. Changes arrive as pull requests from the prefixes above
  (squash merge; a merge commit for the `main` back-merge), checked by the `branch policy` workflow,
  and the security checks must pass.
- **`main`:** no deletion or force pushes. Pull requests only from `develop` (a release, merge commit)
  or `hotfix/*`, with the same checks.
- **Release and module tags** (`v*`, `<module>/v*`) can't be moved or deleted: generated
  repositories pin modules by tag.
- **The maintainer (repository admin) may bypass these rules** and push directly to either branch.
  Everyone else goes through pull requests; [`CODEOWNERS`](.github/CODEOWNERS) requests the
  maintainer's review on each one.

### Hotfixes

1. Branch `hotfix/<issue>-<topic>` from `main` and fix it, with tests.
2. Open a pull request into `main`.
3. Open a pull request `main` → `develop` so the fix isn't lost.

## Commits and pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `ci:`, `chore:`).
- Keep pull requests focused on one concern, and fill in the pull request template.

## Before opening a pull request

| Area | Run |
|---|---|
| Python services | `cd services && uv sync --all-packages`, then follow the separate lint, type and test commands in the [validation checklist](docs/operations/validation-checklist.md) |
| Portal | `cd portal && yarn tsc && yarn lint:all && yarn test:all` |
| Terraform | `terraform fmt -recursive`, `terraform validate` and `terraform test` in changed modules |
| Policies | `conftest verify -p policies/terraform` |
| Template | `uv run --project services python templates/applications/nestjs/render_fixture.py /tmp/orders-api`, then `helm lint` and `npm test` there |
| Secrets | `pre-commit run --all-files` (gitleaks, ruff, terraform fmt) |

See [docs/operations/validation-checklist.md](docs/operations/validation-checklist.md) for the full set.

For local-only work, make the requested changes and commit locally. Publishing, cloud provisioning and
test execution can be deferred by the maintainer; record the checks that remain pending instead of
marking the change verified. Do not push or create a pull request without authorization.

## Rules that reviews enforce

- **No secrets in the repository**, including examples. Placeholders only (`dev-only-…`).
- **GitHub Actions are pinned to full commit SHAs**, with the version in a comment. Check new SHAs against the upstream release tag.
- **No user-supplied Terraform, scripts or workflows run through the platform.** Templates render values, not code.
- **Decisions are recorded.** A change to architecture, identity, security or a major version gets an ADR in `docs/adr/`, and an update to [COMPATIBILITY.md](COMPATIBILITY.md) where versions are involved.
- **Docs stay in sync.** If you change behaviour described in the README or `docs/`, update them in the same pull request.
- Changes to `.github/workflows/`, `iac/`, `policies/` and `templates/` need the maintainer's review (`CODEOWNERS`).

## Dependency updates

Dependabot proposes minor and patch updates, grouped per ecosystem with a 7-day cooldown. It
ignores major versions in `/portal` and of the Node base images, because Backstage pins those majors
itself.

**Upgrading Backstage** is one change for the whole portal:

1. Branch `chore/<issue>-backstage-<version>` from `develop`.
2. `cd portal && yarn backstage-cli versions:bump`, then `yarn install`.
3. Follow the [Backstage upgrade helper](https://backstage.github.io/upgrade-helper/) for changes to
   the app and backend scaffolding.
4. Run the portal checks above and update the Backstage row in [COMPATIBILITY.md](COMPATIBILITY.md).

**Moving to a new Node.js major** happens only once Backstage lists it in `engines`. Portal, application
templates and base images move together in one pull request, with an ADR (see `COMPATIBILITY.md`).

## Adding a new stack

1. Add `templates/applications/<stack>/application/` (rendered by the orchestrator with `[[ ]]` delimiters). Common assets come from `templates/applications/_shared/`; stack files override them.
2. Add the stack to `policies/allowlist.yaml` and to `idp.stacks` in `portal/app-config.yaml`, initially with `enabled: false`.
3. Use the existing reusable CI runtime input (`node`, `python`, `go`, `dotnet`, `java`). Non-Node templates must provide a `verify` Docker target, keeping OIDC trust on the existing workflow.
4. Extend `ci-templates.yml` to render and test it, then enable it.
