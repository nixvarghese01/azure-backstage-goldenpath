"""Read secrets from mounted files.

Secrets reach pods as read-only files through the Secrets Store CSI driver. Environment variables
hold only the *path* to a secret file, never the value (see docs/security/secret-management.md).
"""

from __future__ import annotations

import os
from pathlib import Path


class SecretNotAvailableError(RuntimeError):
    """Raised when a required secret file is not configured or not readable."""


def read_secret_file(path_env_var: str, *, required: bool = True) -> str | None:
    """Return the contents of the file whose path is in ``path_env_var``.

    The value is stripped of surrounding whitespace. Nothing about the value is ever logged.
    """
    raw_path = os.environ.get(path_env_var, "").strip()
    if not raw_path:
        if required:
            raise SecretNotAvailableError(f"{path_env_var} is not set")
        return None
    path = Path(raw_path).expanduser()
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        if required:
            raise SecretNotAvailableError(f"cannot read secret file referenced by {path_env_var}") from exc
        return None
