"""Protections the SDK does not provide for you."""

import ipaddress
import re
import socket
from urllib.parse import urlparse

from mcpdev.errors import InvalidInput

BLOCKED_NETS = [
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        "127.0.0.0/8", "169.254.0.0/16", "0.0.0.0/8",
        "::1/128", "fc00::/7", "fe80::/10",
    )
]

SECRET_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\b(?:bearer\s+)?[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"
        r"\.[A-Za-z0-9_-]{10,}\b",
        r"\bgh[pousr]_[A-Za-z0-9]{16,}\b",
        r"\b(?:sk|rk)-[A-Za-z0-9]{16,}\b",
        r"(?i)(api[_-]?key|secret|password|token)"
        r"\s*[=:]\s*\S{8,}",
    )
]


def safe_url(candidate: str, allowed_hosts: set[str]) -> str:
    """Reject a URL that could reach somewhere it should not."""
    parsed = urlparse(candidate)
    if parsed.scheme != "https":
        raise InvalidInput(
            f"Only https URLs are accepted, not {parsed.scheme!r}."
        )
    host = parsed.hostname or ""
    if host.lower() not in allowed_hosts:
        raise InvalidInput(
            f"{host!r} is not an allowed host. Allowed: "
            f"{', '.join(sorted(allowed_hosts))}."
        )
    for family, _, _, _, sockaddr in socket.getaddrinfo(host, None):
        address = ipaddress.ip_address(sockaddr[0])
        if any(address in net for net in BLOCKED_NETS):
            raise InvalidInput(
                f"{host!r} resolves to a non-public address."
            )
    return candidate


def redact(text: str) -> str:
    """Remove things that look like credentials."""
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[redacted]", text)
    return text
