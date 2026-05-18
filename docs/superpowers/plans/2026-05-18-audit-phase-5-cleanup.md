# Audit Phase 5 — Opportunistic Cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the long-tail of code-quality items surfaced by the audit: pre-existing flake8 violations, the `optimizer_handler.py` rough edges, the auth typo, and idiomatic Python tidies that the earlier phases left for last. Bring `flake8 optimizerapi tests --max-line-length=127` fully clean.

**Architecture:** Pure cleanup. No new modules, no new public surface, no behavior changes.

**Tech Stack:** Standard library `secrets`, `pytest`, mypy from Phase 3.

**Audit reference:** §3, §6, §7 of the audit, plus the "pre-existing E501s" deferred through Phases 1–4.

**Prereq:** Phases 1–4 complete. Full pytest is green.

---

## File Map

- **Modify:** `tests/test_optimizer.py` — delete dead comment lines.
- **Modify:** `optimizerapi/securepickle/__init__.py` — add `__all__` to resolve F401.
- **Modify:** `tests/context.py` — remove unused imports or convert to `__all__`.
- **Modify:** `optimizerapi/optimizer_handler.py` — `USE_WORKER` bool parsing; consolidate `disconnect_check`; normalize return shape.
- **Modify:** `optimizerapi/auth.py` — fix `"Authenitcation"` typo.
- **Modify:** `optimizerapi/optimizer.py` — `enumerate` + `.get()` idiomatic wins.

---

### Task 1: Delete dead 400-character comment lines

**Files:**
- Modify: `tests/test_optimizer.py:12-15`

- [ ] **Step 1: Inspect**

```bash
sed -n '11,16p' tests/test_optimizer.py
```

Expected: three comment lines (`#  {'data': ...}`, `#   'data': ...`, `#   'space': ...`, `#   '...'}}`) totaling ~880 characters. These were sample-payload notes from early development.

- [ ] **Step 2: Delete the comment block**

Remove lines 12-15 of `tests/test_optimizer.py`. The block looks like:

```python
#  {'data': [{'xi': [651, 56, 722, 'Ræv'], 'yi': 1}, ...
#   'data': [{'xi': [0, 5, 'Rød'], 'yi': 10}, ...
#   'optimizerConfig': {'baseEstimator': 'GP', ...
#   'space': [{'type': 'discrete', 'name': 'Alkohol', ...
```

The information they recorded is now captured properly in `docs/api-usage.md` and `scripts/sample*.curl`.

- [ ] **Step 3: Verify flake8**

```bash
env/bin/flake8 tests/test_optimizer.py --max-line-length=127
```
Expected: no output. The two E501 violations that have been pre-existing since the redesign are gone.

- [ ] **Step 4: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: unchanged.

- [ ] **Step 5: Commit**

```bash
git add tests/test_optimizer.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
chore(tests): drop dead 400-char sample-payload comments

The sample payloads are now documented properly in docs/api-usage.md
and scripts/sample*.curl. The comments at the top of test_optimizer.py
were one-off dev notes that have been silently failing flake8 E501
for ages.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Fix F401 re-exports in `securepickle/__init__.py`

The package `__init__.py` imports symbols only to re-export them. flake8 reports F401 because there's no `__all__` declaring intent.

**Files:**
- Modify: `optimizerapi/securepickle/__init__.py`

- [ ] **Step 1: Read current state**

```bash
cat optimizerapi/securepickle/__init__.py
```

Expected (current contents):

```python
"""
Secure pickle module
"""
from .pickler import pickleToString, unpickleFromString
from .secure import get_crypto
```

- [ ] **Step 2: Add `__all__`**

Replace with:

```python
"""Secure pickle module — Fernet-encrypted pickle round-trip."""

from .pickler import pickleToString, unpickleFromString
from .secure import get_crypto

__all__ = ["get_crypto", "pickleToString", "unpickleFromString"]
```

- [ ] **Step 3: Verify flake8**

```bash
env/bin/flake8 optimizerapi/securepickle/__init__.py --max-line-length=127
```
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add optimizerapi/securepickle/__init__.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
chore(securepickle): declare __all__ to resolve F401 on re-exports

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Clean up `tests/context.py`

**Files:**
- Modify: `tests/context.py`

- [ ] **Step 1: Read current state**

```bash
cat tests/context.py
```

Decide based on what you find:

- If `context.py` is an unused / abandoned test helper: delete the file and remove any imports of it. (You'll need to `grep -rn "from .context\|from tests.context\|from context" tests/ optimizerapi/` first.)
- If it is used somewhere: convert its imports into a `__all__` block similar to Task 2.

- [ ] **Step 2: Apply the fix**

In practice, this file imports `optimizer` and `securepickle` for tests to use without going through the full package path. If nothing imports `tests.context`, delete the file. Otherwise add:

```python
"""Test-only convenience re-exports."""

from optimizerapi import optimizer, securepickle

__all__ = ["optimizer", "securepickle"]
```

- [ ] **Step 3: Verify**

```bash
env/bin/flake8 tests/context.py --max-line-length=127
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: no flake8 output; pytest unchanged.

- [ ] **Step 4: Commit**

```bash
git add tests/context.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
chore(tests): tidy tests/context.py (or delete if unused)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

(If the file was deleted, mention that in the commit body.)

---

### Task 4: Sweep `optimizer_handler.py`

Three small wins, one commit.

**Files:**
- Modify: `optimizerapi/optimizer_handler.py`

- [ ] **Step 1: Fix `USE_WORKER` boolean parsing**

Find:

```python
    if "USE_WORKER" in os.environ and os.environ["USE_WORKER"]:
```

The bug: `os.environ["USE_WORKER"] = "false"` is truthy. Any non-empty string passes this gate.

Replace with:

```python
    if _parse_env_bool("USE_WORKER"):
```

Add this helper at module scope (after the imports, before `_LOG`):

```python
def _parse_env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean-ish env var.

    Accepts "true", "1", "yes" (case-insensitive) as True.
    Anything else — including unset or "false" — is False.
    """
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("true", "1", "yes")
```

- [ ] **Step 2: Consolidate `disconnect_check`**

The current function defines `disconnect_check` three separate ways depending on which Connexion / Flask state is reachable. Replace:

```python
    try:
        if "waitress.client_disconnected" in connexion.request.environ:
            disconnect_check = connexion.request.environ["waitress.client_disconnected"]
        else:

            def disconnect_check():
                return False

    except RuntimeError:

        def disconnect_check():
            return False
```

with:

```python
    disconnect_check = _resolve_disconnect_check()
```

And add the helper at module scope:

```python
def _resolve_disconnect_check():
    """Return a callable that reports whether the client has disconnected.

    Outside of a request context (e.g. unit tests) or when running under
    a server that doesn't expose ``waitress.client_disconnected``, this
    returns a no-op that always says "still connected".
    """
    try:
        env = connexion.request.environ
    except RuntimeError:
        return lambda: False
    return env.get("waitress.client_disconnected", lambda: False)
```

- [ ] **Step 3: Normalize `do_run_work` return shape**

Currently the success path returns a `dict` while the error paths return a `(dict, status_code)` tuple. Make all paths return the tuple shape so callers don't branch on it.

Find:

```python
def do_run_work(body) -> dict:
    """ "Handle the run request"""
    try:
        return handle_run(body)
    except IOError as err:
        return ({"message": "I/O error", "error": str(err)}, 400)
    except TypeError as err:
        return ({"message": "Type error", "error": str(err)}, 400)
    except ValueError as err:
        return ({"message": "Validation error", "error": str(err)}, 400)
    except Exception as err:
        # Log unknown exceptions to support debugging
        traceback.print_exc()
        return ({"message": "Unknown error", "error": str(err)}, 500)
```

Replace with:

```python
def do_run_work(body: "RequestBody") -> "ResponseEnvelope":
    """Handle the run request.

    On error we let Connexion translate the exception into the OpenAPI-
    declared 400 / 500 response. The handler stops being a tuple-returning
    special case.
    """
    try:
        return handle_run(body)
    except (IOError, TypeError, ValueError) as err:
        _LOG.warning("client error: %s", err)
        raise connexion.problem(400, "Bad request", str(err))
    except Exception as err:
        _LOG.exception("unexpected error during optimizer run")
        raise connexion.problem(500, "Internal server error", str(err))
```

If the project's Connexion version does not support `connexion.problem` (`2.14.2` does, as `from connexion.exceptions import ProblemException` or similar), substitute the explicit `flask.abort(...)` / raise-with-status path. Test on the dev server before committing.

If `connexion.problem` returns a `(body, status)` tuple rather than an exception, adapt:

```python
    try:
        return handle_run(body)
    except (IOError, TypeError, ValueError) as err:
        _LOG.warning("client error: %s", err)
        return connexion.problem(400, "Bad request", str(err))
    except Exception as err:
        _LOG.exception("unexpected error during optimizer run")
        return connexion.problem(500, "Internal server error", str(err))
```

Either way, the result is that `traceback.print_exc()` (a print equivalent) is gone — the same diagnostics flow via `_LOG.exception`, which includes the traceback automatically.

- [ ] **Step 4: Add the imports if missing**

At the top, ensure `connexion` is imported (it already is — used elsewhere in the file). No new imports needed.

- [ ] **Step 5: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: full suite still green. If a test expected the old tuple-return shape, fix it (the test was testing the bug, not the contract).

- [ ] **Step 6: Smoke-test the server with the worker path off and on**

```bash
USE_WORKER=false timeout 5 env/bin/python -m optimizerapi.server 2>&1 | head -10 || true
```

Expected: no log line saying "USE_WORKER detected" — the explicit `false` is correctly parsed.

- [ ] **Step 7: Commit**

```bash
git add optimizerapi/optimizer_handler.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
refactor(handler): _parse_env_bool, single disconnect_check resolver, normalized error path

Fixes the USE_WORKER='false' truthiness bug, collapses three near-
identical disconnect_check definitions, and routes errors via
connexion.problem so do_run_work returns a single declared shape
instead of a mixed dict/tuple.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Fix `Authenitcation` typo and an idiomatic-Python sweep

**Files:**
- Modify: `optimizerapi/auth.py`
- Modify: `optimizerapi/optimizer.py`

- [ ] **Step 1: Fix the auth.py docstring typo**

Find:

```python
"""Authenitcation module

This module will verify tokens provided bt a Keycloak OpenID server
"""
```

Replace with:

```python
"""Authentication module.

Verifies bearer tokens issued by a Keycloak OpenID server, and the
static API key provided via ``AUTH_API_KEY``.
"""
```

(Also fixes "bt" → "by".)

- [ ] **Step 2: `enumerate` for `round_to_length_scales` in `optimizer.py`**

Find:

```python
    for dim, i in zip(space.dimensions, range(len(space.dimensions))):
```

Replace with:

```python
    for i, dim in enumerate(space.dimensions):
```

- [ ] **Step 3: `in (...)` for the dimension-type check in `optimizer.py`**

Find:

```python
            if (x["type"] == "discrete" or x["type"] == "continuous")
```

Replace with:

```python
            if x["type"] in ("discrete", "continuous")
```

- [ ] **Step 4: `.get()` for the `extras` and `constraints` parses in `optimizer.run`**

Find:

```python
    cfg = body["optimizerConfig"]
    constraints = cfg["constraints"] if "constraints" in cfg else []
    extras = body["extras"] if "extras" in body else {}
```

Replace with:

```python
    cfg = body["optimizerConfig"]
    constraints = cfg.get("constraints", [])
    extras = body.get("extras", {})
```

- [ ] **Step 5: Verify lint + suite**

```bash
env/bin/flake8 optimizerapi --max-line-length=127
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: no new flake8 output; pytest green.

- [ ] **Step 6: Commit**

```bash
git add optimizerapi/auth.py optimizerapi/optimizer.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
chore: typo fix + small idiomatic Python sweep

- auth.py: 'Authenitcation' → 'Authentication', 'bt' → 'by'
- optimizer.py: enumerate; tuple membership for dim type;
  .get() defaults for cfg.constraints and body.extras

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Optional — convert sample fixtures to `@pytest.fixture`

This is offered as a discrete task because it touches many test signatures. Skip if appetite is low; the module-level constants work today and tests mostly `copy.deepcopy` defensively.

**Files:**
- Modify: `tests/test_optimizer.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `tests/conftest.py`**

Pull the read-only fixtures out of `test_optimizer.py`:

```python
"""Shared fixtures for the optimizer test suite."""

import copy

import pytest


@pytest.fixture
def sample_data():
    return copy.deepcopy([
        {"xi": [651, 56, 722, "Ræv"], "yi": [1]},
        {"xi": [651, 42, 722, "Ræv"], "yi": [0.2]},
    ])


@pytest.fixture
def sample_config():
    return copy.deepcopy({
        "baseEstimator": "GP",
        "acqFunc": "gp_hedge",
        "initialPoints": 2,
        "kappa": 1.96,
        "xi": 0.012,
        "space": [
            {"type": "discrete", "name": "Sukker", "from": 0, "to": 1000},
            {"type": "continuous", "name": "Peber", "from": 0, "to": 1000},
            {"type": "continuous", "name": "Hvedemel", "from": 0, "to": 1000},
            {"type": "category", "name": "Kunde", "categories": ["Mus", "Ræv"]},
        ],
    })


@pytest.fixture
def sample_multi_objective_5dim_data():
    return copy.deepcopy([
        {"xi": [16.7, 500, 250, 20, "None"],          "yi": [-2, -17]},
        {"xi": [50,   833, 150, 60, "Whipped cream"], "yi": [-3, -6]},
        {"xi": [58.3, 22,  85,  6,  "Frosting"],      "yi": [-6, -25]},
    ])


@pytest.fixture
def sample_multi_objective_5dim_config():
    return copy.deepcopy({
        "baseEstimator": "GP",
        "acqFunc": "EI",
        "initialPoints": 3,
        "kappa": 1.96,
        "xi": 2,
        "space": [
            {"type": "continuous", "name": "Sugar",       "from": 0, "to": 100},
            {"type": "continuous", "name": "Flour",       "from": 0, "to": 1000},
            {"type": "discrete",   "name": "Temperature", "from": 0, "to": 300},
            {"type": "discrete",   "name": "Time",        "from": 0, "to": 120},
            {"type": "category",   "name": "Finish",
             "categories": ["None", "Frosting", "Whipped cream"]},
        ],
        "constraints": [],
    })
```

- [ ] **Step 2: Migrate `tests/test_optimizer.py` to use the fixtures**

For each test that referenced a module-level constant, add the relevant fixture as a parameter:

```python
# Before
def test_can_be_run_without_data():
    result = optimizer.run(body={"data": [], "optimizerConfig": sampleConfig})
    ...

# After
def test_can_be_run_without_data(sample_config):
    result = optimizer.run(body={"data": [], "optimizerConfig": sample_config})
    ...
```

Repeat for every test in the file. This is mechanical but mass — be patient and re-run pytest after each batch of ~5 tests to catch errors early.

Once every test uses fixtures, delete the module-level `sampleData`, `sampleConfig`, `sampleMultiObjective5DimData`, `sampleMultiObjective5DimConfig` constants from `test_optimizer.py`. (The `sampleMultiObjectiveData`, `brownie_with_constraints`, and `brownie_without_constraints` constants can stay or move to conftest as you prefer.)

- [ ] **Step 3: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: same number of passes as before.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_optimizer.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
refactor(tests): move sample fixtures into conftest.py

Each test now declares its dependencies explicitly via fixture
parameters. Mutating a fixture in one test no longer leaks into others.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Final lint + mypy + pytest

The acceptance gate for the entire audit.

**Files:** none.

- [ ] **Step 1: flake8 clean**

```bash
env/bin/flake8 optimizerapi tests --max-line-length=127
```
Expected: **no output**. Every pre-existing exception is now fixed.

- [ ] **Step 2: mypy clean for `optimizerapi/`**

```bash
env/bin/mypy optimizerapi
```
Expected: 0 errors. (Phase 3 set up the config; Phase 4 cleaned up `optimizer.py`'s body; Phase 5 closes the long-tail gaps.)

If errors remain, fix them inline. They should be small at this point — bad import paths or remaining `Any` leaks at module boundaries.

- [ ] **Step 3: Full test suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 50+ passed (43 original + auth + types + plot_emitters + no-prints + minor). No failures, no errors.

- [ ] **Step 4: No commit required.**

---

## Acceptance criteria (overall audit)

After Phase 5 completes, the following must hold:

- `env/bin/flake8 optimizerapi tests --max-line-length=127` → no output.
- `env/bin/mypy optimizerapi` → 0 errors.
- `env/bin/python -m pytest` → all green.
- `grep -rn "print(" optimizerapi/` → no output (from Phase 2).
- `optimizerapi/optimizer.py:process_result` is under ~80 lines (from Phase 4).
- `optimizerapi/auth.py` uses `secrets.compare_digest` and never prints tokens (from Phase 1).
- `cryptography` is on a current major (from Phase 1).
- The OpenAPI surface is unchanged (response shape and field names preserved across the audit).
- The equivalence test from the pareto redesign still passes (this is the binding behaviour gate).

## Out of scope

- Flask 3 / Connexion 3 migration (separate project).
- Pinning `ProcessOptimizer` to a release tag (no tagged release of the required commit exists at the time of this plan).
- Switching to async / background-only request handling (Phase 6+ if it ever happens).
- Coverage tooling, mutation testing, CI workflow changes.
- Documentation rewrites — `docs/api-usage.md` is current.
