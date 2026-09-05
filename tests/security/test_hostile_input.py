"""Security: hostile inputs, and the authorization matrix."""

import pytest

from tests.conftest import HOSTILE

from mcpdev.errors import InvalidInput
from mcpdev.security.guards import redact, safe_url

ALLOWED = {"api.github.com"}


@pytest.mark.parametrize("candidate", HOSTILE["ssrf"])
def test_ssrf_candidates_are_refused(candidate):
    with pytest.raises(InvalidInput):
        safe_url(candidate, ALLOWED)


def test_allowed_host_passes():
    assert safe_url("https://api.github.com/x", ALLOWED)


@pytest.mark.parametrize("secret", [
    "ghp_ABCDEFGHIJKLMNOPQRSTUV123456",
    "api_key: sk-ABCDEFGHIJKLMNOPQRSTUV",
])
def test_secrets_are_redacted(secret):
    assert secret not in redact(f"failed with {secret}")


@pytest.mark.parametrize(
    "value",
    HOSTILE["sql"] + HOSTILE["command"] + HOSTILE["template"],
)
async def test_hostile_values_are_data_not_code(
    connect, ci_factory, value
):
    """A value is a bound parameter, so it simply matches nothing."""
    async with connect(ci_factory()) as client:
        result = await client.call_tool(
            "open_build_query", {"service": value})
    assert result.is_error is False
    assert result.structured_content["matched"] == 0


@pytest.mark.parametrize("value", HOSTILE["sql"] + HOSTILE["command"])
async def test_hostile_identifiers_are_refused(
    connect, ci_factory, value
):
    """An identifier is allow-listed, so it is refused outright."""
    async with connect(ci_factory()) as client:
        result = await client.call_tool(
            "open_build_query",
            {"service": "payments-api", "sort_by": value})
    assert result.is_error is True
    assert "sort_by must be one of" in result.content[0].text
