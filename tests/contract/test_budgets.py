"""Contract: budgets a caller pays for on every turn."""

import json

from mcpdev.client.loop import to_provider_tools
from mcpdev.servers.calculator import mcp

CATALOG_CHAR_BUDGET = 2_500
RESULT_CHAR_BUDGET = 400


async def test_catalog_stays_within_budget(connect):
    """Chapter 13: the catalog costs tokens on every turn."""
    async with connect(mcp) as client:
        tools = (await client.list_tools()).tools
    size = len(json.dumps(to_provider_tools(tools)))
    assert size <= CATALOG_CHAR_BUDGET, (
        f"catalog grew to {size} chars, "
        f"budget {CATALOG_CHAR_BUDGET}. "
        f"Trim a description or raise the budget deliberately."
    )


async def test_results_stay_small(connect):
    """Chapter 10: shaping is a budget and a security control."""
    async with connect(mcp) as client:
        result = await client.call_tool(
            "summarize",
            {"sample": {"values": list(range(200))}},
        )
    size = len(json.dumps(result.structured_content))
    assert size <= RESULT_CHAR_BUDGET, (
        f"result grew to {size} chars for a 200-item input"
    )
