#!/usr/bin/env bash
# Fingerprint of a plan's changes (resource addresses and actions, no values), from plan-summary.sh's
# JSON on stdin. Two plans with the same fingerprint make the same changes. platform-apply compares
# the approved preview with the plan it applies.
set -euo pipefail
jq -r '.summary.resources[]? | "\(.address) \(.actions | join("/"))"' | LC_ALL=C sort | sha256sum | cut -d' ' -f1
