#!/usr/bin/env bash
# Summarise a Terraform plan JSON for the approval card: counts and resource list (no attribute values,
# so nothing sensitive leaves the runner). Usage: plan-summary.sh plan.json plan.bin > summary.json
set -euo pipefail
PLAN_JSON="$1"; PLAN_BIN="$2"

HASH="$(sha256sum "${PLAN_BIN}" | cut -d' ' -f1)"
jq --arg hash "${HASH}" '
  [.resource_changes[] | select(.change.actions != ["no-op"] and .change.actions != ["read"])] as $c
  | {
      plan_hash: $hash,
      summary: {
        add:     ([$c[] | select(.change.actions | index("create"))] | length),
        change:  ([$c[] | select(.change.actions == ["update"])] | length),
        destroy: ([$c[] | select(.change.actions | index("delete"))] | length),
        reused:  ([.resource_changes[] | select(.mode == "data")] | length),
        resources: [$c[] | {address, type, actions: .change.actions}]
      }
    }' "${PLAN_JSON}"
