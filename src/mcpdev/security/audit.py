"""Structured audit events for every inbound request."""

import json
import logging
import sys
import time
import uuid
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.context import CallNext, ServerMiddleware, ServerRequestContext

from mcpdev.security.guards import redact

log = logging.getLogger("mcpdev.audit")

NAMED = {"tools/call", "prompts/get"}
MAX_ARG_CHARS = 400


def configure(stream: Any = sys.stderr) -> None:
    """One JSON object per line, on stderr. Never stdout."""
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.handlers = [handler]
    log.setLevel(logging.INFO)
    log.propagate = False


class AuditMiddleware(ServerMiddleware[Any]):
    """Record who did what, when, and with which arguments."""

    def __init__(self, server: str, instance: str) -> None:
        self.server = server
        self.instance = instance

    async def __call__(
        self, ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> Any:
        started = time.perf_counter()
        event = self._describe(ctx)
        try:
            result = await call_next(ctx)
        except Exception as exc:
            event["outcome"] = "error"
            event["error"] = type(exc).__name__
            self._emit(event, started)
            raise
        event["outcome"] = self._outcome(result)
        self._emit(event, started)
        return result

    def _describe(
        self, ctx: ServerRequestContext[Any, Any]
    ) -> dict[str, Any]:
        """The fields an incident responder will ask for."""
        params = ctx.params or {}
        token = get_access_token()
        arguments = params.get("arguments")
        rendered = (
            redact(json.dumps(arguments, default=str))
            if arguments is not None
            else None
        )
        return {
            "event_id": str(uuid.uuid4()),
            "ts": time.time(),
            "server": self.server,
            "instance": self.instance,
            "request_id": str(ctx.request_id),
            "method": ctx.method,
            "target": params.get("name") or params.get("uri"),
            "principal": token.subject if token else None,
            "client_id": token.client_id if token else None,
            "scopes": sorted(token.scopes) if token else [],
            "arg_chars": len(rendered) if rendered else 0,
            "arguments": (
                rendered[:MAX_ARG_CHARS] if rendered else None
            ),
        }

    @staticmethod
    def _outcome(result: Any) -> str:
        """Middleware sees the wire form: camelCase keys."""
        if not isinstance(result, dict):
            return "ok"
        if result.get("resultType") == "input_required":
            return "input_required"
        if result.get("isError"):
            return "refused"
        return result.get("resultType") or "ok"

    def _emit(self, event: dict[str, Any], started: float) -> None:
        event["ms"] = round((time.perf_counter() - started) * 1000, 2)
        log.info(json.dumps(event, sort_keys=True))
