"""Two MCP servers under one ASGI application."""

import contextlib
from collections.abc import AsyncIterator

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcpdev.servers.calculator import mcp as calculator
from mcpdev.servers.notes import mcp as notes

calc_app = calculator.streamable_http_app(
    stateless_http=True, json_response=True)
notes_app = notes.streamable_http_app(
    stateless_http=True, json_response=True)


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    """Run both mounted apps' lifespans, not just the parent's."""
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(
            calc_app.router.lifespan_context(app))
        await stack.enter_async_context(
            notes_app.router.lifespan_context(app))
        yield


async def health(request: Request) -> JSONResponse:
    """Liveness probe. Chapter 18 makes this mean something."""
    return JSONResponse({"status": "ok"})


app = Starlette(
    routes=[
        Route("/healthz", health),
        Mount("/calculator", app=calc_app),
        Mount("/notes", app=notes_app),
    ],
    lifespan=lifespan,
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
