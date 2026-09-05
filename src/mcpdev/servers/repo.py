"""Repository server: a shaping layer over a repository API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx2 as httpx
from pydantic import BaseModel, Field

from mcp.server.mcpserver import Context, MCPServer

from mcpdev.config import settings
from mcpdev.errors import InvalidInput, NeedsHuman, Retryable
from mcpdev.servers._patterns import READ_ONLY, Bounded, bounded


@dataclass
class Upstream:
    """Built once per process, shared by every request."""

    http: httpx.AsyncClient


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[Upstream]:
    """Open one HTTP client for the life of the server."""
    headers = {"accept": "application/vnd.github+json"}
    if settings.repo_token:
        headers["authorization"] = f"Bearer {settings.repo_token}"
    async with httpx.AsyncClient(
        base_url=settings.repo_api_base,
        headers=headers,
        timeout=httpx.Timeout(settings.repo_timeout_seconds),
        limits=httpx.Limits(max_connections=10),
    ) as http:
        yield Upstream(http=http)


mcp = MCPServer("repo", version="1.0.0", lifespan=lifespan)


async def _get(ctx: Context, path: str) -> dict:
    """Fetch upstream, or raise a failure the caller can act on."""
    http = ctx.request_context.lifespan_context.http
    try:
        response = await http.get(path)
    except httpx.TimeoutException:
        raise Retryable("The repository service did not respond.")
    except httpx.TransportError:
        raise Retryable("Could not reach the repository service.")

    code = response.status_code
    if code == 404:
        raise InvalidInput(
            "No such repository or ref. Check the owner, name, "
            "and both branch names."
        )
    if code in (401, 403):
        raise NeedsHuman(
            "The repository credential was rejected.",
            "whoever manages MCPDEV_REPO_TOKEN",
        )
    if code == 429:
        raise Retryable(
            "Rate limited by the repository service.",
            after_seconds=60,
        )
    if code >= 500:
        raise Retryable("The repository service returned an error.")
    return response.json()


class Repository(BaseModel):
    """The few repository facts a release decision needs."""

    full_name: str = Field(description="owner/name.")
    default_branch: str = Field(
        description="Branch releases cut from."
    )
    open_issues: int = Field(
        description="Open issues and pull requests."
    )
    archived: bool = Field(description="True if the repo is frozen.")


class ChangeSummary(BaseModel):
    """Aggregate shape of a diff, with no file list."""

    commits: int = Field(description="Commits in the range.")
    files_changed: int = Field(description="Distinct files touched.")
    additions: int = Field(description="Lines added across the range.")
    deletions: int = Field(description="Lines removed across the range.")


class ChangedFile(BaseModel):
    """One file in a diff, without its patch."""

    path: str
    status: str = Field(description="added, modified, or removed.")
    additions: int
    deletions: int


@mcp.tool(annotations=READ_ONLY)
async def repository(owner: str, name: str, ctx: Context) -> Repository:
    """Return the handful of repository facts a release check
    needs. Call this before comparing refs.
    """
    d = await _get(ctx, f"/repos/{owner}/{name}")
    return Repository(
        full_name=d["full_name"],
        default_branch=d["default_branch"],
        open_issues=d["open_issues_count"],
        archived=d["archived"],
    )


@mcp.tool(annotations=READ_ONLY)
async def change_summary(
    owner: str, name: str, base: str, head: str, ctx: Context
) -> ChangeSummary:
    """Size up a release without listing files. Use this first;
    call changed_files only if the size warrants a closer look.
    """
    path = f"/repos/{owner}/{name}/compare/{base}...{head}"
    d = await _get(ctx, path)
    files = d.get("files", [])
    return ChangeSummary(
        commits=d.get("total_commits", 0),
        files_changed=len(files),
        additions=sum(f.get("additions", 0) for f in files),
        deletions=sum(f.get("deletions", 0) for f in files),
    )


@mcp.tool(annotations=READ_ONLY)
async def changed_files(
    owner: str,
    name: str,
    base: str,
    head: str,
    ctx: Context,
    limit: int = Field(default=20, ge=1, le=100),
) -> Bounded:
    """List files changed between two refs, largest change
    first. Patches are omitted; ask for one file if you need it.
    """
    path = f"/repos/{owner}/{name}/compare/{base}...{head}"
    d = await _get(ctx, path)
    files = sorted(
        d.get("files", []),
        key=lambda f: f.get("changes", 0),
        reverse=True,
    )
    shaped = [
        ChangedFile(
            path=f["filename"],
            status=f["status"],
            additions=f.get("additions", 0),
            deletions=f.get("deletions", 0),
        ).model_dump()
        for f in files
    ]
    return bounded(shaped, limit)


if __name__ == "__main__":
    mcp.run()
