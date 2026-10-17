"""Render the chosen stack's application files for the application pull request.

Stack templates use ``[[ ... ]]`` / ``[% ... %]`` delimiters so they never collide with GitHub Actions
``${{ ... }}`` expressions or Helm ``{{ ... }}`` templates inside the files being generated.
Only values from the validated request and non-sensitive infrastructure outputs are available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_SUFFIX = ".j2"


@dataclass(frozen=True)
class RuntimeProfile:
    """Minimum per-pod resources for one stack: a single replica on the standard tier.

    Memory request equals the limit, so the scheduler reserves what the pod may use and the pod is
    never evicted for node memory pressure. CPU requests stay small; limits leave headroom for startup.
    The same numbers size the local Compose service, so local runs match the cluster.
    """

    cpu_request_m: int
    cpu_limit_m: int
    memory_mi: int
    startup_seconds: int
    env: dict[str, str] = field(default_factory=dict)

    def as_values(self) -> dict[str, Any]:
        return {
            "cpu_request": f"{self.cpu_request_m}m",
            "cpu_limit": f"{self.cpu_limit_m}m",
            "cpu_cores": f"{self.cpu_limit_m / 1000:g}",
            "memory": f"{self.memory_mi}Mi",
            "memory_compose": f"{self.memory_mi}m",
            # Startup probe polls every 2 s; the pod gets this long before liveness applies.
            "startup_failure_threshold": self.startup_seconds // 2,
            "env": dict(self.env),
        }


_NODE = RuntimeProfile(50, 500, 384, 30, {"NODE_OPTIONS": "--max-old-space-size=256"})
_STATIC = RuntimeProfile(10, 100, 64, 30)  # nginx serving a built single-page app

RUNTIME_PROFILES: dict[str, RuntimeProfile] = {
    "nestjs": _NODE,
    "nextjs": _NODE,
    "fastapi": RuntimeProfile(50, 500, 256, 30),
    "go": RuntimeProfile(25, 250, 128, 30, {"GOMEMLIMIT": "100MiB"}),
    "dotnet": RuntimeProfile(50, 1000, 384, 60, {"DOTNET_gcServer": "0"}),
    "springboot": RuntimeProfile(100, 1000, 512, 60, {"JAVA_TOOL_OPTIONS": "-XX:MaxRAMPercentage=65"}),
    "react": _STATIC,
    "vue": _STATIC,
}


def runtime_profile(stack: str) -> RuntimeProfile:
    try:
        return RUNTIME_PROFILES[stack]
    except KeyError:
        raise ValueError(f"no runtime profile for stack '{stack}'") from None


def render_stack(templates_dir: Path, stack: str, values: dict[str, Any]) -> dict[str, str]:
    root = templates_dir / stack
    if not root.is_dir():
        raise FileNotFoundError(f"stack template '{stack}' not found")
    values = {**values, "profile": runtime_profile(values.get("stack") or "nestjs").as_values()}
    files: dict[str, str] = {}
    shared = templates_dir / "_shared"
    if shared.is_dir():
        files.update(_render_directory(shared, values))
    files.update(_render_directory(root, values))
    return files


# Files that need the provisioned infrastructure (its outputs) or would run CI/CD before it exists:
# the application pull request adds them after apply.
AFTER_APPLY = (".github/workflows/", "deploy/helm/application/values-")


def render_starter(templates_dir: Path, stack: str, values: dict[str, Any]) -> dict[str, str]:
    """The starter application for the repository's first commit: source, tests, Dockerfile, Compose
    and README, without the CI/CD workflows and Helm values that come with the application PR."""
    values = {"outputs": {}, "resolved": {}, "runtime_capability": {"type": "none"}, **values}
    files = render_stack(templates_dir, stack, values)
    return {path: content for path, content in files.items() if not path.startswith(AFTER_APPLY)}


def _render_directory(root: Path, values: dict[str, Any]) -> dict[str, str]:
    env = Environment(  # noqa: S701 - output is source code, not HTML
        loader=FileSystemLoader(str(root)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        variable_start_string="[[",
        variable_end_string="]]",
        block_start_string="[%",
        block_end_string="%]",
        comment_start_string="[#",
        comment_end_string="#]",
    )
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        # Local .NET builds leave binary caches alongside starter source files.
        if any(part in {"bin", "obj"} for part in path.relative_to(root).parts[:-1]):
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.endswith(_SUFFIX):
            files[rel[: -len(_SUFFIX)]] = env.get_template(rel).render(values=values)
        else:
            files[rel] = path.read_text(encoding="utf-8")
    return files
