"""Build-history server: SQLite behind explicit query handles."""

import json
import sqlite3
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass

from pydantic import BaseModel, Field

from mcp.server.mcpserver import (
    AESGCMRequestStateCodec,
    Context,
    MCPServer,
)

from mcpdev.config import settings
from mcpdev.errors import InvalidInput
from mcpdev.servers._patterns import READ_ONLY, Bounded, bounded

SORTABLE = {"started_at", "duration_s", "id"}
STATUSES = {"passed", "failed"}


@dataclass
class Store:
    """Opened once per process, shared by every request."""

    db_uri: str
    codec: AESGCMRequestStateCodec


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[Store]:
    """Prepare a read-only database URI and a handle codec."""
    if not settings.handle_key:
        raise RuntimeError("MCPDEV_HANDLE_KEY is not set.")
    yield Store(
        db_uri=f"file:{settings.ci_db_path}?mode=ro",
        codec=AESGCMRequestStateCodec(keys=[settings.handle_key]),
    )


mcp = MCPServer("ci", version="1.0.0", lifespan=lifespan)


@contextmanager
def _read(store: Store) -> Iterator[sqlite3.Connection]:
    """A short-lived read-only connection."""
    con = sqlite3.connect(store.db_uri, uri=True, timeout=5.0)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def _mint(store: Store, spec: dict) -> str:
    """Seal a query specification into an opaque handle."""
    ttl = settings.handle_ttl_seconds
    spec = spec | {"exp": int(time.time()) + ttl}
    return store.codec.seal(json.dumps(spec).encode())


def _open(store: Store, handle: str) -> dict:
    """Unseal a handle, or explain why it cannot be used."""
    try:
        spec = json.loads(store.codec.unseal(handle))
    except Exception:
        raise InvalidInput(
            "That handle is not valid. Call open_build_query "
            "again to get a fresh one."
        )
    if spec["exp"] < time.time():
        raise InvalidInput(
            "That handle has expired. Call open_build_query "
            "again to get a fresh one."
        )
    return spec


def _where(spec: dict) -> tuple[str, list]:
    """Build a parameterized WHERE clause from a handle."""
    clauses = ["started_at >= ?"]
    params: list = [int(time.time()) - spec["days"] * 86400]
    if spec.get("service"):
        clauses.append("service = ?")
        params.append(spec["service"])
    if spec.get("branch"):
        clauses.append("branch = ?")
        params.append(spec["branch"])
    if spec.get("status"):
        clauses.append("status = ?")
        params.append(spec["status"])
    return " AND ".join(clauses), params


class QueryHandle(BaseModel):
    """An opaque reference to a filtered set of builds."""

    handle: str = Field(
        description="Pass this to build_page, failure_summary, "
        "or flaky_tests. Valid for a limited time."
    )
    matched: int = Field(description="Builds matching the filter.")
    expires_in_seconds: int


class Build(BaseModel):
    """One build, without its logs."""

    id: int
    service: str
    branch: str
    status: str
    duration_s: int
    commit_sha: str


class FailureSummary(BaseModel):
    """Aggregate health of one filtered set."""

    total: int
    failed: int
    failure_rate: float = Field(description="Failed over total.")
    slowest_seconds: int


@mcp.tool(annotations=READ_ONLY)
def open_build_query(
    ctx: Context,
    service: str | None = None,
    branch: str | None = None,
    status: str | None = None,
    days: int = Field(default=14, ge=1, le=90),
    sort_by: str = "started_at",
) -> QueryHandle:
    """Describe a set of builds once and get a handle back. Pass
    the handle to the other tools instead of repeating filters.
    """
    if status is not None and status not in STATUSES:
        raise InvalidInput(
            f"status must be one of {sorted(STATUSES)}, not "
            f"{status!r}."
        )
    if sort_by not in SORTABLE:
        raise InvalidInput(
            f"sort_by must be one of {sorted(SORTABLE)}, not "
            f"{sort_by!r}."
        )
    store = ctx.request_context.lifespan_context
    spec = {
        "service": service, "branch": branch, "status": status,
        "days": days, "sort_by": sort_by,
    }
    where, params = _where(spec)
    with _read(store) as con:
        n = con.execute(
            f"SELECT COUNT(*) FROM builds WHERE {where}", params
        ).fetchone()[0]
    return QueryHandle(
        handle=_mint(store, spec),
        matched=n,
        expires_in_seconds=settings.handle_ttl_seconds,
    )


@mcp.tool(annotations=READ_ONLY)
def build_page(
    ctx: Context,
    handle: str,
    page: int = Field(default=0, ge=0),
    page_size: int = Field(default=20, ge=1, le=100),
) -> Bounded:
    """Return one page of the builds a handle describes."""
    store = ctx.request_context.lifespan_context
    spec = _open(store, handle)
    where, params = _where(spec)
    order = spec["sort_by"]
    with _read(store) as con:
        rows = con.execute(
            f"SELECT id, service, branch, status, duration_s, "
            f"commit_sha FROM builds WHERE {where} "
            f"ORDER BY {order} DESC LIMIT ? OFFSET ?",
            [*params, page_size, page * page_size],
        ).fetchall()
        total = con.execute(
            f"SELECT COUNT(*) FROM builds WHERE {where}", params
        ).fetchone()[0]
    items = [Build(**dict(r)).model_dump() for r in rows]
    result = bounded(items, page_size)
    result.total = total
    result.truncated = (page + 1) * page_size < total
    return result


@mcp.tool(annotations=READ_ONLY)
def failure_summary(ctx: Context, handle: str) -> FailureSummary:
    """Aggregate health for the builds a handle describes."""
    store = ctx.request_context.lifespan_context
    spec = _open(store, handle)
    where, params = _where(spec)
    with _read(store) as con:
        row = con.execute(
            f"SELECT COUNT(*) AS total, "
            f"SUM(status = 'failed') AS failed, "
            f"MAX(duration_s) AS slowest "
            f"FROM builds WHERE {where}",
            params,
        ).fetchone()
    total = row["total"] or 0
    failed = row["failed"] or 0
    return FailureSummary(
        total=total,
        failed=failed,
        failure_rate=round(failed / total, 3) if total else 0.0,
        slowest_seconds=row["slowest"] or 0,
    )


@mcp.tool(annotations=READ_ONLY)
def flaky_tests(
    ctx: Context,
    handle: str,
    limit: int = Field(default=10, ge=1, le=50),
) -> Bounded:
    """Tests that both passed and failed within the set a handle
    describes. These are the ones worth investigating first.
    """
    store = ctx.request_context.lifespan_context
    spec = _open(store, handle)
    where, params = _where(spec)
    with _read(store) as con:
        rows = con.execute(
            f"SELECT t.name, "
            f"SUM(t.status = 'failed') AS failures, "
            f"COUNT(*) AS runs FROM test_results t "
            f"JOIN builds b ON b.id = t.build_id "
            f"WHERE {where} GROUP BY t.name "
            f"HAVING failures > 0 AND failures < runs "
            f"ORDER BY failures DESC",
            params,
        ).fetchall()
    items = [
        {"test": r["name"], "failures": r["failures"],
         "runs": r["runs"]}
        for r in rows
    ]
    return bounded(items, limit)


if __name__ == "__main__":
    mcp.run()
