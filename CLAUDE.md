# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install
pip install -e .            # production deps
pip install -e ".[dev]"     # + dev deps (pytest, pytest-watch)

# Test
python -m pytest                                            # full suite
python -m pytest tests/test_optimizer.py                    # single module
python -m pytest tests/test_optimizer.py::test_name         # single test
ptw                                                         # watch mode

# Lint (matches CI)
flake8 . --max-line-length=127

# Run dev server (port 9090, Swagger UI at /v1.0/ui/)
python -m optimizerapi.server

# Run worker (requires Redis)
python -m optimizerapi.worker
```

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

## Style

- Double quotes for JSON-like payload keys, snake_case for functions/variables, CapWords for classes
- UPPER_SNAKE_CASE for module-level constants
- When modifying the API contract, update `optimizerapi/openapi/specification.yml` and keep handler `operationId` names consistent
- When adding dependencies, update `pyproject.toml` (`dependencies` or `optional-dependencies.dev`)
- Python 3.9+; type hints optional
