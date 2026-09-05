"""Negative: the paths nobody exercises by hand."""

import pytest

from mcpdev.servers.calculator import mcp


async def test_unknown_tool_is_a_tool_error(connect):
    """Measured: tools/call returns a result, not a protocol error."""
    async with connect(mcp) as client:
        result = await client.call_tool("no_such_tool", {})
    assert result.is_error is True
    assert "Unknown tool" in result.content[0].text


async def test_unknown_prompt_is_a_protocol_error(connect):
    """Prompts differ from tools here."""
    async with connect(mcp) as client:
        with pytest.raises(Exception):
            await client.get_prompt("no_such_prompt", {})


async def test_missing_required_argument_is_rejected(connect):
    async with connect(mcp) as client:
        result = await client.call_tool("add", {"a": 1})
    assert result.is_error is True


async def test_wrong_type_is_rejected_before_the_function(connect):
    async with connect(mcp) as client:
        result = await client.call_tool(
            "add", {"a": "not-a-number", "b": 2})
    assert result.is_error is True
    assert "validation error" in result.content[0].text


async def test_error_text_names_the_argument(connect):
    """Chapter 9: a caller must be able to act on the message."""
    async with connect(mcp) as client:
        result = await client.call_tool("divide", {"a": 1, "b": 0})
    assert "b" in result.content[0].text
    assert "non-zero" in result.content[0].text
