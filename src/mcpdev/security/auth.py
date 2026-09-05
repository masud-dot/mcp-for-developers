"""Token verification and per-tool scope enforcement."""

import functools
from collections.abc import Callable
from typing import Any

import jwt

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier

from mcpdev.config import settings
from mcpdev.errors import NeedsHuman


class JWTVerifier(TokenVerifier):
    """Accept only tokens this server was the audience for."""

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an AccessToken, or None to reject the request."""
        try:
            claims = jwt.decode(
                token,
                settings.auth_signing_key,
                algorithms=[settings.auth_algorithm],
                audience=settings.auth_audience,
                issuer=settings.auth_issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.InvalidTokenError:
            return None

        raw = claims.get("scope", "")
        return AccessToken(
            token=token,
            client_id=claims.get("client_id", ""),
            scopes=raw.split() if isinstance(raw, str) else list(raw),
            expires_at=claims.get("exp"),
            resource=settings.auth_audience,
            subject=claims["sub"],
            claims=claims,
        )


def principal() -> str:
    """The verified caller, for binding state to an owner."""
    token = get_access_token()
    if token is None or not token.subject:
        raise NeedsHuman(
            "This server could not identify the caller.",
            "whoever configured authentication",
        )
    return token.subject


def requires_scope(*needed: str) -> Callable:
    """Refuse a tool unless the token carries every scope."""

    def decorate(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            token = get_access_token()
            held = set(token.scopes) if token else set()
            missing = sorted(set(needed) - held)
            if missing:
                raise NeedsHuman(
                    f"This action needs the {', '.join(missing)} "
                    f"scope, which your credential does not carry.",
                    "whoever grants access to this service",
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorate
