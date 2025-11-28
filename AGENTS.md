# AGENTS

- Before large refactors, run `python -m pytest` and `flake8 .` to ensure consistency.
- Follow existing style: double quotes for JSON-like payload keys, snake_case for functions/variables, CapWords for classes.
- For development dependencies: `pip install -e ".[dev]"`
- Handle errors explicitly; avoid bare `except:` and log or re-raise with context where appropriate.
- Keep functions small and focused; share logic between API handlers and tests instead of duplicating.
- Keep module-level constants UPPER_SNAKE_CASE; avoid one-letter names except simple indices (see `.pylintrc`).
- Lint locally with `flake8 . --max-line-length=127` (matches CI workflow).
- No Cursor or GitHub Copilot instruction files are present; if added later, update this AGENTS file to reference them.
- Prefer pure functions where practical; avoid side effects in import time except for necessary configuration.
- Prefer standard-library imports, then third-party, then local; keep tests mirroring src layout.
- Preserve current behavior around environment variables (e.g. `FLASK_ENV`, `CORS_ORIGIN`, `USE_WORKER`).
- Run a single test by node id, e.g. `python -m pytest tests/test_optimizer.py::test_can_be_run_without_data`.
- Run a single test module via `python -m pytest tests/test_optimizer.py`.
- Run the full test suite with `python -m pytest` (watch mode: `ptw`).
- Start the dev server with `python -m optimizerapi.server` (see README.md).
- Type hints are optional; when adding them, use Python typing and keep function signatures simple.
- Use Python 3.9+ and `pip install -e .` before running.
- When adding dependencies, update `pyproject.toml` in the `dependencies` array
  (or `dev` in `optional-dependencies` for dev tools) and verify with `git diff`
  (see README.md).
- When modifying the API, update `optimizerapi/openapi/specification.yml` and keep handler names consistent.
- Write tests under `tests/` using `pytest` style; use `unittest.mock.patch` for external effects as in `tests/test_optimizer.py`.
