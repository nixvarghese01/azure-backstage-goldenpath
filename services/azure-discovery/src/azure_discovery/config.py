from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    azure_mode: str  # "sdk" (real Azure) or "mock" (local development / tests)
    policy_file: Path
    cache_ttl_seconds: int
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        mode = os.environ.get("DISCOVERY_AZURE_MODE", "sdk").lower()
        if mode not in {"sdk", "mock"}:
            raise ValueError("DISCOVERY_AZURE_MODE must be 'sdk' or 'mock'")
        return cls(
            azure_mode=mode,
            policy_file=Path(os.environ.get("DISCOVERY_POLICY_FILE", "/etc/sportify/allowlist.yaml")),
            cache_ttl_seconds=int(os.environ.get("DISCOVERY_CACHE_TTL_SECONDS", "60")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
