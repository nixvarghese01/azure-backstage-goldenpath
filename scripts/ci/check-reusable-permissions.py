"""Check that generated workflows grant what the platform's reusable workflows ask for.

Also: every reusable job that requests an OIDC token runs in an environment. The generated repositories'
subject template includes the environment claim, and GitHub refuses a token without it ("the claim
'environment' cannot be null or empty").

GitHub validates every job of a called workflow against the calling job's permissions, including jobs
that won't run, and fails the run at startup ("The nested job 'apply' is requesting 'actions: read', but
is only allowed 'actions: none'"). Neither actionlint nor a render catches it, so this does.

Usage: python scripts/ci/check-reusable-permissions.py <generated repo dir> [<platform repo dir>]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

LEVEL = {"none": 0, "read": 1, "write": 2}
USES = re.compile(r"azure-backstage-goldenpath/\.github/workflows/([\w.-]+\.ya?ml)@")


def granted(job: dict, workflow: dict) -> dict[str, str]:
    perms = job.get("permissions", workflow.get("permissions", {}))
    if perms in ("read-all", "write-all"):
        return {"*": perms.split("-")[0]}
    return dict(perms or {})


def main() -> int:
    generated = Path(sys.argv[1])
    platform = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[2]
    problems = []
    callers = sorted(generated.glob(".github/workflows/*.y*ml"))
    for caller in callers:
        wf = yaml.safe_load(caller.read_text(encoding="utf-8"))
        for name, job in (wf.get("jobs") or {}).items():
            m = USES.search(str(job.get("uses", "")))
            if not m:
                continue
            called = yaml.safe_load((platform / ".github/workflows" / m.group(1)).read_text(encoding="utf-8"))
            have = granted(job, wf)
            for nested_name, nested in (called.get("jobs") or {}).items():
                # Generated repos' OIDC subject includes the environment: a token request without one fails.
                if (nested.get("permissions") or {}).get("id-token") == "write" and not nested.get(
                    "environment"
                ):
                    problems.append(
                        f"{m.group(1)} job '{nested_name}' requests id-token without an environment "
                        "(the OIDC subject needs the environment claim)"
                    )
                for scope, level in (nested.get("permissions") or {}).items():
                    got = have.get(scope, have.get("*", "none"))
                    if LEVEL[got] < LEVEL[level]:
                        problems.append(
                            f"{caller.name} job '{name}' -> {m.group(1)} job '{nested_name}' needs "
                            f"{scope}: {level}, caller grants {scope}: {got}"
                        )
    problems = list(dict.fromkeys(problems))  # one report per problem, not per caller
    for p in problems:
        print(f"::error::{p}")
    print(f"checked {len(callers)} generated workflows: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
