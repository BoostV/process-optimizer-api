# AGENTS

- Before large refactors, run `python -m pytest`, `flake8 . --max-line-length=127`, and `mypy optimizerapi` to match CI.
- Consult `README.md` alongside this file for end-user setup and deployment details.
- Dev server runs on port 9090; Swagger UI at `/v1.0/ui/`.
- Follow existing style: double quotes for JSON-like payload keys, snake_case for functions/variables, CapWords for classes.
- For development dependencies: `uv pip install -e ".[dev]"`
- Handle errors explicitly; avoid bare `except:` and log or re-raise with context where appropriate.
- Keep functions small and focused; share logic between API handlers and tests instead of duplicating.
- Keep module-level constants UPPER_SNAKE_CASE; avoid one-letter names except simple indices.
- Lint locally with `flake8 . --max-line-length=127` (matches CI workflow).
- No Cursor or GitHub Copilot instruction files are present; if added later, update this AGENTS file to reference them.
- Prefer pure functions where practical; avoid side effects in import time except for necessary configuration.
- Prefer standard-library imports, then third-party, then local; keep tests mirroring src layout.
- Preserve current behavior around environment variables (e.g. `FLASK_ENV`, `CORS_ORIGIN`, `USE_WORKER`).
- Run a single test by node id, e.g. `python -m pytest tests/test_optimizer.py::test_can_be_run_without_data`.
- Run a single test module via `python -m pytest tests/test_optimizer.py`.
- Run the full test suite with `python -m pytest` (watch mode: `ptw`).
- Run the worker (requires Redis) with `python -m optimizerapi.worker`.
- Start the dev server with `python -m optimizerapi.server` (see README.md).
- Type-check locally with `mypy optimizerapi` (matches CI workflow); see `[tool.mypy]` in `pyproject.toml`.
- Type hints are required on new or changed public functions; keep signatures simple and ensure `mypy optimizerapi` passes.
- Use Python 3.13 (pinned in `mise.toml`); with [mise](https://mise.jdx.dev/) installed, `mise install` provisions Python, `uv`, and `.venv` automatically. Without mise, install Python 3.13 and `uv` manually, then `uv pip install -e .`.
- When adding dependencies, update `pyproject.toml` in the `dependencies` array
  (or `dev` in `optional-dependencies` for dev tools) and verify with `git diff`
  (see README.md).
- When modifying the API, update `optimizerapi/openapi/specification.yml` and keep handler names consistent.
- Write tests under `tests/` using `pytest` style; use `unittest.mock.patch` for external effects as in `tests/test_optimizer.py`.

## Decisions and finishing a branch

- **ADRs are the only durable design doc on `main`.** Significant decisions live
  as Architecture Decision Records under `docs/adr/` (Nygard format); see
  `docs/adr/README.md` for the bar and the workflow. Write one only when a future
  maintainer would ask "why is it like this?" and the code won't answer. Most
  branches need none — one ADR per branch is a smell.
- **Agent-generated plans/specs are branch-only working artifacts.** The
  spec/plan files produced while building (e.g. under `docs/superpowers/`) may
  stay on the branch and in the PR for review, but are removed in a cleanup
  commit before merge so they don't accumulate on `main`. Their durable content,
  if any, is distilled into an ADR first.
- **Branch-finalize flow** (advisory — the agent surfaces it, nothing enforces
  it): when wrapping up a branch, (1) decide whether the work warrants an ADR and
  draft it with human approval, (2) run the CI checks (`python -m pytest`,
  `flake8 . --max-line-length=127`, `mypy optimizerapi`), (3) remove the
  branch's plans/specs in a cleanup commit, then (4) open the PR / merge. The
  Claude Code `finish-branch` skill (`.claude/skills/finish-branch/`) encodes
  this; this policy is vendor-neutral and applies under any agent framework.

## Architecture

This is an OpenAPI-first REST API wrapping [ProcessOptimizer](https://github.com/novonordisk-research/ProcessOptimizer) (Bayesian optimization). The API has a single main endpoint: `POST /optimizer`.

**Request flow:** Connexion validates requests against `optimizerapi/openapi/specification.yml`, routes to handler via `operationId`, handler dispatches to optimizer core logic.

Key modules:
- `optimizerapi/server.py` — Flask/Connexion app init, CORS, Waitress (prod) vs Flask dev server
- `optimizerapi/openapi/specification.yml` — OpenAPI 3.0 spec; defines all schemas and wires handlers via `operationId`
- `optimizerapi/optimizer_handler.py` — HTTP handler; optionally routes work through Redis/RQ job queue (`USE_WORKER=true`) with SHA256-based dedup
- `optimizerapi/optimizer.py` — Core logic: runs optimizer, generates plots (base64 PNG or JSON), handles pickled model reuse, multi-objective support
- `optimizerapi/securepickle/` — Fernet encryption for pickled optimizer state (`PICKLE_KEY` env var)
- `optimizerapi/auth.py` — Optional Keycloak OIDC or static API key auth

**Multi-objective:** When `yi` arrays have >1 element, the optimizer runs in multi-objective mode with separate per-objective plots (`objective_1_*`, `objective_2_*`) and pareto front data.

**Pickled model flow:** Client sends `extras.pickled` to skip expensive GP retraining. If unpickling fails (corrupt, wrong key, schema change), falls back to full run with a warning log.

**Plot formats:** `extras.graphFormat` controls output — `"png"` returns base64 PNG, `"json"` returns structured plot data. JSON mode uses `_get_brownie_bee_1d_plot_safe()` which works around a ProcessOptimizer bug with categorical dimensions.
