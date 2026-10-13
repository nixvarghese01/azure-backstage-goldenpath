#!/usr/bin/env bash
# Fetch DEV GitHub App credentials from a dev Key Vault into ~/.config/sportify (outside the repo, 0600).
# Uses your own `az login`; nothing is printed. See docs/security/secret-management.md §9.
# Usage: scripts/dev-secrets.sh <dev-key-vault-name>
set -euo pipefail
VAULT="${1:?usage: dev-secrets.sh <dev-key-vault-name>}"
DIR="${HOME}/.config/sportify"
umask 077
mkdir -p "${DIR}"

fetch() { # secret-name file
  az keyvault secret show --vault-name "${VAULT}" --name "$1" --query value -o tsv > "${DIR}/$2"
  chmod 600 "${DIR}/$2"
  echo "wrote ${DIR}/$2"
}

fetch gh-app-orchestrator-key gh-app-orchestrator-key.pem
fetch gh-app-orchestrator-webhook-secret gh-app-orchestrator-webhook-secret
fetch gh-app-backstage-credentials gh-app-backstage.yaml   # appId, clientId, clientSecret, privateKey (YAML)
