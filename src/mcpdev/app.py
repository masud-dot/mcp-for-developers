"""The served application: the ops server, plus probes."""

import contextlib
from collections.abc import AsyncIterator

import httpx2 as httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route

from mcp.server.transport_security import TransportSecuritySettings

from mcpdev.config import settings
from mcpdev.servers.ops import mcp as ops

_ready = False


def _mcp_app() -> Starlette:
    """The MCP endpoint, configured for life behind a proxy."""
    return ops.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=settings.allowed_hosts,
            allowed_origins=settings.allowed_origins,
        ),
    )


async def healthz(request: Request) -> PlainTextResponse:
    """Liveness: is this process running at all?"""
    return PlainTextResponse("ok")


async def _upstream_ok() -> bool:
    """Can we still reach the service our tools depend on?"""
    if not settings.readiness_probe_url:
        return True
    try:
        async with httpx.AsyncClient(timeout=2.0) as http:
            response = await http.get(settings.readiness_probe_url)
        return response.status_code < 500
    except httpx.HTTPError:
        return False


async def readyz(request: Request) -> JSONResponse:
    """Readiness: can this instance serve a real request now?"""
    checks = {"started": _ready, "upstream": await _upstream_ok()}
    ok = all(checks.values())
    return JSONResponse(
        {"ready": ok, "checks": checks},
        status_code=200 if ok else 503,
    )


def create_app() -> Starlette:
    """ASGI factory. Referenced as mcpdev.app:create_app."""
    inner = _mcp_app()

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Start the MCP session manager, then admit traffic."""
        global _ready
        async with inner.router.lifespan_context(app):
            _ready = True
            try:
                yield
            finally:
                _ready = False

    return Starlette(
        routes=[
            Route("/healthz", healthz),
            Route("/readyz", readyz),
            Mount("/", app=inner),
        ],
        lifespan=lifespan,
    )
