"""GitHub App client (App #2, orchestrator) and an in-memory mock.

Authentication: a short-lived app JWT (RS256, private key from a mounted file) is exchanged for an
installation token, cached until shortly before expiry. Nothing about either token is logged.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import jwt
from idp_common.secrets import read_secret_file

API = "https://api.github.com"


@dataclass
class WorkflowRun:
    id: int
    name: str
    display_title: str
    status: str  # queued | in_progress | completed | waiting
    conclusion: str | None  # success | failure | cancelled | ...
    html_url: str
    head_branch: str | None = None


@dataclass
class PullRequest:
    number: int
    url: str
    state: str
    merged: bool
    mergeable_state: str | None
    head_sha: str


class GitHubClient(Protocol):
    def dispatch_workflow(self, repo: str, workflow: str, ref: str, inputs: dict[str, str]) -> None: ...

    def list_runs(self, repo: str, workflow: str, per_page: int = 30) -> list[WorkflowRun]: ...

    def commit_files_on_branch(
        self, repo: str, base: str, branch: str, files: dict[str, str], message: str
    ) -> str: ...

    def open_pull_request(self, repo: str, head: str, base: str, title: str, body: str) -> PullRequest: ...

    def get_pull_request(self, repo: str, number: int) -> PullRequest: ...

    def merge_pull_request(self, repo: str, number: int, sha: str) -> None: ...

    def review_protection_rule(
        self, callback_url: str, environment: str, approve: bool, comment: str
    ) -> None: ...


class AppGitHubClient:
    def __init__(self, org: str, app_id: str, installation_id: str) -> None:
        self.org = org
        self.app_id = app_id
        self.installation_id = installation_id
        self._token: str | None = None
        self._token_exp = 0.0

    # ---------------- auth ----------------
    def _app_jwt(self) -> str:
        key = read_secret_file("ORCHESTRATOR_GITHUB_APP_PRIVATE_KEY_FILE")
        now = int(time.time())
        return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": self.app_id}, key, algorithm="RS256")

    def _installation_token(self) -> str:
        if self._token and time.time() < self._token_exp - 300:
            return self._token
        res = httpx.post(
            f"{API}/app/installations/{self.installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {self._app_jwt()}", "Accept": "application/vnd.github+json"},
            timeout=10.0,
        )
        res.raise_for_status()
        self._token = res.json()["token"]
        self._token_exp = time.time() + 3600
        return self._token

    def _req(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._installation_token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        res = httpx.request(
            method, url if url.startswith("http") else f"{API}{url}", headers=headers, timeout=15.0, **kwargs
        )
        res.raise_for_status()
        return res

    # ---------------- workflows ----------------
    def dispatch_workflow(self, repo: str, workflow: str, ref: str, inputs: dict[str, str]) -> None:
        self._req(
            "POST",
            f"/repos/{self.org}/{repo}/actions/workflows/{workflow}/dispatches",
            json={"ref": ref, "inputs": inputs},
        )

    def list_runs(self, repo: str, workflow: str, per_page: int = 30) -> list[WorkflowRun]:
        data = self._req(
            "GET",
            f"/repos/{self.org}/{repo}/actions/workflows/{workflow}/runs",
            params={"per_page": per_page},
        ).json()
        return [
            WorkflowRun(
                id=r["id"],
                name=r.get("name", ""),
                display_title=r.get("display_title", ""),
                status=r["status"],
                conclusion=r.get("conclusion"),
                html_url=r["html_url"],
                head_branch=r.get("head_branch"),
            )
            for r in data.get("workflow_runs", [])
        ]

    # ---------------- git data: one commit with many files ----------------
    def commit_files_on_branch(
        self, repo: str, base: str, branch: str, files: dict[str, str], message: str
    ) -> str:
        r = f"/repos/{self.org}/{repo}"
        base_sha = self._req("GET", f"{r}/git/ref/heads/{base}").json()["object"]["sha"]
        base_tree = self._req("GET", f"{r}/git/commits/{base_sha}").json()["tree"]["sha"]
        tree = []
        for path, content in sorted(files.items()):
            blob = self._req(
                "POST",
                f"{r}/git/blobs",
                json={"content": base64.b64encode(content.encode()).decode(), "encoding": "base64"},
            ).json()
            mode = "100755" if path.endswith(".sh") else "100644"
            tree.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
        new_tree = self._req("POST", f"{r}/git/trees", json={"base_tree": base_tree, "tree": tree}).json()
        commit = self._req(
            "POST",
            f"{r}/git/commits",
            json={"message": message, "tree": new_tree["sha"], "parents": [base_sha]},
        ).json()
        try:
            self._req("POST", f"{r}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 422:  # branch exists: retry after a crash -> move it
                raise
            self._req("PATCH", f"{r}/git/refs/heads/{branch}", json={"sha": commit["sha"], "force": True})
        return str(commit["sha"])

    # ---------------- pull requests ----------------
    def _pr(self, d: dict[str, Any]) -> PullRequest:
        return PullRequest(
            number=d["number"],
            url=d["html_url"],
            state=d["state"],
            merged=bool(d.get("merged")),
            mergeable_state=d.get("mergeable_state"),
            head_sha=d["head"]["sha"],
        )

    def open_pull_request(self, repo: str, head: str, base: str, title: str, body: str) -> PullRequest:
        existing = self._req(
            "GET", f"/repos/{self.org}/{repo}/pulls", params={"head": f"{self.org}:{head}", "state": "open"}
        ).json()
        if existing:
            return self._pr(existing[0])
        return self._pr(
            self._req(
                "POST",
                f"/repos/{self.org}/{repo}/pulls",
                json={"head": head, "base": base, "title": title, "body": body},
            ).json()
        )

    def get_pull_request(self, repo: str, number: int) -> PullRequest:
        return self._pr(self._req("GET", f"/repos/{self.org}/{repo}/pulls/{number}").json())

    def merge_pull_request(self, repo: str, number: int, sha: str) -> None:
        self._req(
            "PUT",
            f"/repos/{self.org}/{repo}/pulls/{number}/merge",
            json={"merge_method": "squash", "sha": sha},
        )

    # ---------------- custom deployment protection rule ----------------
    def review_protection_rule(
        self, callback_url: str, environment: str, approve: bool, comment: str
    ) -> None:
        self._req(
            "POST",
            callback_url,
            json={
                "environment_name": environment,
                "state": "approved" if approve else "rejected",
                "comment": comment[:1000],
            },
        )


@dataclass
class MockGitHubClient:
    """Records calls; used for local development (polling + simulated runs) and tests."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    runs: dict[tuple[str, str], list[WorkflowRun]] = field(default_factory=dict)
    prs: dict[tuple[str, int], PullRequest] = field(default_factory=dict)
    _next_pr: int = 1

    def dispatch_workflow(self, repo: str, workflow: str, ref: str, inputs: dict[str, str]) -> None:
        self.calls.append(("dispatch", {"repo": repo, "workflow": workflow, "ref": ref, "inputs": inputs}))

    def list_runs(self, repo: str, workflow: str, per_page: int = 30) -> list[WorkflowRun]:
        return list(self.runs.get((repo, workflow), []))

    def commit_files_on_branch(
        self, repo: str, base: str, branch: str, files: dict[str, str], message: str
    ) -> str:
        self.calls.append(("commit", {"repo": repo, "branch": branch, "files": sorted(files)}))
        return f"sha-{branch}"

    def open_pull_request(self, repo: str, head: str, base: str, title: str, body: str) -> PullRequest:
        for (r, _), pr in self.prs.items():
            if r == repo and pr.head_sha == f"sha-{head}" and pr.state == "open":
                return pr
        pr = PullRequest(
            number=self._next_pr,
            url=f"https://github.com/mock/{repo}/pull/{self._next_pr}",
            state="open",
            merged=False,
            mergeable_state="clean",
            head_sha=f"sha-{head}",
        )
        self.prs[(repo, pr.number)] = pr
        self._next_pr += 1
        self.calls.append(("open_pr", {"repo": repo, "head": head, "title": title}))
        return pr

    def get_pull_request(self, repo: str, number: int) -> PullRequest:
        return self.prs[(repo, number)]

    def merge_pull_request(self, repo: str, number: int, sha: str) -> None:
        pr = self.prs[(repo, number)]
        pr.merged, pr.state = True, "closed"
        self.calls.append(("merge", {"repo": repo, "number": number}))

    def review_protection_rule(
        self, callback_url: str, environment: str, approve: bool, comment: str
    ) -> None:
        self.calls.append(("review", {"callback_url": callback_url, "approve": approve}))
