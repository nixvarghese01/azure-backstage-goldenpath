# Governance

## Roles

| Role | Who | What they may do |
|---|---|---|
| **Maintainer** | [@nixvarghese01](https://github.com/nixvarghese01) | Owns the repository (see [CODEOWNERS](.github/CODEOWNERS)): reviews and merges pull requests, releases `develop` to `main`, triages issues, manages the roadmap and enforces the [Code of Conduct](CODE_OF_CONDUCT.md) |
| **Contributor** | Anyone | Opens issues and pull requests following [CONTRIBUTING.md](CONTRIBUTING.md) |

Only the maintainer has write access. More maintainers can be added later; that change is made here
and in CODEOWNERS.

## How decisions are made

- **Day-to-day changes** are decided in the pull request: the maintainer reviews and merges once the
  required checks pass ([branch protection](CONTRIBUTING.md#branching-model)).
- **Significant decisions** (architecture, identity, security, a new major version) are recorded as an
  [architecture decision record](docs/adr/) in the same pull request, so the reasoning stays with the
  code. An ADR is proposed in a pull request and accepted when it merges.
- **Deviations from enterprise best practice** (for the free tier) are listed with their reason in
  [best-practice-vs-free-tier.md](docs/best-practice-vs-free-tier.md).
- **What comes next** is planned on the [roadmap](https://github.com/users/nixvarghese01/projects/4) and in
  the issues; anyone can propose work there.

## Releases

Releases follow [Semantic Versioning](https://semver.org/). The maintainer merges `develop` into `main`;
the newest `## [X.Y.Z]` section of the [CHANGELOG](CHANGELOG.md) becomes the release
([CONTRIBUTING.md "Releases"](CONTRIBUTING.md)).

## Security and conduct

Vulnerabilities are handled privately as described in [SECURITY.md](SECURITY.md). Code of Conduct reports
go to the maintainer as described in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md#enforcement).

## Changes to this document

Changes to governance are made by pull request and merged by the maintainer.
