"""The Release-Readiness Copilot: three servers, one question."""

import asyncio
import sys
from dataclasses import dataclass

from mcpdev.client.registry import Registry
from mcpdev.client.session import ServerSpec
from mcpdev.copilot.verdict import Evidence, Verdict, decide

CRITERIA = {
    "max_failure_rate": 0.15,
    "max_flaky_tests": 2,
    "max_files_changed": 50,
}

SERVERS = [
    ServerSpec(name=n, command=sys.executable,
               args=["-m", f"mcpdev.servers.{n}"])
    for n in ("repo", "ci", "ops")
]


@dataclass
class Release:
    """What is being shipped."""

    owner: str
    name: str
    base: str
    head: str
    service: str


async def _gather(reg: Registry, release: Release) -> Evidence:
    """Ask each server what it knows. Never raise."""
    evidence = Evidence()

    summary = await reg.call("repo.change_summary", {
        "owner": release.owner, "name": release.name,
        "base": release.base, "head": release.head})
    if summary.is_error:
        evidence.missing("change size", summary.content[0].text)
    else:
        evidence.record("files_changed",
                        summary.structured_content["files_changed"])
        evidence.record("commits",
                        summary.structured_content["commits"])

    opened = await reg.call("ci.open_build_query", {
        "service": release.service, "days": 14})
    if opened.is_error:
        evidence.missing("build history", opened.content[0].text)
        return evidence

    handle = opened.structured_content["handle"]
    health = await reg.call("ci.failure_summary", {"handle": handle})
    if health.is_error:
        evidence.missing("build health", health.content[0].text)
    else:
        evidence.record("failure_rate",
                        health.structured_content["failure_rate"])

    flaky = await reg.call("ci.flaky_tests",
                           {"handle": handle, "limit": 10})
    if flaky.is_error:
        evidence.missing("flaky tests", flaky.content[0].text)
    else:
        evidence.record("flaky_tests",
                        flaky.structured_content["total"])

    return evidence


async def assess(release: Release) -> tuple[Verdict, Registry]:
    """Answer the question. Degrade rather than fail."""
    async with Registry(threshold=2, cooldown_s=30.0) as reg:
        for spec in SERVERS:
            await reg.add(spec)
        evidence = await _gather(reg, release)
        return decide(evidence, CRITERIA), reg
