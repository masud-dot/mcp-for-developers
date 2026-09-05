"""Several servers behind one application."""

import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Literal

import mcp_types as types
from mcp.client import Client

from mcpdev.client.session import ServerSpec, connect

State = Literal["up", "down", "tripped"]


@dataclass
class Health:
    """What we currently believe about one server."""

    name: str
    state: State = "up"
    failures: int = 0
    tripped_until: float = 0.0
    last_error: str = ""


@dataclass
class Registry:
    """Connections, health, and one namespaced tool catalog."""

    threshold: int = 3
    cooldown_s: float = 30.0
    clients: dict[str, Client] = field(default_factory=dict)
    health: dict[str, Health] = field(default_factory=dict)
    _stack: AsyncExitStack = field(default_factory=AsyncExitStack)

    async def __aenter__(self) -> "Registry":
        await self._stack.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._stack.__aexit__(*exc)

    async def add(self, spec: ServerSpec) -> bool:
        """Connect one server. A failure here is not fatal."""
        self.health.setdefault(spec.name, Health(name=spec.name))
        try:
            client = await self._stack.enter_async_context(
                connect(spec)
            )
        except Exception as exc:
            self._record_failure(spec.name, exc)
            return False
        self.clients[spec.name] = client
        self.health[spec.name] = Health(name=spec.name)
        return True

    def available(self) -> list[str]:
        """Servers we would send a call to right now."""
        now = time.monotonic()
        out = []
        for name, client in self.clients.items():
            h = self.health[name]
            if h.state == "tripped" and now >= h.tripped_until:
                h.state, h.failures = "up", 0
            if h.state == "up":
                out.append(name)
        return out

    async def catalog(
        self, keep: set[str] | None = None
    ) -> list[tuple[str, types.Tool]]:
        """Every tool from every reachable server, qualified."""
        out: list[tuple[str, types.Tool]] = []
        for name in self.available():
            try:
                listed = await self.clients[name].list_tools()
            except Exception as exc:
                self._record_failure(name, exc)
                continue
            for tool in listed.tools:
                qualified = f"{name}.{tool.name}"
                if keep is None or qualified in keep:
                    out.append((qualified, tool))
        return out

    async def call(
        self, qualified: str, arguments: dict[str, Any]
    ) -> types.CallToolResult:
        """Route one call by its qualified name."""
        server, _, tool = qualified.partition(".")
        if server not in self.health:
            return _refuse(f"No server named {server!r}.")
        if server not in self.available():
            h = self.health[server]
            return _refuse(
                f"{server} is unavailable ({h.last_error}). "
                f"Answer without it or try again later."
            )
        try:
            result = await self.clients[server].call_tool(
                tool, arguments
            )
        except Exception as exc:
            self._record_failure(server, exc)
            return _refuse(
                f"{server} failed while handling {tool!r}. "
                f"Answer without it or try again later."
            )
        self.health[server].failures = 0
        return result

    def _record_failure(self, name: str, exc: Exception) -> None:
        """Count it, and trip the breaker if it keeps happening."""
        h = self.health.setdefault(name, Health(name=name))
        h.failures += 1
        h.last_error = _name(exc)
        if h.failures >= self.threshold or name not in self.clients:
            h.state = "tripped"
            h.tripped_until = time.monotonic() + self.cooldown_s
        else:
            h.state = "up"


def _name(exc: BaseException) -> str:
    """The useful name inside a possibly grouped exception."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return type(exc).__name__


def _refuse(message: str) -> types.CallToolResult:
    """A tool result saying this server could not answer."""
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)],
        is_error=True,
    )
