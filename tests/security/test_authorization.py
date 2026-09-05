"""Security: every rejection path, as a matrix."""

import time

import pytest

from mcpdev.security.auth import JWTVerifier

CASES = [
    ("valid", {}, True),
    ("expired", {"exp": int(time.time()) - 10}, False),
    ("wrong audience", {"aud": "https://other.example.com"}, False),
    ("wrong issuer", {"iss": "https://evil.example.com"}, False),
    ("no subject", {"sub": None}, False),
    ("no expiry", {"exp": None}, False),
]


@pytest.mark.parametrize("label,overrides,should_pass", CASES)
async def test_token_matrix(
    token_factory, label, overrides, should_pass
):
    claims = {k: v for k, v in overrides.items() if v is not None}
    drop = [k for k, v in overrides.items() if v is None]
    token = token_factory(**claims)
    if drop:
        import jwt

        decoded = jwt.decode(token, options={"verify_signature": False})
        for key in drop:
            decoded.pop(key, None)
        token = jwt.encode(decoded, "s" * 32, algorithm="HS256")
    verified = await JWTVerifier().verify_token(token)
    assert (verified is not None) is should_pass, label


async def test_wrong_signing_key_is_rejected(token_factory):
    token = token_factory(key="w" * 32)
    assert await JWTVerifier().verify_token(token) is None


async def test_scopes_are_extracted(token_factory):
    verified = await JWTVerifier().verify_token(
        token_factory(scope="mcp:read ops:freeze"))
    assert set(verified.scopes) == {"mcp:read", "ops:freeze"}
    assert verified.subject == "alice@example.com"
