"""Turning evidence into an answer."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Evidence:
    """What the three servers said, and what failed."""

    facts: dict[str, Any] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)

    def record(self, key: str, value: Any) -> None:
        self.facts[key] = value

    def missing(self, what: str, why: str) -> None:
        self.gaps.append(f"{what}: {why}")


@dataclass
class Verdict:
    """The answer, with its reasoning attached."""

    safe: bool
    confidence: str
    reasons: list[str]
    gaps: list[str]

    def render(self) -> str:
        head = "SAFE TO SHIP" if self.safe else "DO NOT SHIP"
        lines = [f"{head} (confidence: {self.confidence})"]
        lines += [f"  - {r}" for r in self.reasons]
        if self.gaps:
            lines.append("  unanswered:")
            lines += [f"    - {g}" for g in self.gaps]
        return "\n".join(lines)


def decide(evidence: Evidence, criteria: dict[str, float]) -> Verdict:
    """Apply the team's release criteria to the evidence."""
    reasons: list[str] = []
    safe = True

    rate = evidence.facts.get("failure_rate")
    if rate is None:
        safe = False
        reasons.append("no build history available")
    elif rate > criteria["max_failure_rate"]:
        safe = False
        reasons.append(
            f"build failure rate {rate:.0%} exceeds "
            f"{criteria['max_failure_rate']:.0%}"
        )
    else:
        reasons.append(f"build failure rate {rate:.0%} is acceptable")

    flaky = evidence.facts.get("flaky_tests", 0)
    if flaky > criteria["max_flaky_tests"]:
        safe = False
        reasons.append(f"{flaky} flaky tests, limit {criteria['max_flaky_tests']}")
    else:
        reasons.append(f"{flaky} flaky tests")

    files = evidence.facts.get("files_changed")
    if files is not None:
        reasons.append(f"{files} files changed across {evidence.facts.get('commits', '?')} commits")
        if files > criteria["max_files_changed"]:
            safe = False
            reasons.append(f"change is larger than {criteria['max_files_changed']} files")

    confidence = "low" if evidence.gaps else "high"
    return Verdict(safe=safe, confidence=confidence,
                   reasons=reasons, gaps=evidence.gaps)
