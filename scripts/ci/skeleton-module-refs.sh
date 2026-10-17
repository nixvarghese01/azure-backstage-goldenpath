#!/usr/bin/env bash
# Print every module tag the application skeleton pins (one `<module>/vX.Y.Z` per line, sorted).
# Fails if a source's tag prefix doesn't match its module directory, which would pin the wrong module.
# Usage: skeleton-module-refs.sh [skeleton terraform dir]
set -euo pipefail

DIR="${1:-templates/applications/nestjs/skeleton/infra/terraform}"
PATTERN='iac/modules/[a-z0-9-]+\?ref=[^"]+'

status=0
while read -r source; do
  module="${source#iac/modules/}"; module="${module%%\?*}"
  ref="${source#*\?ref=}"
  if [[ ! "${ref}" =~ ^${module}/v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "::error::${source}: ref must be ${module}/vX.Y.Z" >&2
    status=1
  fi
  echo "${ref}"
done < <(grep -rhoE "${PATTERN}" "${DIR}" | sort -u)

exit "${status}"
