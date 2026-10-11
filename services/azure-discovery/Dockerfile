# Build from the services/ directory:  docker build -f azure-discovery/Dockerfile .
# Pin base images by digest when building releases (see COMPATIBILITY.md).
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
WORKDIR /src
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock* ./
COPY libs ./libs
COPY azure-discovery ./azure-discovery
RUN uv sync --package azure-discovery --no-dev --frozen --no-editable || \
    uv sync --package azure-discovery --no-dev --no-editable

FROM python:3.14-slim
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=build /src/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 DISCOVERY_POLICY_FILE=/etc/sportify/allowlist.yaml
USER 10001
EXPOSE 8001
CMD ["uvicorn", "azure_discovery.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
