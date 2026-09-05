"""One way to open a connection, whatever the transport."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import mcp_types as types
from mcp.client import CacheConfig, Client
from mcp.client.stdio import StdioServerParameters


@dataclass(frozen=True)
class ServerSpec:
    """How to reach one server, and what to call it."""

    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    """Overlaid on the parent environment, not a replacement."""
    url: str | None = None

    def target(self) -> StdioServerParameters | str:
        """The one argument Client needs to reach this server."""
        if self.url:
            return self.url
        if not self.command:
            raise ValueError(
                f"{self.name}: set either command or url."
            )
        return StdioServerParameters(
            command=self.command,
            args=self.args,
            env={**os.environ, **self.env},
        )


@asynccontextmanager
async def connect(
    spec: ServerSpec, *, cache_ttl_ms: int = 60_000
) -> AsyncIterator[Client]:
    """Open a client, honoring the server's own cache hints."""
    async with Client(
        spec.target(),
        client_info=types.Implementation(
            name="mcpdev", version="1.0.0"
        ),
        cache=CacheConfig(default_ttl_ms=cache_ttl_ms),
    ) as client:
        yield client


def render(result: types.CallToolResult) -> str:
    """Flatten a tool result into text a model can read."""
    if result.structured_content is not None:
        import json

        return json.dumps(result.structured_content)
    return "\n".join(_render_block(b) for b in result.content)


def _render_block(block) -> str:
    """One content block, as text."""
    match block:
        case types.TextContent():
            return block.text
        case types.EmbeddedResource():
            inner = block.resource
            body = getattr(inner, "text", "<binary>")
            return f"[{inner.uri}]\n{body}"
        case types.ResourceLink():
            return f"[link: {block.uri}]"
        case types.ImageContent() | types.AudioContent():
            return f"<{block.type}: {block.mimeType}>"
        case _:
            return f"<{getattr(block, 'type', 'unknown')}>"
