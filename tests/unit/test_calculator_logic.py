"""Unit: the function under the tool, called directly."""

import pytest

from mcpdev.errors import InvalidInput
from mcpdev.servers.calculator import Sample, divide, summarize


def test_divide_returns_quotient():
    assert divide(10, 4) == 2.5


def test_divide_by_zero_is_invalid_input():
    with pytest.raises(InvalidInput) as caught:
        divide(1, 0)
    assert "non-zero" in str(caught.value)


def test_summarize_rounds_mean():
    out = summarize(Sample(values=[2, 4, 6, 9], precision=1))
    assert (out.count, out.total, out.mean) == (4, 21.0, 5.2)


def test_summarize_rejects_empty_batch():
    with pytest.raises(ValueError):
        Sample(values=[])
