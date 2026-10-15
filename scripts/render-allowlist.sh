#!/usr/bin/env bash
# Write the allowlist for one environment: policies/allowlist.yaml (example IDs only) with the
# environment's real IDs merged over it. Top-level maps merge key by key; lists are replaced.
#
# Usage: PLATFORM_ALLOWLIST_JSON='{...}' scripts/render-allowlist.sh <allowlist.yaml> <output.yaml>
#   PLATFORM_ALLOWLIST_JSON comes from `scripts/bootstrap-platform.sh allowlist` (a repository secret).
#   Empty: the file is copied unchanged (mock mode, CI).
# Needs: yq v4 (preinstalled on GitHub-hosted Ubuntu runners).
set -euo pipefail
IN="${1:?usage: render-allowlist.sh <allowlist.yaml> <output.yaml>}"
OUT="${2:?usage: render-allowlist.sh <allowlist.yaml> <output.yaml>}"
if [[ -z "${PLATFORM_ALLOWLIST_JSON:-}" ]]; then
  cp "$IN" "$OUT"; echo "PLATFORM_ALLOWLIST_JSON not set: allowlist copied unchanged (example IDs)"; exit 0
fi
command -v yq >/dev/null || { echo "yq v4 is required" >&2; exit 1; }
overlay="$(mktemp)"; trap 'rm -f "$overlay"' EXIT
printf '%s' "$PLATFORM_ALLOWLIST_JSON" > "$overlay"
yq -p json -o json '.' "$overlay" >/dev/null || { echo "PLATFORM_ALLOWLIST_JSON is not valid JSON" >&2; exit 1; }
yq eval-all '(select(fileIndex == 0) * select(fileIndex == 1)) | ... style=""' "$IN" "$overlay" > "$OUT"
# The placeholder must not survive: discovery would offer a subscription that doesn't exist.
if grep -q '00000000-0000-0000-0000-000000000000\|aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' "$OUT"; then
  echo "allowlist still has example IDs after the merge; extend PLATFORM_ALLOWLIST_JSON" >&2; exit 1
fi
echo "allowlist rendered for this environment"
