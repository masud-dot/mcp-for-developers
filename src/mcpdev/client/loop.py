"""The smallest loop that proves the protocol works."""

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import mcp_types as types
from mcp.client import Client

from mcpdev.client.session import render


@dataclass
class ToolCall:
    """One tool the model chose, in provider-neutral form."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ModelTurn:
    """What a model returned: text, tool calls, or both."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class ModelAdapter(Protocol):
    """The only thing this book needs from a model provider."""

    async def respond(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        """Send the conversation and the catalog; get a turn."""
        ...


def to_provider_tools(tools: list[types.Tool]) -> list[dict]:
    """MCP tool definitions to a provider's tool format."""
    return [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.input_schema,
        }
        for t in tools
    ]


def select(
    tools: list[types.Tool], keep: set[str] | None = None
) -> list[types.Tool]:
    """Narrow a catalog before it costs context on every turn."""
    if keep is None:
        return tools
    return [t for t in tools if t.name in keep]


async def run(
    adapter: ModelAdapter,
    client: Client,
    question: str,
    *,
    keep: set[str] | None = None,
    max_steps: int = 6,
) -> str:
    """Discover, present, select, invoke, return. Repeat."""
    catalog = select((await client.list_tools()).tools, keep)
    tools = to_provider_tools(catalog)
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": question}
    ]

    for _ in range(max_steps):
        turn = await adapter.respond(messages, tools)
        if not turn.tool_calls:
            return turn.text

        messages.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": c.id,
                        "name": c.name,
                        "input": c.arguments,
                    }
                    for c in turn.tool_calls
                ],
            }
        )
        results = []
        for call in turn.tool_calls:
            result = await client.call_tool(call.name, call.arguments)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": render(result),
                    "is_error": bool(result.is_error),
                }
            )
        messages.append({"role": "user", "content": results})

    return (
        f"Stopped after {max_steps} steps without a final answer."
    )
