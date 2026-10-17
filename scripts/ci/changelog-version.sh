#!/usr/bin/env bash
# Release version and notes from CHANGELOG.md (Keep a Changelog). Used by the release and
# branch-policy workflows.
#   changelog-version.sh              prints the newest "## [X.Y.Z]" version; fails if there is none
#   changelog-version.sh --notes V    prints the body of version V's section
set -euo pipefail
FILE="${CHANGELOG:-CHANGELOG.md}"
if [[ "${1:-}" == --notes ]]; then
  version="${2:?usage: changelog-version.sh --notes X.Y.Z}"
  # The section's lines up to the next "## [", without link references.
  awk -v head="## [$version]" '/^## \[/ { p = index($0, head) == 1; next } p' "$FILE" \
    | grep -vE '^\[[^]]+\]: https?://' || true
  exit 0
fi
version="$(sed -nE 's/^## \[([0-9]+\.[0-9]+\.[0-9]+)\].*/\1/p' "$FILE" | head -1)"
[[ -n "$version" ]] || { echo "::error::${FILE} has no '## [X.Y.Z] - <date>' section" >&2; exit 1; }
echo "$version"
