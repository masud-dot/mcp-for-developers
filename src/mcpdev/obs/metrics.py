"""The four metrics that predict an MCP incident."""

from opentelemetry import metrics

_meter = metrics.get_meter("mcpdev")

calls = _meter.create_counter(
    "mcp.tool.calls",
    description="Tool invocations, by tool and outcome.",
)
latency = _meter.create_histogram(
    "mcp.tool.duration",
    unit="ms",
    description="Time to serve a tool call.",
)
upstream_failures = _meter.create_counter(
    "mcp.upstream.failures",
    description="Upstream calls that failed, by classification.",
)
auth_rejections = _meter.create_counter(
    "mcp.auth.rejections",
    description="Requests refused, by reason.",
)


def record_call(tool: str, outcome: str, ms: float) -> None:
    """One call, one measurement, two series."""
    attributes = {"tool": tool, "outcome": outcome}
    calls.add(1, attributes)
    latency.record(ms, attributes)
