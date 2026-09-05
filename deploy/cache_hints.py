"""Cache hints, by data volatility.  Chapter 17.

Only the six methods in CacheableMethod accept a hint; anything else
raises ValueError at construction.

    from deploy.cache_hints import HINTS
    mcp = MCPServer("repo", version="1.0.0", cache_hints=HINTS)
"""

from mcp.server import CacheHint

HINTS = {
    # Identical for every caller, changes on deploy.
    "tools/list": CacheHint(ttl_ms=3_600_000, scope="public"),
    "server/discover": CacheHint(ttl_ms=3_600_000, scope="public"),
    # Per-caller data: private regardless of how long it lives.
    "resources/read": CacheHint(ttl_ms=60_000, scope="private"),
}
