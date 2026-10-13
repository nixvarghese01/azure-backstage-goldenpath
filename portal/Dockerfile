# syntax=docker/dockerfile:1
# Build from the repository root: docker build -f portal/Dockerfile -t sportify/backstage:local .
FROM node:24-bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ libsqlite3-dev git ca-certificates \
    && rm -rf /var/lib/apt/lists/* && corepack enable
WORKDIR /src/portal
COPY portal/ ./
# The handwritten workspace has no lockfile yet. Once committed, builds enforce it.
RUN yarn plugin import https://versions.backstage.io/v1/tags/main/yarn-plugin \
    && if [ -f yarn.lock ]; then yarn install --immutable; else YARN_ENABLE_IMMUTABLE_INSTALLS=false yarn install; fi
RUN yarn build:backend --config app-config.container.yaml
# Assemble the standard backend skeleton and bundle with production dependencies only.
RUN mkdir /runtime && tar -xzf packages/backend/dist/skeleton.tar.gz -C /runtime \
    && cp package.json yarn.lock .yarnrc.yml backstage.json /runtime/ \
    && cp -r .yarn /runtime/.yarn
WORKDIR /runtime
RUN yarn workspaces focus --all --production && yarn cache clean
RUN tar -xzf /src/portal/packages/backend/dist/bundle.tar.gz -C /runtime

FROM node:24-bookworm-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/mkdocs \
    && /opt/mkdocs/bin/pip install --no-cache-dir mkdocs-techdocs-core
ENV PATH="/opt/mkdocs/bin:$PATH" NODE_ENV=production NODE_OPTIONS="--no-node-snapshot"
WORKDIR /app
COPY --from=build --chown=node:node /runtime/ ./
COPY --chown=node:node portal/app-config.container.yaml portal/app-config.docker.yaml portal/app-config.production.yaml ./
COPY --chown=node:node portal/catalog/ ./catalog/
COPY --chown=node:node templates/ ./templates/
COPY --chown=node:node docs/ ./docs/
USER node
EXPOSE 7007
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD node -e "fetch('http://127.0.0.1:7007/.backstage/health/v1/readiness').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "packages/backend", "--config", "app-config.container.yaml", "--config", "app-config.production.yaml"]
