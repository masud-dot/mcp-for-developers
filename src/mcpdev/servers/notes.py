"""A notes server: resources and templates."""

import mcp_types as types

from mcp.server.auth.settings import AuthSettings

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError

from mcpdev.config import settings
from mcpdev.security.auth import JWTVerifier, principal

mcp = MCPServer(
    "notes",
    version="1.0.0",
    token_verifier=JWTVerifier(),
    auth=AuthSettings(
        issuer_url=settings.auth_issuer,
        resource_server_url=settings.auth_audience,
        required_scopes=["mcp:read"],
    ),
)

NOTES: dict[str, tuple[str, str]] = {
    "standup": ("alice@example.com",
                "Blocked on the migration. Ask platform."),
    "release": ("alice@example.com",
                "Cut 2.4.0 Friday; freeze Thursday at 17:00."),
    "salaries": ("bob@example.com", "Confidential."),
}


def _readable(name: str) -> str:
    """Return a note, or refuse as if it did not exist."""
    who = principal()
    entry = NOTES.get(name)
    if entry is None or entry[0] != who:
        raise ResourceNotFoundError(
            f"No note named {name!r}. Read notes://index for "
            f"the available names."
        )
    return entry[1]


@mcp.resource(
    "notes://index",
    description="Every note name available on this server, "
    "one per line. Read this before reading a note.",
    mime_type="text/plain",
)
def index() -> str:
    """List note names this caller may read."""
    who = principal()
    return "\n".join(
        sorted(n for n, (owner, _) in NOTES.items() if owner == who)
    )


@mcp.resource(
    "notes://{name}",
    description="The full text of one note. Names come from "
    "notes://index.",
    mime_type="text/plain",
)
def note(name: str) -> str:
    """Return one note's text."""
    return _readable(name)


@mcp.prompt(
    title="Review a note",
    description="Draft review comments for one note.",
)
def review_note(name: str) -> list[dict]:
    """Ask for a structured review of one note."""
    body = _readable(name)
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    "Review the note below. Reply with exactly "
                    "three sections: Risks, Missing detail, and "
                    "Suggested next action. Be specific and do "
                    "not repeat the note back."
                ),
            },
        },
        {
            "role": "user",
            "content": {"type": "text", "text": body},
        },
    ]


@mcp.prompt(
    title="Compare two notes",
    description="Contrast two notes and report what differs.",
)
def compare_notes(first: str, second: str) -> str:
    """Compare two notes."""
    return (
        f"Compare these two notes and list only what differs.\n\n"
        f"--- {first} ---\n{_readable(first)}\n\n"
        f"--- {second} ---\n{_readable(second)}"
    )


@mcp.completion()
async def complete(ref, argument, context):
    """Suggest note names for prompts and the note template."""
    names = sorted(NOTES)
    if isinstance(ref, types.ResourceTemplateReference):
        if str(ref.uri) != "notes://{name}":
            return None
    elif isinstance(ref, types.PromptReference):
        if ref.name not in ("review_note", "compare_notes"):
            return None
        if argument.name == "second" and context:
            already = (context.arguments or {}).get("first")
            names = [n for n in names if n != already]
    else:
        return None
    matches = [n for n in names if n.startswith(argument.value)]
    return types.Completion(values=matches, has_more=False)


if __name__ == "__main__":
    mcp.run()
