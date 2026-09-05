"""Fixtures that make MCP testing cheap."""

import importlib
import json
import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp.client import Client
from mcp.server.auth.middleware.auth_context import (
    AuthenticatedUser,
    auth_context_var,
)
from mcp.server.auth.provider import AccessToken

GOLDEN = Path(__file__).parent / "golden"


@pytest.fixture
def as_caller():
    """Run the test as a named, scoped principal."""

    def _set(subject: str, *scopes: str) -> None:
        auth_context_var.set(
            AuthenticatedUser(
                AccessToken(
                    token="test", client_id="pytest",
                    scopes=list(scopes) or ["mcp:read"],
                    expires_at=None, resource=None,
                    subject=subject, claims={},
                )
            )
        )

    return _set


@pytest.fixture
def connect():
    """Open an in-process client against a server object."""

    def _open(server) -> Client:
        return Client(server)

    return _open


@pytest.fixture
def builds_db(tmp_path: Path) -> Iterator[str]:
    """A seeded, deterministic build database."""
    path = tmp_path / "builds.db"
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE builds (id INTEGER PRIMARY KEY, service TEXT,"
        " branch TEXT, status TEXT, started_at INTEGER,"
        " duration_s INTEGER, commit_sha TEXT);"
        "CREATE TABLE test_results (build_id INTEGER, suite TEXT,"
        " name TEXT, status TEXT, duration_ms INTEGER);"
    )
    now = int(time.time())
    for i in range(1, 21):
        status = "failed" if i % 4 == 0 else "passed"
        con.execute(
            "INSERT INTO builds VALUES (?,?,?,?,?,?,?)",
            (i, "payments-api", "main", status,
             now - i * 3600, 60 + i, f"{i:040x}"),
        )
        con.execute(
            "INSERT INTO test_results VALUES (?,?,?,?,?)",
            (i, "integration", "test_charge",
             "failed" if i % 8 == 0 else "passed", 100),
        )
    con.commit()
    con.close()
    yield str(path)


@pytest.fixture
def fake_upstream() -> Starlette:
    """A stand-in for the repository API."""

    async def repo(request):
        return JSONResponse({
            "full_name": "acme/payments-api",
            "default_branch": "main",
            "open_issues_count": 7,
            "archived": False,
        })

    async def compare(request):
        return JSONResponse({
            "total_commits": 3,
            "files": [
                {"filename": f"src/mod_{n}.py", "status": "modified",
                 "additions": n * 10, "deletions": n,
                 "changes": n * 11, "patch": "x" * 500}
                for n in range(1, 6)
            ],
        })

    return Starlette(routes=[
        Route("/repos/{owner}/{name}", repo),
        Route("/repos/{owner}/{name}/compare/{refs:path}", compare),
    ])


def assert_golden(name: str, value: object) -> None:
    """Compare against a stored snapshot, or record a new one."""
    path = GOLDEN / f"{name}.json"
    rendered = json.dumps(value, indent=2, sort_keys=False)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered)
        pytest.skip(f"recorded new golden file: {name}")
    assert rendered == path.read_text(), (
        f"{name} changed. If deliberate, delete "
        f"tests/golden/{name}.json and re-run."
    )


HOSTILE = {
    "sql": ["' OR '1'='1", "1; DROP TABLE builds--",
            "1 UNION SELECT"],
    "command": ["; rm -rf /", "$(whoami)", "`id`"],
    "ssrf": ["http://169.254.169.254/latest/meta-data/",
             "https://localhost/admin", "file:///etc/passwd"],
    "template": ["{{7*7}}", "${jndi:ldap://x/y}"],
}


@pytest.fixture
def token_factory(monkeypatch):
    """Mint real JWTs for the authorization matrix."""
    import jwt

    monkeypatch.setenv("MCPDEV_AUTH_SIGNING_KEY", "s" * 32)
    # settings is a module-level singleton built at import, so patching the
    # environment is not enough on its own.
    import mcpdev.config as config
    from mcpdev.config import Settings

    monkeypatch.setattr(config, "settings", Settings())
    import mcpdev.security.auth as auth

    monkeypatch.setattr(auth, "settings", config.settings)

    def _mint(key: str = "s" * 32, **overrides) -> str:
        claims = {
            "iss": "https://auth.example.com",
            "aud": "https://mcp.example.com",
            "sub": "alice@example.com",
            "exp": int(time.time()) + 300,
            "scope": "mcp:read ops:freeze",
            "client_id": "pytest",
        }
        claims.update(overrides)
        return jwt.encode(claims, key, algorithm="HS256")

    return _mint


@pytest.fixture
def ci_factory(builds_db, monkeypatch):
    """Build a fresh ci server: a new instance each call."""
    monkeypatch.setenv("MCPDEV_CI_DB_PATH", builds_db)
    monkeypatch.setenv("MCPDEV_HANDLE_KEY", "k" * 32)
    import mcpdev.config as config
    from mcpdev.config import Settings

    config.settings = Settings()

    def _build():
        import mcpdev.servers.ci as ci

        importlib.reload(ci)
        return ci.mcp

    return _build


