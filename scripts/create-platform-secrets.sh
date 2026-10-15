#!/usr/bin/env bash
# Create the platform's secrets in Key Vault from local files, OUTSIDE Terraform, so values never
# enter Terraform state or plans (docs/security/secret-management.md §6.1).
#
# Run as an operator with just-in-time "Key Vault Secrets Officer" on the platform vault (PIM).
# Afterwards set secrets_created = true in iac/platform/10-identities and re-apply to grant access.
#
# Usage: scripts/create-platform-secrets.sh <vault-name> <dir-with-secret-files>
#   <dir> must contain one file per secret, named exactly as the secret:
#     gh-app-backstage-key  gh-app-backstage-client-secret  backstage-session-secret
#     gh-app-orchestrator-key  gh-app-orchestrator-webhook-secret
#   Missing session/webhook secrets and database passwords are generated randomly. The database
#   passwords (postgres-password, backstage-db-password, orchestrator-db-password) are used by the dev
#   in-cluster PostgreSQL (deploy/charts/postgres); hex, so they are safe in any connection string.
set -euo pipefail
VAULT="${1:?usage: create-platform-secrets.sh <vault-name> <dir>}"
DIR="${2:?usage: create-platform-secrets.sh <vault-name> <dir>}"
EXPIRES="$(date -u -d '+90 days' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v+90d +%Y-%m-%dT%H:%M:%SZ)"

for name in backstage-session-secret gh-app-orchestrator-webhook-secret; do
  if [[ ! -s "${DIR}/${name}" ]]; then
    (umask 077 && openssl rand -base64 48 > "${DIR}/${name}")
    echo "generated ${name}"
  fi
done
for name in postgres-password backstage-db-password orchestrator-db-password; do
  if [[ ! -s "${DIR}/${name}" ]]; then
    (umask 077 && openssl rand -hex 32 > "${DIR}/${name}")
    echo "generated ${name}"
  fi
done

for name in gh-app-backstage-key gh-app-backstage-client-secret backstage-session-secret \
            gh-app-orchestrator-key gh-app-orchestrator-webhook-secret \
            postgres-password backstage-db-password orchestrator-db-password; do
  [[ -s "${DIR}/${name}" ]] || { echo "missing ${DIR}/${name}" >&2; exit 1; }
  az keyvault secret set --vault-name "${VAULT}" --name "${name}" --file "${DIR}/${name}" \
    --expires "${EXPIRES}" --tags owner=platform-team rotation-days=90 --output none
  echo "set ${name} (expires ${EXPIRES})"
done

echo
echo "Done. Securely delete ${DIR} now (e.g. shred -u ${DIR}/*), then re-apply 10-identities with secrets_created = true."
