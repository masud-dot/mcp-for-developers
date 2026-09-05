"""Integration: through a real client session."""

from mcpdev.servers.calculator import mcp


async def test_tools_are_listed(connect):
    async with connect(mcp) as client:
        names = [t.name for t in (await client.list_tools()).tools]
    assert {"add", "divide", "summarize"} <= set(names)


async def test_structured_content_is_returned(connect):
    async with connect(mcp) as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
    assert result.structured_content == {"result": 5.0}
    assert result.is_error is False


async def test_tool_error_is_readable(connect):
    async with connect(mcp) as client:
        result = await client.call_tool("divide", {"a": 1, "b": 0})
    assert result.is_error is True
    assert "non-zero" in result.content[0].text


async def test_schema_rejects_before_the_function_runs(connect):
    async with connect(mcp) as client:
        result = await client.call_tool(
            "summarize", {"sample": {"values": []}}
        )
    assert result.is_error is True
    assert "sample.values" in result.content[0].text
