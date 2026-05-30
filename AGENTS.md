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
