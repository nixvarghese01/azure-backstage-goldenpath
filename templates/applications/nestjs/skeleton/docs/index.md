# ${{ values.name }}

${{ values.description }}

| | |
|---|---|
| Owner | `${{ values.owner }}` |
| Environment | `${{ values.environment }}` |
| Endpoint | `${{ values.urlScheme }}://${{ values.endpointHost }}` |
| Availability tier | `${{ values.availabilityTier }}` |
| Platform request | `${{ values.requestId }}` |

## Runbook

- **Health:** `GET /health/live` (process up), `GET /health/ready` (dependencies, including Azure Storage through Workload Identity).
- **Logs:** `kubectl logs -n ${{ values.name }} deploy/${{ values.name }}` (namespace-scoped access through the deployment identity, or your team's read role).
- **Redeploy:** re-run the `application-deploy` workflow on `main`.
- **Rollback:** a failed Helm upgrade is undone by `--atomic`; a readiness or smoke check that fails after Helm finished restores the previous revision, verified, and the run's `deploy-diagnostics` artifact keeps the evidence. To roll back a good-but-unwanted release, revert the commit on `main`.
- **Current health:** the component's *Operations* tab in Backstage shows what runs now (replicas, pod readiness, image digest), separately from how it was provisioned.
