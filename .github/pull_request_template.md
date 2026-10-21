## What and why

<!-- The change and the reason for it. Link the issue: Closes #... -->

## Type

<!-- Matches the branch prefix (CONTRIBUTING.md "Branching model"). -->

- [ ] `feature/` new behaviour
- [ ] `bugfix/` fix on develop
- [ ] `hotfix/` urgent fix for a release on main
- [ ] `docs/` / `chore/` / `refactor/` / `test/` / `ci/`
- [ ] Release: `develop` → `main`

## Checks

- [ ] Targets `develop` (only releases and hotfixes target `main`)
- [ ] The checks for the areas touched pass ([validation checklist](https://github.com/nixvarghese01/azure-backstage-goldenpath/blob/develop/docs/operations/validation-checklist.md))
- [ ] README / docs updated where behaviour changed
- [ ] No secrets in the diff
