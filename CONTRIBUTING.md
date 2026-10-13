# Contributing

Thanks for helping improve Sportify Azure Backstage. This is a model project, so changes should keep the design consistent and documented.

## Branches and commits

- Work on a branch from `develop`, and open the pull request against `develop`. `main` receives tested releases.
- Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `ci:`, `chore:`).
- Keep pull requests focused on one concern.

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
- Changes to `.github/workflows/`, `iac/`, `policies/` and `templates/` need platform-team review (`CODEOWNERS`).

## Adding a new stack

1. Add `templates/applications/<stack>/application/` (rendered by the orchestrator with `[[ ]]` delimiters). Common assets come from `templates/applications/_shared/`; stack files override them.
2. Add the stack to `policies/allowlist.yaml` and to `sportify.stacks` in `portal/app-config.yaml`, initially with `enabled: false`.
3. Use the existing reusable CI runtime input (`node`, `python`, `go`, `dotnet`, `java`). Non-Node templates must provide a `verify` Docker target, keeping OIDC trust on the existing workflow.
4. Extend `ci-templates.yml` to render and test it, then enable it.
