# Build from the repository root:
#   docker build -f services/provisioning-orchestrator/Dockerfile .
# (The repo root is the context so the stack templates can be baked into the image.)
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
WORKDIR /src
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
COPY services/ ./
RUN if [ -f uv.lock ]; then uv sync --package provisioning-orchestrator --no-dev --frozen --no-editable; \
    else uv sync --package provisioning-orchestrator --no-dev --no-editable; fi

FROM python:3.14-slim
# pip is not needed at runtime, and its vendored certifi lags behind (GHSA-6q48-6c7w-9gw2).
RUN pip uninstall --yes pip \n    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY services/provisioning-orchestrator/alembic.ini /app/alembic.ini
COPY services/provisioning-orchestrator/migrations /app/migrations
# Stack templates rendered into the application pull request.
COPY templates/applications/nestjs/application /app/stack-templates/nestjs
COPY templates/applications/_shared /app/stack-templates/_shared
COPY templates/applications/fastapi/application /app/stack-templates/fastapi
COPY templates/applications/go/application /app/stack-templates/go
COPY templates/applications/dotnet/application /app/stack-templates/dotnet
COPY templates/applications/springboot/application /app/stack-templates/springboot
COPY templates/applications/nextjs/application /app/stack-templates/nextjs
COPY templates/applications/react/application /app/stack-templates/react
COPY templates/applications/vue/application /app/stack-templates/vue
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ORCHESTRATOR_STACK_TEMPLATES_DIR=/app/stack-templates
USER 10001
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/readyz', timeout=3)"
# API by default; the worker Deployment overrides the command with: orchestrator-worker
CMD ["uvicorn", "provisioning_orchestrator.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8002"]
