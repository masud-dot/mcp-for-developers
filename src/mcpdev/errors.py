"""Failure types shared by every server in this book.

Raising one of these preserves your message all the way to the
caller. Raising anything else does not: the SDK replaces an
unexpected exception with the text "Error executing tool <name>"
and sends the detail to the server log instead.
"""

from mcp.server.mcpserver.exceptions import ToolError


class InvalidInput(ToolError):
    """These arguments cannot succeed. Retrying unchanged will
    fail the same way.

    The message must say which argument is wrong and what a
    valid one looks like.
    """


class Retryable(ToolError):
    """Transient. The same call may succeed shortly."""

    def __init__(self, problem: str, after_seconds: int = 30) -> None:
        super().__init__(
            f"{problem} This is temporary; retry the same call "
            f"in about {after_seconds} seconds."
        )


class NeedsHuman(ToolError):
    """A person must act. No retry will help."""

    def __init__(self, problem: str, who: str) -> None:
        super().__init__(
            f"{problem} No retry will help. This needs {who}."
        )
