# Backstage backend image (host build). From portal/:
#   yarn install --immutable && yarn tsc && yarn build:backend
#   docker build -f packages/backend/Dockerfile .
FROM node:24-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/mkdocs && /opt/mkdocs/bin/pip install --no-cache-dir mkdocs-techdocs-core
ENV PATH="/opt/mkdocs/bin:$PATH"

USER node
WORKDIR /app
ENV NODE_ENV=production NODE_OPTIONS="--no-node-snapshot"

COPY --chown=node:node .yarn ./.yarn
COPY --chown=node:node .yarnrc.yml backstage.json yarn.lock package.json ./
COPY --chown=node:node packages/backend/dist/skeleton.tar.gz ./
RUN tar xzf skeleton.tar.gz && rm skeleton.tar.gz
RUN yarn workspaces focus --all --production && rm -rf "$(yarn cache clean)"

COPY --chown=node:node packages/backend/dist/bundle.tar.gz app-config*.yaml ./
COPY --chown=node:node catalog ./catalog
RUN tar xzf bundle.tar.gz && rm bundle.tar.gz

EXPOSE 7007
CMD ["node", "packages/backend", "--config", "app-config.yaml", "--config", "app-config.production.yaml"]
