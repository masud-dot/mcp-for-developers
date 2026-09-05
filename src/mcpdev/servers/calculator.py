"""A calculator server: four tools, two transports."""

from pydantic import BaseModel, Field

from mcp.server.mcpserver import MCPServer

from mcpdev.errors import InvalidInput
from mcpdev.servers._patterns import READ_ONLY

mcp = MCPServer("calculator", version="1.0.0")


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum."""
    return a + b


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a and return the difference."""
    return a - b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers and return the product."""
    return a * b


@mcp.tool(annotations=READ_ONLY)
def divide(a: float, b: float) -> float:
    """Divide a by b and return the quotient. b must not be
    zero.
    """
    if b == 0:
        raise InvalidInput(
            "Cannot divide by zero. Supply a non-zero value for "
            "b, or check whether the numerator is what you meant "
            "to divide."
        )
    return a / b


class Sample(BaseModel):
    """A batch of numbers to summarize."""

    values: list[float] = Field(
        min_length=1,
        description="The numbers to summarize. At least one.",
    )
    precision: int = Field(
        default=2, ge=0, le=10,
        description="Decimal places for the mean.",
    )


class Summary(BaseModel):
    """Descriptive statistics for one batch."""

    count: int = Field(description="How many values were supplied.")
    total: float = Field(description="Sum of the values.")
    mean: float = Field(description="Arithmetic mean, rounded.")
    smallest: float = Field(description="Minimum value.")
    largest: float = Field(description="Maximum value.")


@mcp.tool(annotations=READ_ONLY)
def summarize(sample: Sample) -> Summary:
    """Compute count, sum, mean, minimum and maximum for a batch
    of numbers. Use this instead of calling add repeatedly when
    you have more than two values.
    """
    v = sample.values
    return Summary(
        count=len(v),
        total=sum(v),
        mean=round(sum(v) / len(v), sample.precision),
        smallest=min(v),
        largest=max(v),
    )


if __name__ == "__main__":
    mcp.run()
