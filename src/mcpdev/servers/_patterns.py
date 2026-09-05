"""Tool-design patterns reused by every server in this book."""

from typing import Any

from pydantic import BaseModel, Field

import mcp_types as types

READ_ONLY = types.ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
)
"""For tools that only look. Safe to retry, safe to auto-approve."""

DESTRUCTIVE = types.ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=False,
)
"""For tools that change something a person would want to confirm."""


class Bounded(BaseModel):
    """A list result that admits when it left something out."""

    items: list[Any] = Field(description="The returned items.")
    returned: int = Field(description="How many items are here.")
    total: int = Field(description="How many matched before limiting.")
    truncated: bool = Field(
        description="True when items were omitted. Narrow the "
        "query rather than paging blindly."
    )


def bounded(items: list[Any], limit: int = 20) -> Bounded:
    """Cap a list and record what was dropped."""
    total = len(items)
    kept = items[:limit]
    return Bounded(
        items=kept,
        returned=len(kept),
        total=total,
        truncated=total > len(kept),
    )
