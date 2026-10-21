from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    database_url: str
    database_entra_auth: bool
    # Password read from a file (Key Vault via the CSI driver) for each new connection; for the dev
    # in-cluster PostgreSQL. None with Entra authentication.
    database_password_file: str | None
    discovery_base_url: str
    discovery_scope: str | None  # Entra scope for discovery (None in static/dev mode)
    github_mode: str  # "app" | "mock"
    github_org: str
    github_app_id: str | None
    github_installation_id: str | None
    platform_repo: str
    platform_repo_ref: str
    backstage_base_url: str  # in-cluster API calls (notifications, catalog)
    backstage_public_url: str  # links people open (the Provisioning tab's "Backstage entity")
    app_url_scheme: str  # "https" with TLS on the Gateway, "http" without
    backstage_scope: str | None
    callback_audience: str
    approver_group: str
    # Environments where an approver may approve their own request (single-person demos). Empty by
    # default, so separation of duties applies everywhere; "prod" is always refused.
    self_approval_environments: frozenset[str]
    stack_templates_dir: Path
    infra_environment: str  # GitHub environment holding the custom protection rule
    worker_poll_seconds: float
    worker_lease_seconds: int
    reconcile_interval_seconds: int
    max_step_attempts: int
    log_level: str
    # Operations view (#115): how long one cluster observation is reused, and optional links with
    # {app}, {namespace}, {environment} and {request_id} placeholders (set by the monitoring stack, #107).
    operations_cache_seconds: float = 15.0
    operations_links: dict[str, str | None] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=_env("ORCHESTRATOR_DATABASE_URL", "sqlite:///./orchestrator.db") or "",
            database_entra_auth=(_env("ORCHESTRATOR_DATABASE_ENTRA_AUTH", "false") or "").lower() == "true",
            database_password_file=_env("ORCHESTRATOR_DATABASE_PASSWORD_FILE"),
            discovery_base_url=(_env("DISCOVERY_BASE_URL", "http://azure-discovery:8001") or "").rstrip("/"),
            discovery_scope=_env("DISCOVERY_ENTRA_SCOPE"),
            github_mode=(_env("ORCHESTRATOR_GITHUB_MODE", "app") or "app").lower(),
            github_org=_env("ORCHESTRATOR_GITHUB_ORG", "nixvarghese01") or "nixvarghese01",
            github_app_id=_env("ORCHESTRATOR_GITHUB_APP_ID"),
            github_installation_id=_env("ORCHESTRATOR_GITHUB_APP_INSTALLATION_ID"),
            platform_repo=_env("ORCHESTRATOR_PLATFORM_REPO", "azure-backstage-goldenpath") or "",
            platform_repo_ref=_env("ORCHESTRATOR_PLATFORM_REPO_REF", "main") or "main",
            backstage_base_url=(
                _env("ORCHESTRATOR_BACKSTAGE_BASE_URL", "http://backstage:7007") or ""
            ).rstrip("/"),
            backstage_public_url=(
                _env("ORCHESTRATOR_BACKSTAGE_PUBLIC_URL")
                or _env("ORCHESTRATOR_BACKSTAGE_BASE_URL", "http://backstage:7007")
                or ""
            ).rstrip("/"),
            app_url_scheme="http" if _env("ORCHESTRATOR_APP_URL_SCHEME", "https") == "http" else "https",
            backstage_scope=_env("BACKSTAGE_ENTRA_SCOPE"),
            callback_audience=_env("ORCHESTRATOR_CALLBACK_AUDIENCE", "idp-orchestrator") or "",
            approver_group=_env("ORCHESTRATOR_APPROVER_GROUP", "group:default/platform-approvers") or "",
            self_approval_environments=frozenset(
                e.strip()
                for e in (_env("ORCHESTRATOR_SELF_APPROVAL_ENVIRONMENTS", "") or "").split(",")
                if e.strip() and e.strip() != "prod"
            ),
            stack_templates_dir=Path(_env("ORCHESTRATOR_STACK_TEMPLATES_DIR", "/app/stack-templates") or ""),
            infra_environment=_env("ORCHESTRATOR_INFRA_ENVIRONMENT", "dev-infra") or "dev-infra",
            worker_poll_seconds=float(_env("ORCHESTRATOR_WORKER_POLL_SECONDS", "2") or 2),
            worker_lease_seconds=int(_env("ORCHESTRATOR_WORKER_LEASE_SECONDS", "120") or 120),
            reconcile_interval_seconds=int(_env("ORCHESTRATOR_RECONCILE_SECONDS", "60") or 60),
            max_step_attempts=int(_env("ORCHESTRATOR_MAX_STEP_ATTEMPTS", "6") or 6),
            log_level=_env("LOG_LEVEL", "INFO") or "INFO",
            operations_cache_seconds=float(_env("ORCHESTRATOR_OPERATIONS_CACHE_SECONDS", "15") or 15),
            operations_links={
                kind: _env(f"ORCHESTRATOR_{kind.upper()}_URL_TEMPLATE")
                for kind in ("dashboard", "logs", "traces")
            },
        )
