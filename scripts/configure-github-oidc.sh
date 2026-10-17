#!/usr/bin/env bash
# One-time GitHub organisation setup for ADR-0005: customise the Actions OIDC subject claim so Azure
# federated credentials can trust the platform's reusable workflows (job_workflow_ref) per environment.
# Requires: gh CLI authenticated as an organisation owner.
# Usage: scripts/configure-github-oidc.sh <org>
set -euo pipefail
ORG="${1:?usage: configure-github-oidc.sh <org>}"

gh api --method PUT "orgs/${ORG}/actions/oidc/customization/sub" \
  -f 'include_claim_keys[]=repository_owner_id' \
  -f 'include_claim_keys[]=environment' \
  -f 'include_claim_keys[]=job_workflow_ref'

echo "Organisation ${ORG} now issues subjects like:"
echo "  repository_owner_id:<id>:environment:<env>:job_workflow_ref:<org>/<repo>/.github/workflows/<wf>@<ref>"
echo
echo "The platform repository keeps the default repo-based subject (its own workflows use it):"
gh api --method PUT "repos/${ORG}/azure-backstage-goldenpath/actions/oidc/customization/sub" -F use_default=true
echo "Organisation ID (github_org_id in iac/platform/10-identities): $(gh api "orgs/${ORG}" --jq .id)"
