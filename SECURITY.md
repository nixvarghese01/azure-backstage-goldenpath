# Security policy

## Reporting a vulnerability

**Please don't open a public issue for security problems.**

Report vulnerabilities privately through GitHub: **Security → Report a vulnerability** on this repository (private vulnerability reporting). Include:

- what is affected (component, file, workflow or configuration)
- how to reproduce it, and the impact you expect
- any suggested fix

You'll get an acknowledgement within 5 working days. Confirmed issues are fixed on a private branch and disclosed in the release notes once a fix is available.

## Scope

This is a **model project**: a reference design, not a hosted service. In scope:

- the platform code (`portal/`, `services/`, `iac/`, `policies/`, `.github/workflows/`, `scripts/`)
- the golden-path template and what it generates (`templates/`)
- the documented security design (`docs/security/`)

Out of scope: findings that require a deliberately weakened configuration, and third-party services (Azure, GitHub, Backstage upstream). Report those to their owners.

## Design references

- [Identity and security model](README.md#identity-and-security-model)
- [Secret management](docs/security/secret-management.md)
- [Permissions per identity](docs/security/permissions.md)
- [Reusable workflows and CI identity (ADR-0005)](docs/adr/0005-reusable-workflows-and-ci-identity.md)

## If a secret is exposed

Follow the incident procedure in [secret-management.md §6.3](docs/security/secret-management.md#63-revocation-and-incident-response). Revoke at the source first (GitHub App key, client secret, webhook secret), then rotate.
