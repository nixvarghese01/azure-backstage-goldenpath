#!/usr/bin/env bash
# Records, restores and reports an application release around `helm upgrade` in
# reusable-application-deploy.yml, so a deploy never claims a rollback it didn't verify (#114).
#
#   record                  before the upgrade: the deployed Helm revision and image (none on a first install)
#   recover <check>         after a failed readiness or smoke check (outside Helm's --atomic): roll back to
#                           the recorded revision and verify it; a first install is left for diagnosis
#   report <helm-outcome>   when the deploy failed: what failed and what was (verifiably) restored
#   diagnostics             helm history, workload state, events and logs for the run's artifact
#
# Needs RELEASE and NAMESPACE; writes JSON to STATE_DIR (default: $RUNNER_TEMP/deploy-state).
set -uo pipefail

: "${RELEASE:?}" "${NAMESPACE:?}"
STATE="${STATE_DIR:-${RUNNER_TEMP:-/tmp}/deploy-state}"
mkdir -p "$STATE"
PREVIOUS="$STATE/previous.json"
OUTCOME="$STATE/outcome.json"

# The deployed revision of the release and its first container's image (and digest, once pods ran).
deployed_state() {
  local history revision image digest selector
  history="$(helm history "$RELEASE" -n "$NAMESPACE" -o json --max 50 2>/dev/null || echo '[]')"
  revision="$(jq -r '[.[] | select(.status == "deployed")] | last | .revision // empty' <<< "$history")"
  image="$(kubectl get deployment "$RELEASE" -n "$NAMESPACE" \
    -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true)"
  selector="$(kubectl get deployment "$RELEASE" -n "$NAMESPACE" -o json 2>/dev/null \
    | jq -r '.spec.selector.matchLabels // {} | to_entries | map("\(.key)=\(.value)") | join(",")' || true)"
  digest=""
  if [[ -n "$selector" ]]; then
    digest="$(kubectl get pods -n "$NAMESPACE" -l "$selector" \
      -o jsonpath='{.items[0].status.containerStatuses[0].imageID}' 2>/dev/null || true)"
  fi
  jq -n --arg r "$revision" --arg i "$image" --arg d "$digest" \
    '{revision: ($r | tonumber? // null), image: (if $i == "" then null else $i end),
      digest: (if $d == "" then null else $d end)}'
}

record() {
  deployed_state > "$PREVIOUS"
  echo "Deployed before this upgrade: $(jq -c . "$PREVIOUS")"
}

recover() {
  local check="$1" previous failed rollback message restored
  previous="$(cat "$PREVIOUS" 2>/dev/null || echo '{}')"
  failed="$(deployed_state)"
  local prev_rev prev_image
  prev_rev="$(jq -r '.revision // empty' <<< "$previous")"
  prev_image="$(jq -r '.image // empty' <<< "$previous")"
  restored='null'
  if [[ -z "$prev_rev" ]]; then
    rollback="not_possible_first_install"
    message="The first installation failed its ${check} check. There is no earlier release to restore, so the release is left installed for diagnosis; Clean up removes it."
  elif helm rollback "$RELEASE" "$prev_rev" -n "$NAMESPACE" --wait --timeout 5m \
      && kubectl rollout status deployment/"$RELEASE" -n "$NAMESPACE" --timeout 3m; then
    restored="$(deployed_state)"
    if [[ "$(jq -r '.image // empty' <<< "$restored")" == "$prev_image" ]]; then
      rollback="succeeded"
      message="The ${check} check failed after Helm finished, so revision ${prev_rev} (${prev_image}) was restored and verified as revision $(jq -r .revision <<< "$restored")."
    else
      rollback="failed"
      message="The ${check} check failed and the rollback to revision ${prev_rev} ran, but the workload runs $(jq -r '.image // "no image"' <<< "$restored"), not ${prev_image}. The release needs attention."
    fi
  else
    rollback="failed"
    restored="$(deployed_state)"
    message="The ${check} check failed and the rollback to revision ${prev_rev} (${prev_image}) failed. The failed release may still be serving; it needs attention."
  fi
  jq -n --arg c "$check" --arg rb "$rollback" --arg m "$message" \
    --argjson p "$previous" --argjson f "$failed" --argjson r "$restored" \
    '{failure: $c, rollback: $rb, message: $m, previous: $p, failed_release: $f, restored: $r}' > "$OUTCOME"
  echo "$message"
  [[ "$rollback" != "failed" ]]
}

report() {
  local helm_outcome="${1:-}" previous now rollback message
  if [[ -s "$OUTCOME" ]]; then
    jq '. + {diagnostics: "deploy-diagnostics"}' "$OUTCOME"
    return
  fi
  previous="$(cat "$PREVIOUS" 2>/dev/null || echo '{}')"
  if [[ "$helm_outcome" != "failure" ]]; then
    jq -n --argjson p "$previous" '{failure: "before_upgrade", rollback: "not_needed", previous: $p,
      message: "The deployment failed before the Helm upgrade finished; the release was not changed."}'
    return
  fi
  # Helm's --atomic undoes a failed upgrade itself; say so only if the cluster shows it.
  now="$(deployed_state)"
  if [[ "$(jq -r '.revision // empty' <<< "$previous")" == "" ]]; then
    if [[ "$(jq -r '.revision // empty' <<< "$now")" == "" ]]; then
      rollback="helm_atomic"
      message="The first installation failed; Helm (--atomic) removed it, so nothing is installed."
    else
      rollback="unknown"
      message="The first installation failed and a release is still installed; see the diagnostics."
    fi
  elif [[ "$(jq -r '.image // empty' <<< "$now")" == "$(jq -r '.image // empty' <<< "$previous")" ]]; then
    rollback="helm_atomic"
    message="The Helm upgrade failed; Helm (--atomic) restored $(jq -r .image <<< "$previous") as revision $(jq -r .revision <<< "$now")."
  else
    rollback="unknown"
    message="The Helm upgrade failed and the workload doesn't run the previous image $(jq -r .image <<< "$previous"); see the diagnostics."
  fi
  jq -n --arg rb "$rollback" --arg m "$message" --argjson p "$previous" --argjson n "$now" \
    '{failure: "deploy", rollback: $rb, message: $m, previous: $p, restored: $n, diagnostics: "deploy-diagnostics"}'
}

diagnostics() {
  local out="$STATE/diagnostics"
  mkdir -p "$out"
  helm history "$RELEASE" -n "$NAMESPACE" > "$out/helm-history.txt" 2>&1 || true
  kubectl get deployment,replicaset,pod,service -n "$NAMESPACE" -o wide > "$out/workloads.txt" 2>&1 || true
  kubectl describe pods -n "$NAMESPACE" > "$out/pods-describe.txt" 2>&1 || true
  kubectl get events -n "$NAMESPACE" --sort-by=.lastTimestamp > "$out/events.txt" 2>&1 || true
  kubectl logs deployment/"$RELEASE" -n "$NAMESPACE" --all-containers --tail=300 > "$out/logs.txt" 2>&1 || true
  cp "$PREVIOUS" "$OUTCOME" "$out/" 2>/dev/null || true
}

case "${1:-}" in
  record) record ;;
  recover) recover "${2:?check name}" ;;
  report) report "${2:-}" ;;
  diagnostics) diagnostics ;;
  *) echo "usage: $0 record | recover <check> | report <helm-outcome> | diagnostics" >&2; exit 2 ;;
esac
