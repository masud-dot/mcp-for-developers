# mcp-for-developers

Companion code for **Model Context Protocol (MCP) for Developers — Build, Secure, and Deploy MCP Servers and Clients with Python**.

Every listing in the book was executed against this repository before the
chapter shipped. Filenames, module paths, environment variables, and command
lines match the text from Chapter 4 through Chapter 28.

## Technical baseline

The book pins exactly, and so does this repository:

| | |
|---|---|
| MCP specification | `2026-07-28` |
| Python SDK | `mcp==2.1.1`, `mcp-types==2.1.1` |
| Python | 3.12 or later |
| HTTP client | `httpx2` — the SDK ships the 2.x line under that name; `import httpx` fails |

The pin is exact rather than a floor. Protocol revisions are dates, the SDK
tracks them, and a book that says "install the latest" is a book whose examples
stop matching its text on the first minor release.

## Quick start

```bash
uv sync
uv run pytest -q
uv run mcp dev src/mcpdev/servers/calculator.py
```

## Running the capstone

The Release-Readiness Copilot needs a build history. The seed script is
deterministic and window-stable, so the numbers in Chapter 28 reproduce
whenever you run it:

```bash
uv run python scripts/seed_builds.py builds.db
export MCPDEV_CI_DB_PATH=builds.db
export MCPDEV_HANDLE_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
export MCPDEV_REQUEST_STATE_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
export MCPDEV_AUTH_SIGNING_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
```

Each key must be **at least 32 bytes** — the SDK refuses to start otherwise — and **identical across every replica**. The SDK generates a
per-process `requestState` key by default, which means approval flows fail
intermittently across instances until you set one yourself. Chapter 14 measures
exactly that.

## Layout

```
src/mcpdev/
  config.py                Ch. 4, extended throughout
  errors.py                Ch. 9    typed, actionable failures
  app.py                   Ch. 18   ASGI factory, health and readiness
  servers/
    smoke.py               Ch. 4    teaching only
    calculator.py          Ch. 5, 6, 9, 16
    notes.py               Ch. 7, 8, 21
    _patterns.py           Ch. 6    shared tool patterns
    repo.py                Ch. 10, 21    capstone
    ci.py                  Ch. 11        capstone
    ops.py                 Ch. 14, 20    capstone
  client/
    session.py             Ch. 12, 14    capstone
    loop.py                Ch. 13        capstone
    registry.py            Ch. 15        capstone
  security/
    auth.py                Ch. 20   token verification, per-tool scopes
    guards.py              Ch. 21   SSRF allow-listing, redaction
    audit.py               Ch. 22   structured audit middleware
  obs/                     Ch. 25   tracing, logging, metrics
  copilot/                 Ch. 28   the capstone
tests/
  unit/ contract/ negative/ integration/ security/
  golden/                  committed catalog snapshots
deploy/                    nginx, cache hints, catalog entry
scripts/seed_builds.py     Ch. 28   deterministic fixture
examples/mount_two.py      Ch. 16   two servers in one ASGI app
```

## Continuous integration

`.github/workflows/ci.yml` runs eight stages, ordered by how fast they fail:
lint, types, then the five test suites, then conformance as advisory only.
No repository secrets are required; the security suite mints its own throwaway
JWTs.

Lint and type settings live in `pyproject.toml`, and every exception is
documented there with the chapter that explains the convention.

## Tests

Five layers, and each catches something the layer below cannot see.

```bash
uv run pytest tests/unit -q          # logic, in isolation
uv run pytest tests/integration -q   # through a real client session
uv run pytest tests/contract -q      # golden-file catalog snapshots
uv run pytest tests/negative -q      # error paths
uv run pytest tests/security -q      # hostile input, authorization matrix
```

The contract suite is the one worth understanding. Rename a tool and unit and
integration tests both stay green, because they test the renamed tool. Only a
comparison against a stored snapshot notices that the name a external caller
depends on has changed.

## Deliberate gaps

Three things here are knowingly incomplete, because the book uses them to teach.
**Do not deploy any of them as they are.**

- `smoke.py` and the early `calculator.py` are teaching artifacts, superseded
  rather than maintained.
- `repo.py` has no per-record authorization and holds a shared upstream
  credential. Chapter 27 uses it as a security-review exercise for exactly that
  reason — a review that finds nothing was not a review.
- `notes.py` gains authorization only in Chapter 21. Earlier chapters show it
  without.

`divide` in `calculator.py` also stays deliberately broken from Chapter 5 until
Chapter 9, where failure design is the subject.

## Container

`Dockerfile` and `docker-compose.yml` are written to current practice: two-stage
build, `uv sync --locked --no-dev`, non-root UID 10001, read-only root
filesystem, dropped capabilities, and required secrets enforced with `:?`.

**They have not been built or run.** No container runtime was available in the
environment where this repository was developed. Build before you rely on them.

## License

See `LICENSE`.
