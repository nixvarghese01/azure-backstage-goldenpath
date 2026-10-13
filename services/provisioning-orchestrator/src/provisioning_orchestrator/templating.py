"""Render the chosen stack's application files for the application pull request.

Stack templates use ``[[ ... ]]`` / ``[% ... %]`` delimiters so they never collide with GitHub Actions
``${{ ... }}`` expressions or Helm ``{{ ... }}`` templates inside the files being generated.
Only values from the validated request and non-sensitive infrastructure outputs are available.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_SUFFIX = ".j2"


def render_stack(templates_dir: Path, stack: str, values: dict[str, Any]) -> dict[str, str]:
    root = templates_dir / stack
    if not root.is_dir():
        raise FileNotFoundError(f"stack template '{stack}' not found")
    files: dict[str, str] = {}
    shared = templates_dir / "_shared"
    if shared.is_dir():
        files.update(_render_directory(shared, values))
    files.update(_render_directory(root, values))
    return files


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
