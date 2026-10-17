# Build from the repository root: docker build -f services/azure-discovery/Dockerfile .
# Pin base images by digest when building releases (see COMPATIBILITY.md).
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
WORKDIR /src
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
# Include the complete workspace: uv must resolve every declared member.
COPY services/ ./
RUN if [ -f uv.lock ]; then uv sync --package azure-discovery --no-dev --frozen --no-editable; \
    else uv sync --package azure-discovery --no-dev --no-editable; fi

FROM python:3.14-slim
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY policies/allowlist.yaml /etc/idp/allowlist.yaml
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DISCOVERY_POLICY_FILE=/etc/idp/allowlist.yaml
USER 10001
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/readyz', timeout=3)"
CMD ["uvicorn", "azure_discovery.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
