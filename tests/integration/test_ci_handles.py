"""Integration: handles across independently built servers."""

import importlib

import pytest


async def test_handle_survives_a_different_instance(
    connect, ci_factory
):
    """The whole point of Chapter 11, as a test."""
    async with connect(ci_factory()) as instance_a:
        opened = await instance_a.call_tool(
            "open_build_query",
            {"service": "payments-api", "days": 30},
        )
    handle = opened.structured_content["handle"]
    assert opened.structured_content["matched"] == 20

    async with connect(ci_factory()) as instance_b:
        summary = await instance_b.call_tool(
            "failure_summary", {"handle": handle}
        )
    assert summary.structured_content["total"] == 20
    assert summary.structured_content["failed"] == 5


async def test_tampered_handle_is_refused(connect, ci_factory):
    async with connect(ci_factory()) as client:
        opened = await client.call_tool(
            "open_build_query", {"service": "payments-api"})
        handle = opened.structured_content["handle"]
        bad = handle[:-2] + ("A" if handle[-2] != "A" else "B") + handle[-1]
        result = await client.call_tool(
            "failure_summary", {"handle": bad})
    assert result.is_error is True
    assert "not valid" in result.content[0].text


async def test_sort_field_is_allow_listed(connect, ci_factory):
    async with connect(ci_factory()) as client:
        result = await client.call_tool("open_build_query", {
            "service": "payments-api",
            "sort_by": "id; DROP TABLE builds--"})
    assert result.is_error is True
    assert "sort_by must be one of" in result.content[0].text
