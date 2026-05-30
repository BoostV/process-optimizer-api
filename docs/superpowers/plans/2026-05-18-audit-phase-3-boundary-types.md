# Audit Phase 3 — Boundary Types & Static Checking

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `TypedDict` definitions for the request/response/cache shapes, annotate every public function signature in `optimizerapi/`, and add `mypy` to the dev workflow as a CI-grade type check. Acts as a safety net before the Phase 4 refactor.

**Architecture:** One new module — `optimizerapi/types.py` — owns every boundary `TypedDict`. Modules import the relevant types and use them in signatures only (the runtime structures stay plain dicts, since the request validation lives in Connexion + OpenAPI, not Python). `mypy` is configured in `pyproject.toml` and runs against `optimizerapi/` only (tests are not type-checked yet).

**Tech Stack:** Python 3.13 stdlib `typing` (`TypedDict`, `Literal`, `NotRequired`, `Self`), `mypy`.

**Audit reference:** §2 of the audit. `body: dict` is the only thing keeping the contract honest today; adding types catches mistakes at edit time and makes Phase 4 safer.

**Prereq:** Phase 1 & 2 complete (clean baseline of 48+ tests, no `print` in `optimizerapi/`).

---

## File Map

- **Create:** `optimizerapi/types.py` — all `TypedDict` definitions for request, response, cache.
- **Modify:** `pyproject.toml` — add `mypy>=1.13` to dev deps; add `[tool.mypy]` section.
- **Modify:** `optimizerapi/pickled_state.py` — annotate signatures using the new types.
- **Modify:** `optimizerapi/optimizer_handler.py` — annotate signatures.
- **Modify:** `optimizerapi/optimizer.py` — annotate `run` and `process_result` signatures.
- **Modify:** `AGENTS.md`/`CLAUDE.md` — document `mypy` in the dev loop.

---

### Task 1: Create `optimizerapi/types.py`

**Files:**
- Create: `optimizerapi/types.py`
- Create: `tests/test_types.py` — sanity check the module imports and the types are usable.

- [ ] **Step 1: Write the failing test**

Create `tests/test_types.py`:

```python
"""Sanity checks for the boundary type definitions."""

from optimizerapi.types import (
    CachePayload,
    Constraint,
    DataPoint,
    Dimension,
    Extras,
    OptimizerConfig,
    Plot,
    RequestBody,
    ResponseEnvelope,
    ResponseResult,
    ResponseResultExtras,
)


def test_request_body_accepts_realistic_request():
    """A typical request body matches the RequestBody shape at runtime.

    TypedDicts don't enforce at runtime; we use isinstance(d, dict) as a
    proxy and let mypy catch shape mismatches statically.
    """
    body: RequestBody = {
        "data": [{"xi": [50, 833, 150, 60, "Whipped cream"], "yi": [-3, -6]}],
        "optimizerConfig": {
            "baseEstimator": "GP",
            "acqFunc": "EI",
            "initialPoints": 3,
            "kappa": 1.96,
            "xi": 2,
            "space": [
                {"type": "continuous", "name": "Sugar", "from": 0, "to": 100},
                {"type": "category", "name": "Finish",
                 "categories": ["None", "Whipped cream"]},
            ],
            "constraints": [],
        },
        "extras": {"graphFormat": "json", "includeModel": "true"},
    }
    assert isinstance(body, dict)
    assert body["data"][0]["xi"][-1] == "Whipped cream"


def test_response_envelope_shape():
    response: ResponseEnvelope = {
        "plots": [{"id": "single_0_0", "plot": "{}"}],
        "result": {
            "next": [[1, 2, 3]],
            "models": [],
            "pickled": "",
            "extras": {"pickledUsed": False},
        },
    }
    assert response["result"]["extras"]["pickledUsed"] is False


def test_cache_payload_shape():
    payload: CachePayload = {
        "fingerprint": "a" * 64,
        "result": "opaque",
        "next": [[1, 2]],
        "optimizer": "opaque",
    }
    assert payload["fingerprint"] == "a" * 64
```

- [ ] **Step 2: Run test to verify it fails**

```bash
env/bin/python -m pytest tests/test_types.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'optimizerapi.types'`.

- [ ] **Step 3: Create `optimizerapi/types.py`**

```python
"""Boundary types for the optimizer API.

These ``TypedDict``s describe the shape of the request body, response
envelope, and internal cache payload. They are *static* contracts —
they exist to be checked by ``mypy`` and to document the API to
readers. Runtime validation of incoming requests lives in Connexion +
OpenAPI; we do not duplicate that here.

Note on the ``Dimension`` field name ``from``:
    ``from`` is a Python keyword, so the class-based ``TypedDict``
    syntax cannot declare it. We use the alternative call-based
    syntax to define ``Dimension``.
"""

from typing import Any, Literal, NotRequired, TypedDict


# --- Request types ---------------------------------------------------------

Dimension = TypedDict(
    "Dimension",
    {
        "type": Literal["continuous", "discrete", "category"],
        "name": str,
        "from": NotRequired[float],
        "to": NotRequired[float],
        "categories": NotRequired[list[str]],
    },
)


class Constraint(TypedDict):
    type: Literal["sum"]
    dimensions: list[int]
    value: float


class OptimizerConfig(TypedDict):
    baseEstimator: str
    acqFunc: str
    initialPoints: int
    kappa: float
    xi: float
    space: list[Dimension]
    constraints: NotRequired[list[Constraint]]


class DataPoint(TypedDict):
    xi: list[str | float]
    yi: list[float]


GraphFormat = Literal["png", "json", "none"]
GraphName = Literal["objective", "convergence", "pareto", "single"]
ObjectivePars = Literal["result", "expected_minimum"]


class Extras(TypedDict, total=False):
    objectivePars: ObjectivePars
    graphFormat: GraphFormat
    experimentSuggestionCount: int
    maxQuality: int
    graphs: list[GraphName]
    selectedPoint: list[str | float]
    pickled: str
    # NB: stringly-typed; see audit §3 for the rationale for not migrating yet.
    includeModel: Literal["true", "false"]
    useActualMeasurementHistogram: Literal["true", "false"]


class RequestBody(TypedDict):
    data: list[DataPoint]
    optimizerConfig: OptimizerConfig
    extras: NotRequired[Extras]


# --- Response types --------------------------------------------------------

class Plot(TypedDict):
    id: str
    plot: str  # base64 PNG OR JSON-serialised plot data


class ResponseResultExtras(TypedDict, total=False):
    pickledUsed: bool
    parameters: dict[str, Any]
    libraries: list[str]
    pythonVersion: str
    apiVersion: str
    timeOfExecution: str


class ResponseModel(TypedDict, total=False):
    expected_minimum: list[list[str | float]]
    extras: dict[str, Any]


class ResponseResult(TypedDict, total=False):
    next: list[list[str | float]]
    models: list[ResponseModel]
    pickled: str
    extras: ResponseResultExtras
    expected_minimum: list[list[str | float] | float]


class ResponseEnvelope(TypedDict):
    plots: list[Plot]
    result: ResponseResult


# --- Cache payload (pickled_state) -----------------------------------------

class CachePayload(TypedDict):
    fingerprint: str
    # ProcessOptimizer's OptimizerResult or list thereof — kept opaque
    # so types.py does not depend on the optimizer library.
    result: Any
    next: list[list[str | float]]
    # ProcessOptimizer.Optimizer — also opaque.
    optimizer: Any
```

- [ ] **Step 4: Run tests**

```bash
env/bin/python -m pytest tests/test_types.py -v
```
Expected: PASS, 3 tests.

- [ ] **Step 5: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 51+N passed (48 + 3 new). (`N` is the no-print parametrize tests from Phase 2.)

- [ ] **Step 6: Commit**

```bash
git add optimizerapi/types.py tests/test_types.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
feat(types): add TypedDicts for request, response, and cache payload

Static-only contracts for mypy; runtime validation continues to live in
Connexion + OpenAPI. The new types.py module is the single source of
truth for what the boundary shapes look like in Python.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Install and configure `mypy`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `mypy` to dev deps**

Find:
```
dev = ["pytest==8.3.3", "pytest-watch==4.2.0", "flake8>=7"]
```

Replace with:
```
dev = ["pytest==8.3.3", "pytest-watch==4.2.0", "flake8>=7", "mypy>=1.13"]
```

- [ ] **Step 2: Add `[tool.mypy]` configuration**

Append to the end of `pyproject.toml`:

```toml
[tool.mypy]
files = ["optimizerapi"]
python_version = "3.13"
strict = false
# Start permissive; we tighten as Phase 4 lands.
warn_unused_ignores = true
warn_redundant_casts = true
warn_return_any = true
disallow_any_unimported = false
check_untyped_defs = true
# Third-party libraries that don't ship type stubs.
ignore_missing_imports = true
```

- [ ] **Step 3: Install**

```bash
env/bin/pip install -e ".[dev]" 2>&1 | tail -3
```
Expected: `Successfully installed ... mypy-1.x.x ...`.

- [ ] **Step 4: Capture the baseline**

```bash
env/bin/mypy optimizerapi 2>&1 | tail -20
```

Don't try to fix things yet — this is the baseline that subsequent tasks will whittle down. The expected number of errors is "moderate" (most signatures are untyped today). Take note of the count for reference.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
build: add mypy to dev deps with permissive baseline config

Subsequent tasks tighten signatures module-by-module. Permissive mode
keeps the gate green during the migration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Annotate `pickled_state.py`

**Files:**
- Modify: `optimizerapi/pickled_state.py`

- [ ] **Step 1: Edit**

The current functions are untyped. Add precise signatures using the new types.

Find:
```python
def compute_fingerprint(data, optimizer_config):
    """Return sha256 hex of the canonical-JSON of (data, optimizerConfig).
```

Replace with:
```python
def compute_fingerprint(
    data: list["DataPoint"],
    optimizer_config: "OptimizerConfig",
) -> str:
    """Return sha256 hex of the canonical-JSON of (data, optimizerConfig).
```

Find:
```python
def pack(*, result, next_points, optimizer, fingerprint, crypto):
    """Encrypt a pickled cache payload for the given fingerprint."""
```

Replace with:
```python
def pack(
    *,
    result: object,
    next_points: list[list[str | float]],
    optimizer: object,
    fingerprint: str,
    crypto: "Fernet",
) -> str:
    """Encrypt a pickled cache payload for the given fingerprint."""
```

Find:
```python
def unpack_if_valid(blob, *, expected_fingerprint, crypto):
    """Decrypt and validate a pickled cache payload.
```

Replace with:
```python
def unpack_if_valid(
    blob: str,
    *,
    expected_fingerprint: str,
    crypto: "Fernet",
) -> "CachePayload | None":
    """Decrypt and validate a pickled cache payload.
```

Add the imports at the top of the file (after the existing `import logging`):

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from .types import CachePayload, DataPoint, OptimizerConfig
```

Using `TYPE_CHECKING` keeps import-time light and avoids circular-import risk during the Phase 4 refactor when `optimizer.py` will also start importing from `types.py`.

- [ ] **Step 2: Run mypy on the module**

```bash
env/bin/mypy optimizerapi/pickled_state.py 2>&1 | tail -10
```
Expected: 0 errors (or the same module-local errors mypy reported in the baseline minus the ones the new annotations resolved).

- [ ] **Step 3: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: unchanged (tests don't change behavior).

- [ ] **Step 4: Commit**

```bash
git add optimizerapi/pickled_state.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
types: annotate pickled_state public surface

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Annotate `optimizer_handler.py`

**Files:**
- Modify: `optimizerapi/optimizer_handler.py`

- [ ] **Step 1: Edit signatures**

Find:
```python
def run(body) -> dict:
```

Replace with:
```python
def run(body: "RequestBody") -> "ResponseEnvelope | tuple[dict[str, str], int]":
```

The return-shape is the existing `dict | (dict, status_code)` mix that `do_run_work` produces. (Phase 5 normalizes this.)

Find:
```python
def do_run_work(body) -> dict:
    """ "Handle the run request"""
```

Replace with:
```python
def do_run_work(body: "RequestBody") -> "ResponseEnvelope | tuple[dict[str, str], int]":
    """Handle the run request."""
```

Add at the top of the file:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import RequestBody, ResponseEnvelope
```

- [ ] **Step 2: Run mypy on the module**

```bash
env/bin/mypy optimizerapi/optimizer_handler.py 2>&1 | tail -10
```
Expected: 0 new errors.

- [ ] **Step 3: Run full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: unchanged.

- [ ] **Step 4: Commit**

```bash
git add optimizerapi/optimizer_handler.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
types: annotate optimizer_handler.run and do_run_work

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Annotate `optimizer.py` public entry points

We only annotate `run` and `process_result` here. Helpers stay untyped for now — Phase 4 splits them into smaller pieces and annotates them as it goes.

**Files:**
- Modify: `optimizerapi/optimizer.py`

- [ ] **Step 1: Edit `run` signature**

Find:
```python
def run(body) -> dict:
    """ "Handle the run request"""
```

Replace with:
```python
def run(body: "RequestBody") -> dict:
    """Handle the run request.

    Returns the response envelope as a plain ``dict`` — the json_tricks
    round-trip at the bottom of the function dropping NumPy types is
    why we cannot return ``ResponseEnvelope`` directly without an
    explicit cast.
    """
```

- [ ] **Step 2: Edit `process_result` signature**

Find:
```python
def process_result(result, optimizer, dimensions, cfg, extras, data, space,
                   *, request_fingerprint, pickled_used):
```

Replace with:
```python
def process_result(
    result: object,
    optimizer: object,
    dimensions: list[str],
    cfg: "OptimizerConfig",
    extras: "Extras",
    data: list[tuple[list[str | float], list[float]]],
    space: list,
    *,
    request_fingerprint: str,
    pickled_used: bool,
) -> dict:
```

- [ ] **Step 3: Add the imports**

At the top of the file, near the existing imports, add:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import Extras, OptimizerConfig, RequestBody
```

- [ ] **Step 4: Run mypy and full suite**

```bash
env/bin/mypy optimizerapi/optimizer.py 2>&1 | tail -10
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: mypy may surface in-body issues; ignore them for now (they belong to Phase 4). The `def`-line types are what matter here. Pytest is unchanged.

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/optimizer.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
types: annotate optimizer.run and process_result signatures

Body-level annotations and helper functions land in Phase 4 along with
the structural refactor that splits process_result into focused units.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Document the type-check command

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add a line to `AGENTS.md`**

Open `AGENTS.md`. After the line:
```
- Lint locally with `flake8 . --max-line-length=127` (matches CI workflow).
```

Insert (alphabetical placement):
```
- Type-check locally with `mypy optimizerapi` (matches CI workflow); see `[tool.mypy]` in `pyproject.toml`.
```

- [ ] **Step 2: Add the same to `CLAUDE.md`**

In the `## Commands` block of `CLAUDE.md`, after the flake8 line, add:

```bash
# Type-check (matches CI)
mypy optimizerapi
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md CLAUDE.md
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
docs: document mypy in dev-loop instructions

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Acceptance criteria

- `optimizerapi/types.py` exists and exports the documented TypedDicts.
- `tests/test_types.py` passes (3 sanity-check assertions).
- `mypy optimizerapi` runs (it does not need to be error-free yet; Phase 4 cleans up the body-level issues).
- Public function signatures in `pickled_state.py`, `optimizer_handler.py`, and `optimizer.py` have types referencing the new module.
- Full pytest run is green.
- `AGENTS.md` and `CLAUDE.md` mention `mypy optimizerapi`.

## Out of scope

- Annotating every helper inside `optimizer.py` (Phase 4).
- Making `mypy strict = true` (deferred until after Phase 4).
- Type-checking the test suite (low ROI; tests are dynamic by nature).
- Switching to `pyright` (mypy chosen because it's the most familiar tooling).
