#!/usr/bin/env bash
# shellcheck disable=SC2015  # `check && ok || fail`: ok/warn/fail always succeed
# One-time platform bootstrap, run by a platform admin with `az login` and `gh auth login`.
#
# The pipelines (platform-provision.yml, platform-apply.yml, platform-release.yml) sign in to Azure with
# identities that 10-identities creates, and keep Terraform state in the storage that 00-bootstrap
# creates. Those two stacks therefore run once from here; everything after them runs in the pipeline.
#
# Steps, each safe to re-run, each run separately so you can review before anything is created:
#   preflight    read-only: Azure and GitHub sign-in, tools, providers, vCPU quota, stack inputs
#   providers    register the resource providers and the EncryptionAtHost feature
#   state        00-bootstrap: Terraform state storage, then migrate its own state into it
#   identities   10-identities: GitHub-federated identities, service identities, Key Vault, Entra apps
#   github       repository variables and environments the pipelines read (IDs only, no secrets)
#
# Cost guard: every step that touches Azure stops unless the subscription is a Free Trial (or other
# credit-based offer) with its spending limit on, so usage comes out of the credit and the subscription
# is disabled, not billed, when the credit ends. Set IDP_ALLOW_BILLED_SUBSCRIPTION=true to lift it.
#
# Usage: scripts/bootstrap-platform.sh <step> [--env dev] [--location uksouth]
# Needs: az, gh, terraform ~> 1.16, python3. Inputs: iac/platform/{10-identities,20-shared-dev,
# 30-cluster-config}/terraform.tfvars, copied from the .example files with your IDs.
set -euo pipefail

STEP="${1:-}"; shift || true
ENVIRONMENT="dev"
LOCATION="uksouth"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENVIRONMENT="$2"; shift 2 ;;
    --location) LOCATION="$2"; shift 2 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLATFORM="${ROOT}/iac/platform"
PY="$(command -v python3 || command -v python)"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo nixvarghese01/azure-backstage-goldenpath)"
STATE_RG="rg-idp-tfstate-${ENVIRONMENT}"
PROVIDERS=(Microsoft.ContainerService Microsoft.ContainerRegistry Microsoft.KeyVault Microsoft.DBforPostgreSQL
  Microsoft.Network Microsoft.Storage Microsoft.ManagedIdentity Microsoft.Compute Microsoft.OperationalInsights)

ok() { printf '  \033[32mok\033[0m   %s\n' "$*"; }
warn() { printf '  \033[33mwarn\033[0m %s\n' "$*"; }
fail() { printf '  \033[31mfail\033[0m %s\n' "$*"; FAILED=1; }
json() { "$PY" -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1], {'d': d}))" "$1"; }

# State storage name, from 10-identities' inputs (the single place it is configured).
state_account() {
  sed -nE 's/^state_storage_account_name *= *"([^"]+)".*/\1/p' "${PLATFORM}/10-identities/terraform.tfvars" 2>/dev/null \
    || true
}

# backend.hcl for a stack. Locally Terraform uses your az login; the pipeline variant adds use_oidc.
backend_hcl() { # <stack> [oidc]
  cat <<EOF
resource_group_name  = "${STATE_RG}"
storage_account_name = "$(state_account)"
container_name       = "platform"
key                  = "platform/$1.tfstate"
use_azuread_auth     = true
EOF
  [[ "${2:-}" == oidc ]] && echo "use_oidc             = true"
  return 0
}

# Spending limit and offer of the signed-in subscription (Reader is enough).
cost_guard() {
  local sub policies limit quota
  sub="$(az account show --query id -o tsv)"
  policies="$(az rest --method get --url "https://management.azure.com/subscriptions/${sub}?api-version=2022-12-01"     --query subscriptionPolicies -o json)"
  limit="$(json "d.get('spendingLimit') or 'unknown'" <<< "$policies")"
  quota="$(json "d.get('quotaId') or 'unknown'" <<< "$policies")"
  if [[ "$limit" == On ]]; then
    ok "spending limit On (${quota}): usage comes out of the credit; no charges to your card"
  elif [[ "${IDP_ALLOW_BILLED_SUBSCRIPTION:-}" == true ]]; then
    warn "spending limit ${limit} (${quota}): charges allowed by IDP_ALLOW_BILLED_SUBSCRIPTION"
  else
    fail "spending limit ${limit} (${quota}): this subscription can be billed. Use a Free Trial with the spending limit on, or set IDP_ALLOW_BILLED_SUBSCRIPTION=true"
    exit 1
  fi
}

preflight() {
  FAILED=0
  echo "Azure"
  if sub="$(az account show -o json 2>/dev/null)" && az group list --query "[0].name" -o tsv >/dev/null 2>&1; then
    ok "signed in: $(json "d['name']" <<< "$sub") ($(json "d['id']" <<< "$sub")), tenant $(json "d['tenantId']" <<< "$sub")"
  else
    fail "not signed in or token expired: az login --tenant <tenant id>"
  fi
  echo "GitHub"
  gh auth status >/dev/null 2>&1 && ok "gh signed in, repository ${REPO}" || fail "gh auth login"
  echo "Tools"
  tf="$(terraform version -json 2>/dev/null | json "d['terraform_version']" || true)"
  [[ "$tf" == 1.16.* ]] && ok "terraform ${tf}" || fail "terraform ~> 1.16 needed (found ${tf:-none})"
  [[ -n "$PY" ]] && ok "python $("$PY" --version 2>&1 | cut -d' ' -f2)" || fail "python3 needed"
  [[ -n "${FAILED}" && "${FAILED}" == 1 ]] && { echo "Fix the above first."; exit 1; }

  echo "Cost"
  cost_guard

  echo "Resource providers"
  for p in "${PROVIDERS[@]}"; do
    s="$(az provider show -n "$p" --query registrationState -o tsv 2>/dev/null || echo unknown)"
    [[ "$s" == Registered ]] && ok "$p" || warn "$p: $s (run: $0 providers)"
  done
  s="$(az feature show --namespace Microsoft.Compute --name EncryptionAtHost --query properties.state -o tsv 2>/dev/null || echo unknown)"
  [[ "$s" == Registered ]] && ok "feature EncryptionAtHost" || warn "feature EncryptionAtHost: $s (run: $0 providers)"

  local vm family
  vm="$(sed -nE 's/^ *vm_size *= *"([^"]+)".*//p' "${PLATFORM}/20-shared-dev/terraform.tfvars" 2>/dev/null | head -1)"
  vm="${vm:-Standard_D2s_v5}"
  case "$vm" in
    Standard_B*_v2) family=standardBsv2Family ;;
    Standard_B*) family=standardBSFamily ;;
    Standard_D*as_v5) family=standardDASv5Family ;;
    *) family=standardDSv5Family ;;
  esac
  echo "vCPU quota in ${LOCATION} (AKS node: ${vm} = 2 vCPU)"
  usage="$(az vm list-usage -l "$LOCATION" -o json 2>/dev/null || echo '[]')"
  read -r used limit < <(json "' '.join(str(u[k]) for u in d if u['name']['value']=='cores' for k in ('currentValue','limit')) or '0 0'" <<< "$usage")
  if (( limit - used >= 2 )); then ok "total regional vCPUs ${used}/${limit}"; else fail "total regional vCPUs ${used}/${limit}: request a quota increase or choose another region"; fi
  read -r used limit < <(json "' '.join(str(u[k]) for u in d if u['name']['value']=='${family}' for k in ('currentValue','limit')) or '0 0'" <<< "$usage")
  if (( limit - used >= 2 )); then ok "${family} ${used}/${limit}"; else fail "${family} ${used}/${limit}: request an increase, or set another vm_size in 20-shared-dev"; fi

  echo "Stack inputs (git-ignored; IDs only)"
  for s in 10-identities 20-shared-dev; do
    f="${PLATFORM}/${s}/terraform.tfvars"
    if [[ ! -f "$f" ]]; then fail "$s/terraform.tfvars missing: copy terraform.tfvars.example and fill in your IDs"
    elif grep -q "00000000-0000-0000-0000-000000000000\|\"000000000\"" "$f"; then fail "$s/terraform.tfvars still has placeholder IDs"
    else ok "$s/terraform.tfvars"; fi
  done
  [[ -f "${PLATFORM}/30-cluster-config/terraform.tfvars" ]] && ok "30-cluster-config/terraform.tfvars" \
    || warn "30-cluster-config/terraform.tfvars missing (defaults are used)"
  [[ "${FAILED}" == 0 ]] && echo "Preflight passed." || { echo "Preflight found problems."; exit 1; }
}

providers() {
  FAILED=0; cost_guard
  for p in "${PROVIDERS[@]}"; do az provider register -n "$p" -o none && echo "registering $p"; done
  az feature register --namespace Microsoft.Compute --name EncryptionAtHost -o none
  echo "Waiting for EncryptionAtHost (can take ~15 minutes)..."
  until [[ "$(az feature show --namespace Microsoft.Compute --name EncryptionAtHost --query properties.state -o tsv)" == Registered ]]; do sleep 30; done
  az provider register -n Microsoft.Compute -o none
  echo "Providers and EncryptionAtHost registered."
}

state() {
  FAILED=0; cost_guard
  local dir="${PLATFORM}/00-bootstrap" account
  account="$(state_account)"
  [[ -n "$account" ]] || { echo "Set state_storage_account_name in 10-identities/terraform.tfvars first."; exit 1; }
  local suffix="${account#stidptfstate"${ENVIRONMENT}"}"
  cd "$dir"
  if [[ ! -f backend.tf ]]; then
    # First run: local state, create the storage, then move this stack's own state into it.
    terraform init -input=false
    terraform apply -var "environment=${ENVIRONMENT}" -var "location=${LOCATION}" -var "name_suffix=${suffix}"
    # The deployer needs data-plane access: shared keys are disabled (Entra only).
    me="$(az ad signed-in-user show --query id -o tsv)"
    az role assignment create --assignee-object-id "$me" --assignee-principal-type User \
      --role "Storage Blob Data Contributor" --scope "$(terraform output -raw storage_account_id)" -o none || true
    echo "Waiting 60s for the role assignment to propagate..."; sleep 60
    cp backend.tf.example backend.tf
    backend_hcl 00-bootstrap > backend.hcl
    terraform init -input=false -migrate-state -force-copy -backend-config=backend.hcl
    rm -f terraform.tfstate terraform.tfstate.backup
    echo "State storage ${account} created; 00-bootstrap state now lives in it (platform/00-bootstrap.tfstate)."
  else
    backend_hcl 00-bootstrap > backend.hcl
    terraform init -input=false -backend-config=backend.hcl
    terraform apply -var "environment=${ENVIRONMENT}" -var "location=${LOCATION}" -var "name_suffix=${suffix}"
  fi
}

identities() {
  FAILED=0; cost_guard
  cd "${PLATFORM}/10-identities"
  backend_hcl 10-identities > backend.hcl
  terraform init -input=false -backend-config=backend.hcl
  terraform apply -var-file=terraform.tfvars
}

github() {
  FAILED=0; cost_guard
  local out tenant sub
  out="$(cd "${PLATFORM}/10-identities" && terraform output -json)"
  tenant="$(json "d['tenant_id']['value']" <<< "$out")"
  sub="$(az account show --query id -o tsv)"
  cid() { json "d['client_ids']['value']['$1']" <<< "$out"; }

  echo "Repository variables on ${REPO} (identifiers only)"
  setvar() { gh variable set "$1" --repo "$REPO" --body "$2" >/dev/null && ok "$1"; }
  setvar AZURE_TENANT_ID "$tenant"
  setvar AZURE_SUBSCRIPTION_ID "$sub"
  setvar PLATFORM_CLIENT_ID "$(cid platform)"
  setvar PLATFORM_PLAN_CLIENT_ID "$(cid platform_plan)"
  setvar PLATFORM_DEPLOY_CLIENT_ID "$(cid platform_deploy)"
  setvar VENDING_CLIENT_ID "$(cid vending)"
  setvar BACKSTAGE_CLIENT_ID "$(cid backstage)"
  setvar DISCOVERY_CLIENT_ID "$(cid discovery)"
  setvar ORCHESTRATOR_CLIENT_ID "$(cid orchestrator)"
  setvar PLATFORM_BACKEND_HCL "$(backend_hcl __STACK__ oidc)"
  setvar PLATFORM_TFVARS_JSON "$("$PY" - "$PLATFORM" <<'EOF'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
print(json.dumps({s: (root / s / "terraform.tfvars").read_text(encoding="utf-8")
                  for s in ("10-identities", "20-shared-dev", "30-cluster-config")
                  if (root / s / "terraform.tfvars").exists()}))
EOF
)"
  local tfv="${PLATFORM}/20-shared-dev/terraform.tfvars"
  setvar ACR_NAME "$(sed -nE '/^acr *=/,/^}/ s/^ *name *= *"([^"]+)".*/\1/p' "$tfv" | head -1)"
  setvar AKS_NAME "$(sed -nE '/^aks *=/,/^}/ s/^ *name *= *"([^"]+)".*/\1/p' "$tfv" | head -1)"
  setvar AKS_RESOURCE_GROUP "rg-idp-platform-${ENVIRONMENT}"
  local outputs; outputs="$(mktemp)"; printf '%s' "$out" > "$outputs"
  setvar PLATFORM_CHART_VALUES_JSON "$("$PY" - "$tfv" "$ENVIRONMENT" "$outputs" <<'EOF'
import json, re, sys
out = json.load(open(sys.argv[3], encoding="utf-8"))
tfvars, env = open(sys.argv[1], encoding="utf-8").read(), sys.argv[2]
pg = re.search(r'^postgres_name\s*=\s*"([^"]+)"', tfvars, re.M).group(1) + ".postgres.database.azure.com"
auth, pid, tenant = out["service_auth"]["value"], out["principal_ids"]["value"], out["tenant_id"]["value"]
kv = out["key_vault_name"]["value"]
# Single-node dev cluster: one replica each. GitHub App IDs are added once the apps exist (#19).
print(json.dumps({
  "backstage": json.dumps({"replicas": 1, "keyVault": {"name": kv, "tenantId": tenant}, "env": {
      "POSTGRES_HOST": pg, "POSTGRES_USER": f"id-idp-backstage-{env}", "AZURE_TENANT_ID": tenant,
      "DISCOVERY_ENTRA_SCOPE": auth["discovery"]["scope"], "ORCHESTRATOR_ENTRA_SCOPE": auth["orchestrator"]["scope"],
      "BACKSTAGE_ENTRA_AUDIENCE": auth["backstage"]["audience"]}}),
  "azure-discovery": json.dumps({"replicas": 1, "auth": {"tenantId": tenant, "audience": auth["discovery"]["audience"],
      "allowedCallers": f'{pid["backstage"]},{pid["orchestrator"]}'}}),
  "provisioning-orchestrator": json.dumps({"api": {"replicas": 1}, "worker": {"replicas": 1},
      "keyVault": {"name": kv, "tenantId": tenant},
      "database": {"url": f"postgresql+psycopg://id-idp-orchestrator-{env}@{pg}:5432/orchestrator?sslmode=require"},
      "auth": {"tenantId": tenant, "audience": auth["orchestrator"]["audience"], "allowedCallers": pid["backstage"]},
      # Single-person demo: the requester may approve in dev only (never prod), recorded as self_approved.
      "config": {"discoveryScope": auth["discovery"]["scope"], "backstageScope": auth["backstage"]["scope"],
                 "selfApprovalEnvironments": env if env != "prod" else ""}}),
}))
EOF
)"
  rm -f "$outputs"

  echo "Environments (deployments limited to develop and main)"
  local me; me="$(gh api user -q .id)"
  # platform-plan: read-only. platform-teardown: destroy-only, no reviewers, so TTL teardown never waits.
  for e in platform platform-deploy platform-plan platform-teardown; do
    if [[ "$e" == platform-plan || "$e" == platform-teardown ]]; then
      body='{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}'
    else
      body="{\"reviewers\":[{\"type\":\"User\",\"id\":${me}}],\"deployment_branch_policy\":{\"protected_branches\":false,\"custom_branch_policies\":true}}"
    fi
    gh api -X PUT "repos/${REPO}/environments/${e}" --input - <<< "$body" >/dev/null
    for b in develop main; do
      gh api -X POST "repos/${REPO}/environments/${e}/deployment-branch-policies" -f name="$b" -f type=branch >/dev/null 2>&1 || true
    done
    case "$e" in
      platform-plan) ok "$e (read-only)" ;;
      platform-teardown) ok "$e (destroy only, no approval)" ;;
      *) ok "$e (you approve each run)" ;;
    esac
  done
  echo "Done. Next: Actions -> platform-provision -> Run workflow on develop (pick ttl_hours)."
  echo "platform-ttl tears the platform down when ttl_hours expires; check it hourly in Actions."
}

case "$STEP" in
  preflight) preflight ;;
  providers) providers ;;
  state) state ;;
  identities) identities ;;
  github) github ;;
  *) sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
