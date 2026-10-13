#!/usr/bin/env bash
# Report a stage result to the provisioning orchestrator, authenticated with this job's GitHub OIDC
# token (audience: the orchestrator). No secrets involved. Never fails the job on its own.
# Usage: callback.sh <stage> <status> [data-json-file]
set -uo pipefail

STAGE="$1"; STATUS="$2"; DATA_FILE="${3:-}"
: "${SPORTIFY_REQUEST_ID:?}" "${SPORTIFY_CALLBACK_URL:?}"
AUDIENCE="${SPORTIFY_CALLBACK_AUDIENCE:-sportify-orchestrator}"

if [[ -z "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" ]]; then
  echo "::warning::id-token permission missing; callback skipped (the orchestrator will reconcile)"
  exit 0
fi

TOKEN="$(curl -fsSL -H "Authorization: bearer ${ACTIONS_ID_TOKEN_REQUEST_TOKEN}" \
  "${ACTIONS_ID_TOKEN_REQUEST_URL}&audience=${AUDIENCE}" | jq -r .value)"
echo "::add-mask::${TOKEN}"

DATA='{}'
if [[ -n "${DATA_FILE}" && -s "${DATA_FILE}" ]]; then DATA="$(cat "${DATA_FILE}")"; fi

BODY="$(jq -n --arg r "${SPORTIFY_REQUEST_ID}" --arg s "${STAGE}" --arg st "${STATUS}" \
  --argjson id "${GITHUB_RUN_ID}" \
  --arg url "${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}" \
  --argjson data "${DATA}" \
  '{request_id:$r, stage:$s, status:$st, run_id:$id, run_url:$url, data:$data}')"

for attempt in 1 2 3; do
  if curl -fsS -X POST "${SPORTIFY_CALLBACK_URL}/v1/callbacks/actions" \
      -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" -d "${BODY}" >/dev/null; then
    echo "reported ${STAGE}=${STATUS}"
    exit 0
  fi
  sleep $((attempt * 5))
done
echo "::warning::callback failed after retries; the orchestrator will reconcile from the run status"
exit 0
