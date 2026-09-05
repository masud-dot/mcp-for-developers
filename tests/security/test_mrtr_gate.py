"""Security: the approval gate, both legs, both callers."""

import pytest

from mcp.server.auth.middleware.auth_context import (
    AuthenticatedUser,
    auth_context_var,
)
from mcp.server.auth.provider import AccessToken

import mcp_types as types


@pytest.fixture
def ops_server(monkeypatch):
    monkeypatch.setenv("MCPDEV_REQUEST_STATE_KEY", "r" * 32)
    monkeypatch.setenv("MCPDEV_AUTH_SIGNING_KEY", "s" * 32)
    import importlib

    import mcpdev.config as config
    from mcpdev.config import Settings

    config.settings = Settings()
    import mcpdev.servers.ops as ops

    importlib.reload(ops)
    return ops.mcp


def _as(subject, *scopes):
    auth_context_var.set(AuthenticatedUser(AccessToken(
        token="t", client_id="pytest", scopes=list(scopes),
        expires_at=None, resource=None, subject=subject, claims={})))


async def _accept(ctx, params):
    return types.ElicitResult(
        action="accept", content={"proceed": True, "reason": "test"})


async def test_authorized_caller_is_asked(connect, ops_server):
    _as("alice@example.com", "mcp:read", "ops:freeze")
    client = connect(ops_server)
    client.elicitation_callback = _accept
    async with client as session:
        result = await session.call_tool(
            "request_deploy_freeze", {"service": "payments-api"})
    assert "FROZEN" in result.content[0].text


async def test_unscoped_caller_is_refused_before_the_prompt(
    connect, ops_server
):
    """Chapter 20: the guard fires on the resolver, not the body."""
    _as("mallory@example.com", "mcp:read")
    asked = []

    async def watchful(ctx, params):
        asked.append(params.message)
        return await _accept(ctx, params)

    client = connect(ops_server)
    client.elicitation_callback = watchful
    async with client as session:
        result = await session.call_tool(
            "request_deploy_freeze", {"service": "payments-api"})
    assert result.is_error is True
    assert "ops:freeze" in result.content[0].text
    assert asked == [], (
        "a human was prompted for an unauthorized call"
    )
