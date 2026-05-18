# Pareto `extras` Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock in the contract for `extras.selectedPoint` / `extras.pickled` / `extras.includeModel` such that `pickled` is a verified cache hint (never authoritative) and a no-`pickled` round-trip produces equivalent output to a `pickled` round-trip.

**Architecture:** Pull pickle pack/unpack logic into a new `optimizerapi/pickled_state.py` module that owns the request-fingerprint computation, payload structure (`{"fingerprint", "result", "next", "optimizer"}`), and the four-stage validation flow (decrypt → structural → fingerprint → fast-path). `optimizer.py:run` delegates to it. A `result.extras.pickledUsed` boolean is added so the UI can observe fast-path usage. PNG + `selectedPoint` and `includeModel=false` + `pickled` log warnings but otherwise do exactly what the request asked for.

**Tech Stack:** Python 3.9+, pytest, Connexion/Flask, Fernet (already wired via `optimizerapi/securepickle`), ProcessOptimizer.

**Spec:** [`docs/superpowers/specs/2026-05-18-pareto-extras-redesign-design.md`](../specs/2026-05-18-pareto-extras-redesign-design.md)

---

## File Map

- **Create:** `optimizerapi/pickled_state.py` — fingerprint + pack/unpack helpers; sole owner of payload structure and fall-through logging.
- **Create:** `tests/test_pickled_state.py` — unit tests for fingerprint determinism, round-trip, and each fall-through reason.
- **Modify:** `optimizerapi/optimizer.py` — replace the inline unpickle block in `run`, thread fingerprint + `pickled_used` through to `process_result`, add the two new warning logs.
- **Modify:** `optimizerapi/openapi/specification.yml` — tighten descriptions for `extras.pickled` and `extras.selectedPoint`; add `result.extras.pickledUsed`.
- **Modify:** `tests/test_optimizer.py` — add the binding equivalence test, fingerprint-mismatch test, PNG+selectedPoint warning test, includeModel+pickled warning test, and pickledUsed round-trip test; refresh `test_old_format_pickled_falls_back` and `test_pickled_response_is_dict_format` for the new payload shape.

---

### Task 1: Fingerprint helper in new module

**Files:**
- Create: `optimizerapi/pickled_state.py`
- Test: `tests/test_pickled_state.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_pickled_state.py` with the following content:

```python
"""Tests for pickled_state: fingerprint + pack/unpack helpers."""

from optimizerapi.pickled_state import compute_fingerprint


SAMPLE_DATA = [
    {"xi": [651, 56, 722, "Ræv"], "yi": [1]},
    {"xi": [651, 42, 722, "Ræv"], "yi": [0.2]},
]

SAMPLE_CONFIG = {
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
}


def test_fingerprint_is_deterministic():
    fp1 = compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG)
    fp2 = compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG)
    assert fp1 == fp2
    assert isinstance(fp1, str)
    assert len(fp1) == 64  # sha256 hex


def test_fingerprint_is_independent_of_dict_key_order():
    reordered_config = {
        "space": SAMPLE_CONFIG["space"],
        "xi": SAMPLE_CONFIG["xi"],
        "kappa": SAMPLE_CONFIG["kappa"],
        "initialPoints": SAMPLE_CONFIG["initialPoints"],
        "acqFunc": SAMPLE_CONFIG["acqFunc"],
        "baseEstimator": SAMPLE_CONFIG["baseEstimator"],
    }
    assert compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG) == compute_fingerprint(
        SAMPLE_DATA, reordered_config
    )


def test_fingerprint_changes_when_data_changes():
    other_data = SAMPLE_DATA + [{"xi": [100, 100, 100, "Mus"], "yi": [0.5]}]
    assert compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG) != compute_fingerprint(
        other_data, SAMPLE_CONFIG
    )


def test_fingerprint_changes_when_config_changes():
    other_config = dict(SAMPLE_CONFIG, kappa=2.0)
    assert compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG) != compute_fingerprint(
        SAMPLE_DATA, other_config
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pickled_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'optimizerapi.pickled_state'`.

- [ ] **Step 3: Write minimal implementation**

Create `optimizerapi/pickled_state.py` with:

```python
"""Pickled-state cache: fingerprint a request, pack/unpack pickled payloads.

The fingerprint binds a pickled blob to the request that produced it, so a
client that sends a stale pickled along with newer data gets a clean fall-
through to a full run instead of silently buggy reuse.
"""

import hashlib
import json


def compute_fingerprint(data, optimizer_config):
    """Return sha256 hex of the canonical-JSON of (data, optimizerConfig).

    Canonical JSON: sorted keys, no whitespace. Numbers are emitted as Python's
    default JSON representation, which is stable for the integer / float values
    that flow through the API.
    """
    payload = {"data": data, "optimizerConfig": optimizer_config}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pickled_state.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/pickled_state.py tests/test_pickled_state.py
git commit -m "feat: add request fingerprint helper for pickled cache"
```

---

### Task 2: Pack + unpack with fall-through logging

**Files:**
- Modify: `optimizerapi/pickled_state.py`
- Modify: `tests/test_pickled_state.py`

- [ ] **Step 1: Write the failing tests (extend `tests/test_pickled_state.py`)**

Append to `tests/test_pickled_state.py`:

```python
import logging

from optimizerapi.pickled_state import pack, unpack_if_valid
from optimizerapi.securepickle import get_crypto, pickleToString


def _crypto():
    return get_crypto()


def test_pack_unpack_round_trip():
    crypto = _crypto()
    fingerprint = compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG)
    blob = pack(result="result-sentinel", next_points=["next-sentinel"],
                optimizer="opt-sentinel", fingerprint=fingerprint, crypto=crypto)
    assert isinstance(blob, str) and len(blob) > 0

    payload = unpack_if_valid(blob, expected_fingerprint=fingerprint, crypto=crypto)
    assert payload is not None
    assert payload["result"] == "result-sentinel"
    assert payload["next"] == ["next-sentinel"]
    assert payload["optimizer"] == "opt-sentinel"
    assert payload["fingerprint"] == fingerprint


def test_unpack_returns_none_on_fingerprint_mismatch(caplog):
    crypto = _crypto()
    fingerprint = compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG)
    blob = pack(result="r", next_points=[], optimizer="o",
                fingerprint=fingerprint, crypto=crypto)

    with caplog.at_level(logging.WARNING, logger="optimizerapi.pickled_state"):
        result = unpack_if_valid(blob, expected_fingerprint="0" * 64, crypto=crypto)
    assert result is None
    assert any("fingerprint_mismatch" in record.message for record in caplog.records)


def test_unpack_returns_none_on_decrypt_failure(caplog):
    crypto = _crypto()
    with caplog.at_level(logging.WARNING, logger="optimizerapi.pickled_state"):
        result = unpack_if_valid("not-a-valid-blob", expected_fingerprint="x" * 64,
                                 crypto=crypto)
    assert result is None
    assert any("decrypt_failed" in record.message for record in caplog.records)


def test_unpack_returns_none_on_bad_structure(caplog):
    crypto = _crypto()
    # Encrypt a non-dict payload using the same machinery.
    bogus_blob = pickleToString(["not", "a", "dict"], crypto)

    with caplog.at_level(logging.WARNING, logger="optimizerapi.pickled_state"):
        result = unpack_if_valid(bogus_blob, expected_fingerprint="x" * 64,
                                 crypto=crypto)
    assert result is None
    assert any("bad_structure" in record.message for record in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pickled_state.py -v`
Expected: FAIL with `ImportError: cannot import name 'pack' from 'optimizerapi.pickled_state'`.

- [ ] **Step 3: Implement `pack` and `unpack_if_valid`**

Append to `optimizerapi/pickled_state.py`:

```python
import logging

from .securepickle import pickleToString, unpickleFromString

_LOG = logging.getLogger(__name__)

_REQUIRED_KEYS = ("fingerprint", "result", "next", "optimizer")


def pack(*, result, next_points, optimizer, fingerprint, crypto):
    """Encrypt a pickled cache payload for the given fingerprint."""
    payload = {
        "fingerprint": fingerprint,
        "result": result,
        "next": next_points,
        "optimizer": optimizer,
    }
    return pickleToString(payload, crypto)


def unpack_if_valid(blob, *, expected_fingerprint, crypto):
    """Decrypt and validate a pickled cache payload.

    Returns the payload dict on success, or None if anything is off. Any
    failure is logged once at WARNING with a reason tag in the message:
    decrypt_failed | bad_structure | fingerprint_mismatch.
    """
    if not blob:
        return None
    try:
        payload = unpickleFromString(blob, crypto)
    except Exception:
        _LOG.warning("pickled cache ignored: decrypt_failed")
        return None
    if not isinstance(payload, dict) or not all(k in payload for k in _REQUIRED_KEYS):
        _LOG.warning("pickled cache ignored: bad_structure")
        return None
    if payload["fingerprint"] != expected_fingerprint:
        _LOG.warning("pickled cache ignored: fingerprint_mismatch")
        return None
    return payload
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pickled_state.py -v`
Expected: PASS, 8 tests total (4 from Task 1 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/pickled_state.py tests/test_pickled_state.py
git commit -m "feat: add pack/unpack_if_valid for pickled cache with fall-through logging"
```

---

### Task 3: Wire `pickled_state` into `optimizer.py`

This task replaces the inline unpickle block at `optimizer.py:105-129` with a single call to `unpack_if_valid`, threads a `pickled_used` flag through `process_result`, and switches the repack at `optimizer.py:395` to use `pack`. The `pickled_used` flag surfaces as `result.extras.pickledUsed`.

**Files:**
- Modify: `optimizerapi/optimizer.py:32` (imports)
- Modify: `optimizerapi/optimizer.py:68-167` (`run` function)
- Modify: `optimizerapi/optimizer.py:177-415` (`process_result` function)
- Modify: `tests/test_optimizer.py` (add the round-trip assertion test described below)

- [ ] **Step 1: Write the failing test (`pickledUsed` round-trip)**

Add this test to `tests/test_optimizer.py`, after `test_pickled_round_trip`:

```python
def test_pickled_used_flag_round_trip():
    """First run has pickledUsed=False; second run with returned pickled has pickledUsed=True."""
    first = optimizer.run(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true"},
    })
    assert first["result"]["extras"]["pickledUsed"] is False
    pickled_value = first["result"]["pickled"]
    assert len(pickled_value) > 0

    second = optimizer.run(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true", "pickled": pickled_value},
    })
    assert second["result"]["extras"]["pickledUsed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_optimizer.py::test_pickled_used_flag_round_trip -v`
Expected: FAIL — `pickledUsed` key not in `result["result"]["extras"]`.

- [ ] **Step 3: Update the imports in `optimizer.py`**

Replace the line:

```python
from .securepickle import get_crypto, pickleToString, unpickleFromString
```

with:

```python
from .securepickle import get_crypto
from .pickled_state import compute_fingerprint, pack, unpack_if_valid
```

- [ ] **Step 4: Replace the inline unpickle block in `run`**

Inside `run`, replace the block currently at lines 105–129:

```python
    # Pickled consumption: attempt to skip training if extras.pickled is provided
    pickled_input = extras.get("pickled", "")
    if pickled_input:
        try:
            unpickled = unpickleFromString(pickled_input, get_crypto())
            if isinstance(unpickled, dict) and "result" in unpickled and "optimizer" in unpickled:
                result = unpickled["result"]
                optimizer = unpickled["optimizer"]
                response = process_result(result, optimizer, dimensions, cfg, extras, data, space)
                response["result"]["extras"]["parameters"] = {
                    "dimensions": dimensions,
                    "space": space,
                    "hyperparams": hyperparams,
                    "Xi": Xi,
                    "Yi": Yi,
                    "extras": extras,
                }
                return json.loads(json_tricks.dumps(response))
            else:
                pickled_input = ""
        except Exception:
            logging.getLogger(__name__).warning(
                "Failed to unpickle extras.pickled, falling back to full run"
            )
            pickled_input = ""
```

with:

```python
    request_fingerprint = compute_fingerprint(body["data"], cfg)
    pickled_input = extras.get("pickled", "")
    cached = unpack_if_valid(
        pickled_input, expected_fingerprint=request_fingerprint, crypto=get_crypto()
    ) if pickled_input else None

    if cached is not None:
        result = cached["result"]
        optimizer = cached["optimizer"]
        response = process_result(
            result, optimizer, dimensions, cfg, extras, data, space,
            request_fingerprint=request_fingerprint, pickled_used=True,
        )
        response["result"]["extras"]["parameters"] = {
            "dimensions": dimensions,
            "space": space,
            "hyperparams": hyperparams,
            "Xi": Xi,
            "Yi": Yi,
            "extras": extras,
        }
        return json.loads(json_tricks.dumps(response))
```

- [ ] **Step 5: Update the full-run path in `run` to pass the new kwargs**

Find the existing call at `optimizer.py:154`:

```python
    response = process_result(result, optimizer, dimensions, cfg, extras, data, space)
```

Replace with:

```python
    response = process_result(
        result, optimizer, dimensions, cfg, extras, data, space,
        request_fingerprint=request_fingerprint, pickled_used=False,
    )
```

- [ ] **Step 6: Update `process_result` signature and body**

Change the signature from:

```python
def process_result(result, optimizer, dimensions, cfg, extras, data, space):
```

to:

```python
def process_result(result, optimizer, dimensions, cfg, extras, data, space,
                   *, request_fingerprint, pickled_used):
```

Inside `process_result`, locate the existing line:

```python
    result_details = {"next": [], "models": [], "pickled": "", "extras": {}}
```

Immediately after the existing `add_version_info(result_details["extras"])` call near the end of `process_result`, set the flag:

```python
    result_details["extras"]["pickledUsed"] = pickled_used
```

Then replace the existing repack block:

```python
    if pickle_model:
        result_details["pickled"] = pickleToString(
            {"result": result, "next": result_details["next"], "optimizer": optimizer},
            get_crypto()
        )
```

with:

```python
    if pickle_model:
        result_details["pickled"] = pack(
            result=result,
            next_points=result_details["next"],
            optimizer=optimizer,
            fingerprint=request_fingerprint,
            crypto=get_crypto(),
        )
```

- [ ] **Step 7: Run the new test to verify it passes**

Run: `python -m pytest tests/test_optimizer.py::test_pickled_used_flag_round_trip -v`
Expected: PASS.

- [ ] **Step 8: Run the existing pickled tests to confirm no regression**

Run:
```bash
python -m pytest tests/test_optimizer.py -k "pickled or selectedPoint" -v
```
Expected: All targeted tests PASS. (One pre-existing unrelated failure `test_multi_objective_json_single_plots` is out of scope and not in this filter.)

- [ ] **Step 9: Commit**

```bash
git add optimizerapi/optimizer.py tests/test_optimizer.py
git commit -m "feat: delegate pickled cache to pickled_state and surface pickledUsed"
```

---

### Task 4: Binding equivalence test

This is the test that enforces the north-star principle in §2 of the spec: the same request with and without `pickled` produces identical single-plot output.

**Files:**
- Modify: `tests/test_optimizer.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_optimizer.py` (placement: near the other multi-objective `selectedPoint` tests):

```python
def test_equivalence_with_and_without_pickled_multi_objective():
    """Same selectedPoint, same data: pickled vs no-pickled produce identical single plots."""
    base_body = {
        "data": sampleMultiObjective5DimData,
        "optimizerConfig": sampleMultiObjective5DimConfig,
        "extras": {
            "graphs": ["single", "pareto"],
            "graphFormat": "json",
            "selectedPoint": [50, 833, 150, 60, "Whipped cream"],
            "includeModel": "true",
        },
    }

    # Seed: one full run to capture pickled.
    seed = optimizer.run(body=copy.deepcopy({
        **base_body,
        "extras": {**base_body["extras"], "selectedPoint": None},
    }))
    pickled_value = seed["result"]["pickled"]
    assert len(pickled_value) > 0

    # Run A: no pickled (full retrain), with selectedPoint.
    body_no_pickle = copy.deepcopy(base_body)
    result_no_pickle = optimizer.run(body=body_no_pickle)

    # Run B: same request + pickled.
    body_with_pickle = copy.deepcopy(base_body)
    body_with_pickle["extras"]["pickled"] = pickled_value
    result_with_pickle = optimizer.run(body=body_with_pickle)

    # Sanity: fast path actually engaged.
    assert result_with_pickle["result"]["extras"]["pickledUsed"] is True
    assert result_no_pickle["result"]["extras"]["pickledUsed"] is False

    # Compare every plot entry except the pickled string itself (which is
    # not in plots) — identical plot ids and identical plot bodies.
    plots_no_pickle = {p["id"]: p["plot"] for p in result_no_pickle["plots"]}
    plots_with_pickle = {p["id"]: p["plot"] for p in result_with_pickle["plots"]}
    assert set(plots_no_pickle) == set(plots_with_pickle)
    for plot_id in plots_no_pickle:
        assert plots_no_pickle[plot_id] == plots_with_pickle[plot_id], (
            f"divergence on plot {plot_id}"
        )
```

If `sampleMultiObjective5DimData` and `sampleMultiObjective5DimConfig` are not defined as module-level fixtures yet, define them near the top of the test file (mirroring the values from `scripts/sample-multi.curl`):

```python
sampleMultiObjective5DimData = [
    {"xi": [16.7, 500, 250, 20, "None"], "yi": [-2, -17]},
    {"xi": [50, 833, 150, 60, "Whipped cream"], "yi": [-3, -6]},
    {"xi": [58.3, 22, 85, 6, "Frosting"], "yi": [-6, -25]},
]

sampleMultiObjective5DimConfig = {
    "baseEstimator": "GP",
    "acqFunc": "EI",
    "initialPoints": 3,
    "kappa": 1.96,
    "xi": 2,
    "space": [
        {"type": "continuous", "name": "Sugar", "from": 0, "to": 100},
        {"type": "continuous", "name": "Flour", "from": 0, "to": 1000},
        {"type": "discrete", "name": "Temperature", "from": 0, "to": 300},
        {"type": "discrete", "name": "Time", "from": 0, "to": 120},
        {"type": "category", "name": "Finish", "categories": ["None", "Frosting", "Whipped cream"]},
    ],
    "constraints": [],
}
```

(Check first whether equivalents already exist further down `tests/test_optimizer.py` — search for `sampleMultiObjective5Dim`. If they do, reuse them and skip the redefinition.)

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_optimizer.py::test_equivalence_with_and_without_pickled_multi_objective -v`
Expected: PASS. If it FAILS with a plot divergence, that is a real regression — investigate before continuing. Likely culprits: the fast path silently skipping `selectedPoint`, or `_get_brownie_bee_1d_plot_safe` being called with different state on the two paths.

- [ ] **Step 3: Commit**

```bash
git add tests/test_optimizer.py
git commit -m "test: assert equivalence of pickled and full-run plots"
```

---

### Task 5: Fingerprint-mismatch test

**Files:**
- Modify: `tests/test_optimizer.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_optimizer.py`:

```python
def test_pickled_fingerprint_mismatch_falls_through(caplog):
    """A pickled produced from one data set is ignored when data changes."""
    import logging as _logging

    seed = optimizer.run(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true"},
    })
    pickled_value = seed["result"]["pickled"]
    assert len(pickled_value) > 0

    altered_data = sampleData + [{"xi": [100, 100, 100, "Mus"], "yi": [0.5]}]

    with caplog.at_level(_logging.WARNING, logger="optimizerapi.pickled_state"):
        result = optimizer.run(body={
            "data": altered_data,
            "optimizerConfig": sampleConfig,
            "extras": {"includeModel": "true", "pickled": pickled_value},
        })

    assert result["result"]["extras"]["pickledUsed"] is False
    assert any("fingerprint_mismatch" in r.message for r in caplog.records)
    # Response still valid — server fell through to a full run.
    assert "next" in result["result"]
    assert len(result["result"]["next"]) > 0
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_optimizer.py::test_pickled_fingerprint_mismatch_falls_through -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_optimizer.py
git commit -m "test: fingerprint mismatch falls through with warning"
```

---

### Task 6: Warn when PNG + `selectedPoint` are combined

**Files:**
- Modify: `optimizerapi/optimizer.py` (`process_result`)
- Modify: `tests/test_optimizer.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_optimizer.py`:

```python
def test_selectedPoint_with_png_logs_warning_and_is_ignored(caplog):
    import logging as _logging

    with caplog.at_level(_logging.WARNING, logger="optimizerapi.optimizer"):
        result = optimizer.run(body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {
                "graphFormat": "png",
                "selectedPoint": [651, 56, 722, "Ræv"],
                "includeModel": "false",
            },
        })

    assert any("selectedPoint ignored on png path" in r.message for r in caplog.records)
    # No crash, response is valid.
    assert "plots" in result
    assert "next" in result["result"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_optimizer.py::test_selectedPoint_with_png_logs_warning_and_is_ignored -v`
Expected: FAIL — warning not emitted.

- [ ] **Step 3: Add the warning in `process_result`**

In `optimizerapi/optimizer.py`, inside `process_result`, right after the existing lines that read `graph_format` and `selected_point`:

```python
    graph_format = extras.get("graphFormat", "png")
    # ...
    pickle_model = json.loads(extras.get("includeModel", "true").lower())
    selected_point = extras.get("selectedPoint")
```

append:

```python
    if selected_point is not None and graph_format != "json":
        logging.getLogger(__name__).warning(
            "selectedPoint ignored on png path (graphFormat=%s)", graph_format
        )
```

(No other behavior change — the PNG branch already never reads `selected_point`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_optimizer.py::test_selectedPoint_with_png_logs_warning_and_is_ignored -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/optimizer.py tests/test_optimizer.py
git commit -m "feat: warn when selectedPoint is sent with png graphFormat"
```

---

### Task 7: Warn when `includeModel=false` + `pickled` are combined

**Files:**
- Modify: `optimizerapi/optimizer.py` (`run`)
- Modify: `tests/test_optimizer.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_optimizer.py`:

```python
def test_includeModel_false_with_pickled_logs_chain_break_warning(caplog):
    import logging as _logging

    seed = optimizer.run(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true"},
    })
    pickled_value = seed["result"]["pickled"]

    with caplog.at_level(_logging.WARNING, logger="optimizerapi.optimizer"):
        second = optimizer.run(body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"pickled": pickled_value, "includeModel": "false"},
        })

    assert any("includeModel=false with extras.pickled" in r.message for r in caplog.records)
    # Contract preserved: empty pickled returned.
    assert second["result"]["pickled"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_optimizer.py::test_includeModel_false_with_pickled_logs_chain_break_warning -v`
Expected: FAIL.

- [ ] **Step 3: Add the warning in `run`**

In `optimizerapi/optimizer.py`, inside `run`, after the `extras` dict is read and after `pickled_input` is computed (Task 3 put `pickled_input = extras.get("pickled", "")` right above the `cached = ...` line), add:

```python
    if pickled_input:
        include_model_str = str(extras.get("includeModel", "true")).lower()
        if include_model_str == "false":
            logging.getLogger(__name__).warning(
                "includeModel=false with extras.pickled — next call will pay the full cost"
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_optimizer.py::test_includeModel_false_with_pickled_logs_chain_break_warning -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/optimizer.py tests/test_optimizer.py
git commit -m "feat: warn when includeModel=false drops a returnable pickled cache"
```

---

### Task 8: OpenAPI spec updates

**Files:**
- Modify: `optimizerapi/openapi/specification.yml`

- [ ] **Step 1: Tighten `extras.pickled` description**

In `specification.yml`, find:

```yaml
            pickled:
              description: Previously-pickled model state to skip expensive GP model retraining
              type: string
```

Replace the description with:

```yaml
            pickled:
              description: >
                Opaque cache hint produced by a previous response. The server
                validates it matches the current data / optimizerConfig; on
                mismatch it is ignored and a full run is performed.
              type: string
```

- [ ] **Step 2: Tighten `extras.selectedPoint` description**

Find:

```yaml
            selectedPoint:
              description: Override the highlight point in JSON single plots with explicit X-space coordinates
              type: array
```

Replace the description with:

```yaml
            selectedPoint:
              description: >
                Override the highlight point in single plots with explicit
                X-space coordinates. Honored only when graphFormat is "json";
                ignored on the PNG path.
              type: array
```

- [ ] **Step 3: Add `pickledUsed` to the response result schema**

Locate the `result` schema (around line 264) and find the inner `result:` block:

```yaml
        result:
          type: object
          properties:
            expected_minimum:
              ...
            pickled:
              type: string
            next:
              ...
            models:
              ...
            extras:
              type: object
```

Change the trailing `extras:` block to:

```yaml
            extras:
              type: object
              properties:
                pickledUsed:
                  description: True iff the server reused the pickled cache hint for this response.
                  type: boolean
```

- [ ] **Step 4: Confirm OpenAPI still parses**

Run: `python -m optimizerapi.server` and confirm it boots without YAML/OpenAPI errors. Hit `Ctrl-C` once the line `Serving on http://...` (or the Connexion startup line) appears. Then close.

Alternative non-interactive check:

```bash
python -c "import yaml; yaml.safe_load(open('optimizerapi/openapi/specification.yml'))"
```

Expected: no traceback.

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/openapi/specification.yml
git commit -m "docs(openapi): tighten descriptions for pickled/selectedPoint, add pickledUsed"
```

---

### Task 9: Refresh legacy pickled tests

The payload structure is now `{"fingerprint", "result", "next", "optimizer"}`. Two existing tests need their expectations refreshed.

**Files:**
- Modify: `tests/test_optimizer.py`

- [ ] **Step 1: Update `test_old_format_pickled_falls_back`**

The current test (at the location shown by `grep -n "test_old_format_pickled_falls_back" tests/test_optimizer.py`) constructs an old-format list and expects fall-through. Under the new code path this now flows through `bad_structure`. The functional assertion still holds; add an explicit warning assertion and a `pickledUsed=False` assertion to make it precise.

Replace the test body with:

```python
def test_old_format_pickled_falls_back(caplog):
    """A pickled payload that decrypts but isn't the new dict shape falls through."""
    import logging as _logging

    old_format_data = ["some", "old", "data"]
    old_pickled = pickleToString(old_format_data, get_crypto())

    with caplog.at_level(_logging.WARNING, logger="optimizerapi.pickled_state"):
        result = optimizer.run(body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"pickled": old_pickled, "includeModel": "false"},
        })

    assert "result" in result
    assert len(result["result"]["next"]) > 0
    assert result["result"]["extras"]["pickledUsed"] is False
    assert any("bad_structure" in r.message for r in caplog.records)
```

- [ ] **Step 2: Update `test_pickled_response_is_dict_format`**

The existing test asserts the response pickled is a dict with `result`, `next`, `optimizer`. Add `fingerprint` to the assertions so the new contract is locked.

Locate the test and replace its tail-end assertions (after `unpickled = unpickleFromString(pickled_value, get_crypto())`) with:

```python
    assert isinstance(unpickled, dict), f"Expected dict, got {type(unpickled)}"
    assert set(unpickled.keys()) >= {"fingerprint", "result", "next", "optimizer"}
    assert isinstance(unpickled["fingerprint"], str) and len(unpickled["fingerprint"]) == 64
```

- [ ] **Step 3: Update `test_invalid_pickled_falls_back`**

This test sends raw garbage and expects fall-through. Add `pickledUsed` and warning assertions for symmetry:

```python
def test_invalid_pickled_falls_back(caplog):
    """An undecodable pickled string falls through to a full run."""
    import logging as _logging

    with caplog.at_level(_logging.WARNING, logger="optimizerapi.pickled_state"):
        result = optimizer.run(body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"pickled": "this_is_not_valid_pickled_data_at_all", "includeModel": "false"},
        })

    assert "result" in result
    assert len(result["result"]["next"]) > 0
    assert result["result"]["extras"]["pickledUsed"] is False
    assert any("decrypt_failed" in r.message for r in caplog.records)
```

- [ ] **Step 4: Run the three updated tests**

Run:
```bash
python -m pytest tests/test_optimizer.py::test_old_format_pickled_falls_back \
                 tests/test_optimizer.py::test_pickled_response_is_dict_format \
                 tests/test_optimizer.py::test_invalid_pickled_falls_back -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_optimizer.py
git commit -m "test: refresh legacy pickled tests for new payload shape and warnings"
```

---

### Task 10: Full suite + lint

**Files:** none new.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest`
Expected: All tests pass except the pre-existing `test_multi_objective_json_single_plots` (out of scope per the spec). If anything else fails, stop and investigate; do not paper over by adjusting tests.

- [ ] **Step 2: Run flake8**

Run: `flake8 . --max-line-length=127`
Expected: no warnings.

- [ ] **Step 3: Smoke-check the server boots**

Run: `python -m optimizerapi.server` in one shell; wait for the startup line; then `Ctrl-C`. Confirms the OpenAPI parses end-to-end and there are no import errors from the new module.

- [ ] **Step 4: Final commit (if any cleanup landed during steps 1–3)**

If steps 1–3 surfaced fixes:

```bash
git add -A
git commit -m "chore: final cleanup after pareto extras redesign"
```

Otherwise skip.

---

## Out of scope (do not implement here)

- Server-side session cache with short-ID `extras.pickleHandle`.
- Migrating `includeModel` to a real boolean.
- A structured `pickledRejectedReason` in the response.
- Fixing `test_multi_objective_json_single_plots`.
- Modifications to ProcessOptimizer source or `_get_brownie_bee_1d_plot_safe`.
