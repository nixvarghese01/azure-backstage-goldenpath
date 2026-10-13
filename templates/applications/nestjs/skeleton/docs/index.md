# ${{ values.name }}

${{ values.description }}

| | |
|---|---|
| Owner | `${{ values.owner }}` |
| Environment | `${{ values.environment }}` |
| Endpoint | `https://${{ values.endpointHost }}` |
| Availability tier | `${{ values.availabilityTier }}` |
| Platform request | `${{ values.requestId }}` |

## Runbook

- **Health:** `GET /health/live` (process up), `GET /health/ready` (dependencies, including Azure Storage through Workload Identity).
- **Logs:** `kubectl logs -n ${{ values.name }} deploy/${{ values.name }}` (namespace-scoped access through the deployment identity, or your team's read role).
- **Redeploy:** re-run the `application-deploy` workflow on `main`.
- **Rollback:** Helm deploys with `--atomic`, so failed deploys roll back automatically. To roll back a good-but-unwanted release, revert the commit on `main`.
