# syntax=docker/dockerfile:1
# Build from the repository root: docker build -f portal/Dockerfile -t idp/backstage:local .
FROM node:24-bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ libsqlite3-dev git ca-certificates \
    && rm -rf /var/lib/apt/lists/* && corepack enable
WORKDIR /src/portal
COPY portal/ ./
# The Backstage Yarn plugin and yarn.lock are committed, so installs are reproducible.
RUN yarn install --immutable
# --config resolves from packages/backend; the container config needs no GitHub App credentials file.
RUN yarn build:backend --config ../../app-config.container.yaml
# Assemble the standard backend skeleton and bundle with production dependencies only.
RUN mkdir /runtime && tar -xzf packages/backend/dist/skeleton.tar.gz -C /runtime \
    && cp package.json yarn.lock .yarnrc.yml backstage.json /runtime/ \
    && cp -r .yarn /runtime/.yarn
WORKDIR /runtime
RUN yarn workspaces focus backend --production && yarn cache clean
RUN tar -xzf /src/portal/packages/backend/dist/bundle.tar.gz -C /runtime

FROM node:24-bookworm-slim AS runtime-base
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV NODE_ENV=production NODE_OPTIONS="--no-node-snapshot" CATALOG_BRANCH=main GITHUB_OWNER_TYPE=organization
WORKDIR /app
COPY --from=build --chown=node:node /runtime/ ./
COPY --chown=node:node portal/app-config.container.yaml portal/app-config.docker.yaml portal/app-config.docs.yaml portal/app-config.lite.yaml portal/app-config.production.yaml ./
COPY --chown=node:node portal/catalog/ ./catalog/
# The portal only needs the infrastructure scaffold; the worker owns application generation.
COPY --chown=node:node templates/applications/nestjs/template.yaml ./templates/applications/nestjs/template.yaml
COPY --chown=node:node templates/applications/nestjs/skeleton/ ./templates/applications/nestjs/skeleton/
USER node
EXPOSE 7007
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD node -e "fetch('http://127.0.0.1:7007/.backstage/health/v1/readiness').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "packages/backend", "--config", "app-config.container.yaml", "--config", "app-config.production.yaml"]

# Local default: prebuilt TechDocs only; omit Python, MkDocs and documentation source.
FROM runtime-base AS runtime-lite
CMD ["node", "packages/backend", "--config", "app-config.container.yaml", "--config", "app-config.production.yaml", "--config", "app-config.lite.yaml"]

# Default release image preserves on-demand TechDocs generation.
FROM runtime-base AS runtime
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/mkdocs \
    && /opt/mkdocs/bin/pip install --no-cache-dir mkdocs-techdocs-core
ENV PATH="/opt/mkdocs/bin:$PATH"
COPY --chown=node:node docs/ ./docs/
USER node
