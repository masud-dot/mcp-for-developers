"""Operations server: approval-gated actions."""

from typing import Annotated

from pydantic import BaseModel, Field

from mcp.server.mcpserver import (
    AcceptedElicitation,
    DeclinedElicitation,
    Elicit,
    ElicitationResult,
    MCPServer,
    RequestStateSecurity,
    Resolve,
)

from mcp.server.auth.settings import AuthSettings

from mcpdev.config import settings
from mcpdev.security.auth import JWTVerifier, principal, requires_scope

mcp = MCPServer(
    "ops",
    version="1.0.0",
    request_state_security=RequestStateSecurity(
        keys=[settings.request_state_key]
    ),
    token_verifier=JWTVerifier(),
    auth=AuthSettings(
        issuer_url=settings.auth_issuer,
        resource_server_url=settings.auth_audience,
        required_scopes=["mcp:read"],
    ),
)


class Confirm(BaseModel):
    """What a person must answer before deploys are frozen."""

    proceed: bool = Field(description="Freeze deploys now?")
    reason: str = Field(default="", description="Why")


@requires_scope("ops:freeze")
def ask_freeze(service: str) -> Elicit[Confirm]:
    """Resolver: authorized callers only. Runs on leg one, so
    an unauthorized caller never reaches a human.
    """
    return Elicit(f"Freeze deploys for {service}?", Confirm)


@mcp.tool()
@requires_scope("ops:freeze")
def request_deploy_freeze(
    service: str,
    approval: Annotated[
        ElicitationResult[Confirm], Resolve(ask_freeze)
    ],
) -> str:
    """Freeze deploys. Requires human approval."""
    ok = isinstance(approval, AcceptedElicitation)
    if ok and approval.data.proceed:
        return (
            f"FROZEN {service} by {principal()}: "
            f"{approval.data.reason}"
        )
    if isinstance(approval, DeclinedElicitation):
        return f"NOT FROZEN {service}: declined"
    return f"NOT FROZEN {service}: cancelled"


if __name__ == "__main__":
    mcp.run()
