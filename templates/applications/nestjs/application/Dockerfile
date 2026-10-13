# Basic multi-stage build: compile with dev dependencies, run with production dependencies only.
# Runs as a non-root user; nothing is written to the image filesystem at runtime (readOnlyRootFilesystem).
# Pin base images by digest in production (see the platform's COMPATIBILITY.md).

FROM node:24-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
COPY tsconfig*.json nest-cli.json ./
COPY src ./src
RUN npm run build && npm prune --omit=dev

FROM node:24-alpine AS runtime
ENV NODE_ENV=production PORT=3000
WORKDIR /app
RUN addgroup -S -g 10001 app && adduser -S -D -H -u 10001 -G app app
COPY --from=build --chown=10001:10001 /app/node_modules ./node_modules
COPY --from=build --chown=10001:10001 /app/dist ./dist
COPY --chown=10001:10001 package.json ./
USER 10001
EXPOSE 3000
CMD ["node", "dist/main.js"]
