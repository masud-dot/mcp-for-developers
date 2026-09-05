"""Integration: per-record authorization."""

import pytest


@pytest.fixture
def notes_server(monkeypatch):
    monkeypatch.setenv("MCPDEV_AUTH_SIGNING_KEY", "s" * 32)
    import importlib

    import mcpdev.config as config
    from mcpdev.config import Settings

    config.settings = Settings()
    import mcpdev.servers.notes as notes

    importlib.reload(notes)
    return notes.mcp


async def test_index_lists_only_your_notes(
    connect, notes_server, as_caller
):
    as_caller("alice@example.com")
    async with connect(notes_server) as client:
        body = (await client.read_resource("notes://index"))
    assert body.contents[0].text.split() == ["release", "standup"]


async def test_other_callers_note_is_refused(
    connect, notes_server, as_caller
):
    as_caller("alice@example.com")
    async with connect(notes_server) as client:
        with pytest.raises(Exception) as caught:
            await client.read_resource("notes://salaries")
    assert "salaries" in str(caught.value)


async def test_refusal_matches_a_missing_note(
    connect, notes_server, as_caller
):
    """Not-permitted must be indistinguishable from not-found."""
    as_caller("alice@example.com")
    async with connect(notes_server) as client:
        with pytest.raises(Exception) as forbidden:
            await client.read_resource("notes://salaries")
        with pytest.raises(Exception) as missing:
            await client.read_resource("notes://nope")
    def shape(exc):
        return str(exc).replace("salaries", "X").replace("nope", "X")

    assert shape(forbidden.value) == shape(missing.value)
