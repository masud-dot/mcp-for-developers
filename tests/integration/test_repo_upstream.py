"""Integration: a server against a stand-in upstream."""

import threading
import time

import pytest
import uvicorn


@pytest.fixture(scope="module")
def upstream_url(request):
    """Serve the fake upstream for the length of the module."""
    from tests.conftest import fake_upstream

    app = fake_upstream.__wrapped__()
    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=9411, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1.5)
    yield "http://127.0.0.1:9411"
    server.should_exit = True


@pytest.fixture
def repo_server(upstream_url, monkeypatch):
    """repo.py pointed at the stand-in."""
    import mcpdev.config as config
    from mcpdev.config import Settings

    monkeypatch.setenv("MCPDEV_REPO_API_BASE", upstream_url)
    config.settings = Settings()
    import importlib

    import mcpdev.servers.repo as repo

    importlib.reload(repo)
    return repo.mcp


async def test_repository_is_projected(connect, repo_server):
    async with connect(repo_server) as client:
        result = await client.call_tool(
            "repository", {"owner": "acme", "name": "payments-api"})
    assert result.structured_content == {
        "full_name": "acme/payments-api",
        "default_branch": "main",
        "open_issues": 7,
        "archived": False,
    }


async def test_change_summary_aggregates(connect, repo_server):
    async with connect(repo_server) as client:
        result = await client.call_tool("change_summary", {
            "owner": "acme", "name": "payments-api",
            "base": "v1", "head": "main"})
    assert result.structured_content["files_changed"] == 5
    assert result.structured_content["commits"] == 3


async def test_changed_files_omits_patches(connect, repo_server):
    async with connect(repo_server) as client:
        result = await client.call_tool("changed_files", {
            "owner": "acme", "name": "payments-api",
            "base": "v1", "head": "main", "limit": 2})
    payload = result.structured_content
    assert payload["returned"] == 2
    assert payload["total"] == 5
    assert payload["truncated"] is True
    assert "patch" not in payload["items"][0]
