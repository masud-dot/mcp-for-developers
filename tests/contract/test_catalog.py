"""Contract: the shape a caller depends on."""

from tests.conftest import assert_golden

from mcpdev.servers.calculator import mcp


async def test_catalog_matches_golden_file(connect):
    async with connect(mcp) as client:
        tools = (await client.list_tools()).tools
    assert_golden("calculator_catalog", [
        {
            "name": t.name,
            "description": t.description,
            "inputSchema": t.input_schema,
            "outputSchema": t.output_schema,
        }
        for t in tools
    ])


async def test_tool_order_is_deterministic(connect):
    async with connect(mcp) as client:
        first = [t.name for t in (await client.list_tools()).tools]
        second = [t.name for t in (await client.list_tools()).tools]
    assert first == second
