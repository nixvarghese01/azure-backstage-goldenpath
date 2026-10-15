# Portal dependency alerts: decisions

Dependabot alerts on `portal/yarn.lock` and `portal/packages/app/package.json`, reviewed 2026-10-15 (#13).
All are transitive through Backstage 1.55 or its tooling. Where a fix exists inside the ranges the
dependents allow, it is applied with a Yarn resolution (`portal/package.json`); everything else needs a
breaking major that the dependents don't accept, or has no fix, and is accepted below with the reason.

**Review again by 2026-12-15** (with #16): on each Backstage upgrade, re-run `yarn why <package>` for the
rows below and drop the ones that are gone.

## Fixed

| Package | Was | Now | How |
|---|---|---|---|
| `prismjs` (DOM clobbering, moderate) | 1.27.0 via `refractor` (`~1.27.0`) | 1.30.0 | resolution `prismjs@npm:~1.27.0` → `1.30.0` (minor) |

## Accepted

| Package (severity) | Version, path | Fix | Why accepted |
|---|---|---|---|
| `@graphql-tools/utils` (high) | 8.9.0, `@graphql-tools/merge`/`schema` 8 (mockttp in `@backstage/backend-openapi-utils`) | 12.x | Exact pin; test-time HTTP mocking only. Also in `.trivyignore.yaml` until 2026-12-15. |
| `basic-ftp` (high) | 5.3.1 via `get-uri` | 6.x | Only for `ftp://` URLs, which the portal never fetches. Also in `.trivyignore.yaml`. |
| `node-forge` (high) | 1.4.0 via `@backstage/backend-defaults` | none | No patched release. The backend's HTTPS support (self-signed certificates); the deployed backend serves plain HTTP on 7007 behind the Gateway. |
| `braces` (high) | 3.0.3 via `chokidar`, `micromatch` | none | No patched release. Build and file-watch tooling; patterns come from config, not users. |
| `react-router` (moderate, ×4) | 6.30.6, `packages/app` and `react-router-dom` | 7.x | Backstage 1.55's legacy frontend requires react-router 6. |
| `postcss-selector-parser` (moderate) | 6.1.4 via `postcss-calc`, `postcss-merge-rules` | 7.x | Build-time CSS minification of the portal's own styles. |
| `uuid` (moderate) | 3.4.0 / 8 / 9 / 10 via `@material-table/core` and others | 11.1.1 | The advisory needs a caller-supplied `buf`; dependents only generate IDs. |
| `file-type` (moderate) | 16.5.4 via `@trendyol-js/openstack-swift-sdk` | 21.x | OpenStack Swift TechDocs storage, which this portal doesn't use (local TechDocs). |
| `@octokit/request`, `request-error`, `plugin-paginate-rest` (moderate) | 6.2.8 / 3.0.3 / 6.1.2 via `@octokit/auth-app` 4 and `@octokit/rest` 19 | 8.x / 5.x / 9.x | ReDoS on responses from GitHub's API (trusted). Newer majors are already used where dependents allow. |
| `sprintf-js` (moderate) | 1.0.3 via `argparse` 1 | none | No patched release. CLI argument parsing in build tooling. |
| `elliptic` (low) | 6.6.1 via `browserify-sign`, `create-ecdh` | none | No patched release. Browser crypto polyfills in the bundler; the portal signs nothing in the browser. |

Dismissed in GitHub with reason "tolerable risk" and a link to this page, so a new alert stands out.
