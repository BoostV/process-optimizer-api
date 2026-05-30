# Audit Phase 4 — Refactor `process_result`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `optimizer.py:process_result` (~250 lines, 4-way branching) into focused helpers. Pull plot-rendering code into a new `plot_emitters.py` module. Eliminate the three near-duplicate JSON single-plot loops via a single helper that takes a `prefix` argument. Behavior is unchanged — the equivalence test from the pareto redesign is the binding correctness gate.

**Architecture:** Two refactors stacked:

1. **Internal extraction in `optimizer.py`:** small helpers (`_parse_extras`, `_compute_next_experiments`, `_flatten_expected_minima`, `_set_expected_minimum`) live in the same file as private functions.
2. **External extraction:** the plot-emission code moves to `optimizerapi/plot_emitters.py`. The three duplicated single-plot loops collapse into `emit_json_single_plots(plots, model, *, prefix, selected_point)`. PNG emission moves to `emit_png_plots`.

After both steps, `process_result` becomes a ~60-line dispatcher.

**Tech Stack:** Python 3.13, mypy from Phase 3 catches refactor mistakes, the equivalence test (`test_equivalence_with_and_without_pickled_multi_objective`) catches behavior drift.

**Audit reference:** §1 of the audit. The `process_result` function is the single largest source of structural debt; the refactor pays back the typing investment from Phase 3.

**Prereq:** Phases 1, 2, 3 complete. `mypy optimizerapi/optimizer.py` runs (errors permitted; this phase reduces them).

---

## File Map

- **Modify:** `optimizerapi/optimizer.py` — extract helpers, shrink `process_result`.
- **Create:** `optimizerapi/plot_emitters.py` — `emit_png_plots`, `emit_json_single_plots`, `emit_pareto_data`.
- **Create:** `tests/test_plot_emitters.py` — focused unit tests for the new module.

### Behavioral safety net

Every task ends with `python -m pytest 2>&1 | tail -3`. The CRITICAL invariant is that `test_equivalence_with_and_without_pickled_multi_objective` passes after every commit — that's the binding contract from the pareto redesign. If it fails at any point, STOP and report BLOCKED with the divergence details. Do NOT modify the test to make it pass.

---

### Task 1: Extract `_parse_extras` and the PNG-warning move

The top of `process_result` reads extras keys and emits the PNG + selectedPoint warning. Pull both into a private helper that returns a small dataclass.

**Files:**
- Modify: `optimizerapi/optimizer.py`

- [ ] **Step 1: Add the dataclass and helper near the top of `optimizer.py`**

Add at the top of the file (after the existing imports + version-info helpers, but before `process_result`):

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class _ParsedExtras:
    graph_format: str
    max_quality: int
    graphs_to_return: list[str]
    objective_pars: str
    include_model: bool
    selected_point: list[str | float] | None
    experiment_suggestion_count: int


def _parse_bool(value: object, default: bool = True) -> bool:
    """Coerce extras' stringly-typed boolean fields.

    Accepts the literals "true" / "false" (case-insensitive), real bools,
    and JSON-style ``true``/``false``. Anything else falls back to *default*.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    return default


def _parse_extras(extras: "Extras", logger: "logging.Logger") -> _ParsedExtras:
    """Read the request ``extras`` block into a typed view.

    Emits the PNG + selectedPoint warning here so callers don't need to
    duplicate the check.
    """
    graph_format = extras.get("graphFormat", "png")
    selected_point = extras.get("selectedPoint")
    if selected_point is not None and graph_format != "json":
        logger.warning(
            "selectedPoint ignored on png path (graphFormat=%s)", graph_format
        )
    return _ParsedExtras(
        graph_format=graph_format,
        max_quality=int(extras.get("maxQuality", 5)),
        graphs_to_return=extras.get(
            "graphs", ["objective", "convergence", "pareto", "single"]
        ),
        objective_pars=extras.get("objectivePars", "result"),
        include_model=_parse_bool(extras.get("includeModel", "true")),
        selected_point=selected_point,
        experiment_suggestion_count=int(extras.get("experimentSuggestionCount", 1)),
    )
```

- [ ] **Step 2: Use it inside `process_result`**

Inside `process_result`, replace the block that currently reads the extras keys:

```python
    graph_format = extras.get("graphFormat", "png")
    max_quality = int(extras.get("maxQuality", "5"))
    graphs_to_return = extras.get(
        "graphs", ["objective", "convergence", "pareto", "single"]
    )

    objective_pars = extras.get("objectivePars", "result")

    pickle_model = json.loads(extras.get("includeModel", "true").lower())
    selected_point = extras.get("selectedPoint")
    if selected_point is not None and graph_format != "json":
        logging.getLogger(__name__).warning(
            "selectedPoint ignored on png path (graphFormat=%s)", graph_format
        )

    experiment_suggestion_count = 1
    if "experimentSuggestionCount" in extras:
        experiment_suggestion_count = extras["experimentSuggestionCount"]
```

with:

```python
    parsed = _parse_extras(extras, logging.getLogger(__name__))
    graph_format = parsed.graph_format
    max_quality = parsed.max_quality
    graphs_to_return = parsed.graphs_to_return
    objective_pars = parsed.objective_pars
    pickle_model = parsed.include_model
    selected_point = parsed.selected_point
    experiment_suggestion_count = parsed.experiment_suggestion_count
```

The reassignment to local names preserves the existing body's references — minimising the diff and keeping the refactor incremental. Future tasks can drop the local aliases as the body shrinks.

- [ ] **Step 3: Run the equivalence test**

```bash
env/bin/python -m pytest tests/test_optimizer.py::test_equivalence_with_and_without_pickled_multi_objective -v
```
Expected: PASS.

- [ ] **Step 4: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: unchanged from end of Phase 3.

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/optimizer.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
refactor(optimizer): extract _parse_extras + _parse_bool helper

Single source of truth for extras parsing (including the PNG+selectedPoint
warning). The local aliases preserve the rest of the function body for now;
subsequent tasks drop them as the body shrinks.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Extract `_compute_next_experiments` and `_flatten_expected_minima`

These two are small but ugly. Pulling them out reduces noise in `process_result`.

**Files:**
- Modify: `optimizerapi/optimizer.py`

- [ ] **Step 1: Add the helpers**

Below `_parse_extras`, add:

```python
def _compute_next_experiments(
    optimizer: object,
    cfg: "OptimizerConfig",
    n_points: int,
) -> list[list[str | float]]:
    """Ask the optimizer for the next N experiments, normalising the shape.

    ``optimizer.ask`` can return either a single experiment (flat list) or
    a list of experiments. We always return a list of lists.
    """
    constraints = cfg.get("constraints", [])
    if constraints:
        next_exp = optimizer.ask(n_points=n_points, strategy="cl_min")
    else:
        next_exp = optimizer.ask(n_points=n_points)
    if next_exp and not any(isinstance(x, list) for x in next_exp):
        next_exp = [next_exp]
    return round_to_length_scales(next_exp, optimizer.space)


def _flatten_expected_minima(models: list[dict]) -> None:
    """In-place flatten of nested ``expected_minimum`` entries on each model.

    The pre-flatten shape from ``process_model`` can be a list of mixed
    scalars and lists; the response contract is a single flat list inside
    a one-element outer list. This function normalises that.
    """
    for model in models:
        flat = []
        for x in model["expected_minimum"]:
            if isinstance(x, list):
                flat.extend(x)
            else:
                flat.append(x)
        model["expected_minimum"] = [flat]
```

- [ ] **Step 2: Use them inside `process_result`**

Replace the existing next-experiment block:

```python
    if "constraints" in cfg and len(cfg["constraints"]) > 0:
        next_exp = optimizer.ask(
            n_points=experiment_suggestion_count, strategy="cl_min"
        )
    else:
        next_exp = optimizer.ask(n_points=experiment_suggestion_count)
    if len(next_exp) > 0 and not any(isinstance(x, list) for x in next_exp):
        next_exp = [next_exp]
    result_details["next"] = round_to_length_scales(next_exp, optimizer.space)
```

with:

```python
    result_details["next"] = _compute_next_experiments(
        optimizer, cfg, experiment_suggestion_count
    )
```

Replace the trailing flatten block (currently 3 levels of nested list comprehension):

```python
    org_models = response["result"]["models"]
    for model in org_models:
        # Flatten expected minimum entries
        model["expected_minimum"] = [
            [
                item
                for sublist in [
                    x if isinstance(x, list) else [x] for x in model["expected_minimum"]
                ]
                for item in sublist
            ]
        ]
    return response
```

with:

```python
    _flatten_expected_minima(response["result"]["models"])
    return response
```

- [ ] **Step 3: Run the equivalence test + full suite**

```bash
env/bin/python -m pytest tests/test_optimizer.py::test_equivalence_with_and_without_pickled_multi_objective -v
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: equivalence PASS; full suite unchanged.

- [ ] **Step 4: Commit**

```bash
git add optimizerapi/optimizer.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
refactor(optimizer): extract _compute_next_experiments, _flatten_expected_minima

Both were small but inline-ugly: the next-experiment shape normalisation
and the 3-deep list comprehension for flattening models. Each now reads
as a single function call at the call site.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Create `plot_emitters.py` with `emit_json_single_plots`

The biggest DRY win. The same single-plot emission code is currently inlined three times in `process_result` (single-obj JSON, multi-obj objective_1, multi-obj objective_2), each with a different prefix. We replace all three with one helper.

**Files:**
- Create: `optimizerapi/plot_emitters.py`
- Create: `tests/test_plot_emitters.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_plot_emitters.py`:

```python
"""Tests for the plot-emitters module."""

import json

import numpy
import pytest

from optimizerapi.plot_emitters import emit_json_single_plots


class _FakePlotData:
    """Mimics ProcessOptimizer's get_Brownie_Bee_1d_plot return value."""

    @staticmethod
    def make(n_dims: int):
        # Each dimension yields a 4-element series; the last entry is a
        # histogram (mean, std) pair.
        dims = [[[1.0, 2.0, 3.0, 4.0] for _ in range(4)] for _ in range(n_dims)]
        histogram = (numpy.array([42.0]), numpy.array([1.5]))
        return dims + [histogram]


@pytest.fixture
def fake_brownie_1d(monkeypatch):
    """Patch _get_brownie_bee_1d_plot_safe so this test doesn't need ProcessOptimizer."""
    def _stub(result, x_eval=None):
        return _FakePlotData.make(n_dims=3)
    monkeypatch.setattr(
        "optimizerapi.plot_emitters._get_brownie_bee_1d_plot_safe", _stub
    )


def test_emit_json_single_plots_writes_one_entry_per_dim_plus_histogram(fake_brownie_1d):
    plots: list = []
    emit_json_single_plots(plots, result=object(), prefix="single_0", selected_point=None)
    ids = [p["id"] for p in plots]
    assert ids == ["single_0_0", "single_0_1", "single_0_2", "single_0_3"]
    # Last entry is the histogram payload.
    histogram_payload = json.loads(plots[-1]["plot"])
    assert "histogram" in histogram_payload
    assert histogram_payload["histogram"]["mean"] == 42.0
    assert histogram_payload["histogram"]["std"] == 1.5


def test_emit_json_single_plots_supports_different_prefixes(fake_brownie_1d):
    plots: list = []
    emit_json_single_plots(plots, result=object(), prefix="objective_2", selected_point=None)
    ids = [p["id"] for p in plots]
    assert ids[0] == "objective_2_0"
    assert ids[-1] == "objective_2_3"


def test_emit_json_single_plots_passes_selected_point_through(monkeypatch):
    captured = {}

    def _stub(result, x_eval=None):
        captured["x_eval"] = x_eval
        return _FakePlotData.make(n_dims=2)

    monkeypatch.setattr(
        "optimizerapi.plot_emitters._get_brownie_bee_1d_plot_safe", _stub
    )

    plots: list = []
    sp = [50, 833, "Whipped cream"]
    emit_json_single_plots(plots, result=object(), prefix="single_0", selected_point=sp)
    assert captured["x_eval"] == sp
```

- [ ] **Step 2: Run test to verify it fails**

```bash
env/bin/python -m pytest tests/test_plot_emitters.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'optimizerapi.plot_emitters'`.

- [ ] **Step 3: Create the module**

Create `optimizerapi/plot_emitters.py`:

```python
"""Plot emission for the optimizer API response.

Two output formats are supported:
- ``emit_png_plots`` — base64 PNG plots, used by the legacy UI.
- ``emit_json_single_plots`` / ``emit_pareto_data`` — structured JSON
  plot data, used by the React-based UI.
"""

from typing import TYPE_CHECKING, Any

import json_tricks
import numpy

# Imported from optimizer.py — the private helper that wraps a ProcessOptimizer
# bug with categorical x_eval values. Phase 5 considers moving it here too.
from .optimizer import _get_brownie_bee_1d_plot_safe

if TYPE_CHECKING:
    from .types import Plot


def emit_json_single_plots(
    plots: list["Plot"],
    *,
    result: Any,
    prefix: str,
    selected_point: list[str | float] | None,
) -> None:
    """Append one plot entry per dimension plus a final histogram entry.

    Parameters
    ----------
    plots:
        The mutable list of plot entries to append to.
    result:
        A ProcessOptimizer ``OptimizerResult``-like object.
    prefix:
        Plot-id prefix. The emitted ids are ``{prefix}_0``, ``{prefix}_1``,
        ..., with the final id being ``{prefix}_<n>`` for the histogram.
    selected_point:
        X-space coordinates to highlight, or ``None`` to use the default.
    """
    one_d_data = _get_brownie_bee_1d_plot_safe(result, x_eval=selected_point)
    histogram_entry = one_d_data[-1]
    for i, dim_data in enumerate(one_d_data[:-1]):
        plots.append(
            {"id": f"{prefix}_{i}", "plot": json_tricks.dumps({"data": dim_data})}
        )
    plots.append(
        {
            "id": f"{prefix}_{len(one_d_data) - 1}",
            "plot": json_tricks.dumps(
                {
                    "histogram": {
                        "mean": float(numpy.ravel(histogram_entry[0])[0]),
                        "std": float(numpy.ravel(histogram_entry[1])[0]),
                    }
                }
            ),
        }
    )
```

- [ ] **Step 4: Run tests**

```bash
env/bin/python -m pytest tests/test_plot_emitters.py -v
```
Expected: 3 PASS.

- [ ] **Step 5: Replace the three duplicated loops in `process_result`**

In `optimizer.py:process_result`, find the single-objective JSON loop:

```python
        elif graph_format == "json":
            for idx, model in enumerate(result):
                if "single" in graphs_to_return and optimizer.n_objectives != 2:
                    obj1_1D_data = _get_brownie_bee_1d_plot_safe(result[idx], x_eval=selected_point)
                    histogram_entry = obj1_1D_data[-1]
                    for i, dim_data in enumerate(obj1_1D_data[:-1]):
                        plots.append(
                            {
                                "id": f"single_{idx}_{i}",
                                "plot": json_tricks.dumps({"data": dim_data}),
                            }
                        )
                    plots.append(
                        {
                            "id": f"single_{idx}_{len(obj1_1D_data) - 1}",
                            "plot": json_tricks.dumps(
                                {
                                    "histogram": {
                                        "mean": float(
                                            numpy.ravel(histogram_entry[0])[0]
                                        ),
                                        "std": float(
                                            numpy.ravel(histogram_entry[1])[0]
                                        ),
                                    }
                                }
                            ),
                        }
                    )
                if "convergence" in graphs_to_return:
                    pass
                    # skip plotting convergence data in json format

                if "objective" in graphs_to_return:
                    pass
                    # skip plotting objective data in json format
```

Replace with:

```python
        elif graph_format == "json":
            for idx, model in enumerate(result):
                if "single" in graphs_to_return and optimizer.n_objectives != 2:
                    emit_json_single_plots(
                        plots,
                        result=result[idx],
                        prefix=f"single_{idx}",
                        selected_point=selected_point,
                    )
            # convergence and objective plots are PNG-only; nothing to emit here.
```

Then find the multi-objective objective_1 loop (a near-copy):

```python
            if optimizer.n_objectives == 2 and "single" in graphs_to_return:
                obj1_1D_data = _get_brownie_bee_1d_plot_safe(result[0], x_eval=selected_point)
                histogram_entry = obj1_1D_data[-1]
                for i, dim_data in enumerate(obj1_1D_data[:-1]):
                    plots.append(
                        {
                            "id": f"objective_1_{i}",
                            "plot": json_tricks.dumps({"data": dim_data}),
                        }
                    )
                plots.append(
                    {
                        "id": f"objective_1_{len(obj1_1D_data) - 1}",
                        "plot": json_tricks.dumps(
                            {
                                "histogram": {
                                    "mean": float(numpy.ravel(histogram_entry[0])[0]),
                                    "std": float(numpy.ravel(histogram_entry[1])[0]),
                                }
                            }
                        ),
                    }
                )

                obj2_1D_data = _get_brownie_bee_1d_plot_safe(result[1], x_eval=selected_point)
                histogram_entry2 = obj2_1D_data[-1]
                for i, dim_data in enumerate(obj2_1D_data[:-1]):
                    plots.append(
                        {
                            "id": f"objective_2_{i}",
                            "plot": json_tricks.dumps({"data": dim_data}),
                        }
                    )
                plots.append(
                    {
                        "id": f"objective_2_{len(obj2_1D_data) - 1}",
                        "plot": json_tricks.dumps(
                            {
                                "histogram": {
                                    "mean": float(numpy.ravel(histogram_entry2[0])[0]),
                                    "std": float(numpy.ravel(histogram_entry2[1])[0]),
                                }
                            }
                        ),
                    }
                )
```

Replace with:

```python
            if optimizer.n_objectives == 2 and "single" in graphs_to_return:
                emit_json_single_plots(
                    plots,
                    result=result[0],
                    prefix="objective_1",
                    selected_point=selected_point,
                )
                emit_json_single_plots(
                    plots,
                    result=result[1],
                    prefix="objective_2",
                    selected_point=selected_point,
                )
```

Add the import at the top of `optimizer.py` (after the existing local imports):

```python
from .plot_emitters import emit_json_single_plots
```

- [ ] **Step 6: Run the equivalence test**

```bash
env/bin/python -m pytest tests/test_optimizer.py::test_equivalence_with_and_without_pickled_multi_objective -v
```
Expected: PASS. This test is the BINDING gate — if it fails, the prefix or argument order is wrong somewhere.

- [ ] **Step 7: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: all green, ~3 more tests than before (the new plot_emitters tests).

- [ ] **Step 8: Commit**

```bash
git add optimizerapi/plot_emitters.py optimizerapi/optimizer.py tests/test_plot_emitters.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
refactor(optimizer): unify three JSON single-plot loops into emit_json_single_plots

Same body was inlined three times in process_result with different
prefix strings: single_{idx}, objective_1, objective_2. They are now
one function call each, in a new optimizerapi/plot_emitters.py module.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Move PNG plot emission to `plot_emitters.py`

The PNG path inside `process_result` is its own ~25-line block. Move it out so the dispatcher has fewer branches to read.

**Files:**
- Modify: `optimizerapi/plot_emitters.py`
- Modify: `optimizerapi/optimizer.py`

- [ ] **Step 1: Add `emit_png_plots` to `plot_emitters.py`**

Append to `optimizerapi/plot_emitters.py`:

```python
import base64
import io

import matplotlib.pyplot as plt
from ProcessOptimizer.plots import (
    plot_brownie_bee_frontend,
    plot_convergence,
    plot_objective,
)


def emit_png_plots(
    plots: list["Plot"],
    *,
    result: list,
    dimensions: list[str],
    graphs: list[str],
    max_quality: int,
    objective_pars: str,
) -> None:
    """Append base64-encoded PNG plots for each model in ``result``."""
    for idx, model in enumerate(result):
        if "single" in graphs:
            bb_plots = plot_brownie_bee_frontend(model, max_quality=max_quality)
            for i, plot in enumerate(bb_plots):
                plots.append(
                    {"id": f"single_{idx}_{i}", "plot": _figure_to_b64(plot)}
                )
                plt.close(plot)
        if "convergence" in graphs:
            plot_convergence(model)
            _emit_current_figure(plots, f"convergence_{idx}")
        if "objective" in graphs:
            plot_objective(
                model,
                dimensions=dimensions,
                usepartialdependence=False,
                show_confidence=True,
                pars=objective_pars,
            )
            _emit_current_figure(plots, f"single_{idx}")


def _figure_to_b64(figure) -> str:
    buf = io.BytesIO()
    figure.savefig(buf, format="png")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _emit_current_figure(plots: list["Plot"], plot_id: str) -> None:
    """Snapshot the current matplotlib figure into ``plots`` and clear it."""
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plots.append({"id": plot_id, "plot": base64.b64encode(buf.read()).decode("utf-8")})
    plt.clf()
```

`_emit_current_figure` is the new home for the logic that was in the old `add_plot` helper in `optimizer.py`. The `debug=True` branch of `add_plot` is dropped — it was an unused breakpoint helper.

- [ ] **Step 2: Use `emit_png_plots` from `process_result`**

In `optimizer.py:process_result`, find the PNG branch:

```python
        if graph_format == "png":
            for idx, model in enumerate(result):
                if "single" in graphs_to_return:
                    bb_plots = plot_brownie_bee_frontend(model, max_quality=max_quality)
                    for i, plot in enumerate(bb_plots):
                        pic_io_bytes = io.BytesIO()
                        plot.savefig(pic_io_bytes, format="png")
                        pic_io_bytes.seek(0)
                        pic_hash = base64.b64encode(pic_io_bytes.read())
                        plots.append(
                            {"id": f"single_{idx}_{i}", "plot": str(pic_hash, "utf-8")}
                        )
                        plt.close(plot)
                if "convergence" in graphs_to_return:
                    plot_convergence(model)
                    add_plot(plots, f"convergence_{idx}")

                if "objective" in graphs_to_return:
                    plot_objective(
                        model,
                        dimensions=dimensions,
                        usepartialdependence=False,
                        show_confidence=True,
                        pars=objective_pars,
                    )
                    add_plot(plots, f"single_{idx}")

            if optimizer.n_objectives == 1:
                minimum = expected_minimum(result[0], return_std=True)
                result_details["expected_minimum"] = [
                    round_to_length_scales(minimum[0], optimizer.space),
                    minimum[1],
                ]
```

Replace with:

```python
        if graph_format == "png":
            emit_png_plots(
                plots,
                result=result,
                dimensions=dimensions,
                graphs=graphs_to_return,
                max_quality=max_quality,
                objective_pars=objective_pars,
            )
            if optimizer.n_objectives == 1:
                _set_expected_minimum(result_details, result[0], optimizer.space)
```

The `_set_expected_minimum` helper is new — add it near the other private helpers in `optimizer.py`:

```python
def _set_expected_minimum(
    result_details: dict,
    single_result: object,
    space: object,
) -> None:
    """Compute and store the expected minimum (single-objective only)."""
    minimum = expected_minimum(single_result, return_std=True)
    result_details["expected_minimum"] = [
        round_to_length_scales(minimum[0], space),
        minimum[1],
    ]
```

Then find the duplicated `expected_minimum` block in the JSON single-objective branch:

```python
            if optimizer.n_objectives == 1:
                minimum = expected_minimum(result[0], return_std=True)
                result_details["expected_minimum"] = [
                    round_to_length_scales(minimum[0], optimizer.space),
                    minimum[1],
                ]
```

Replace with:

```python
            if optimizer.n_objectives == 1:
                _set_expected_minimum(result_details, result[0], optimizer.space)
```

Add the import:

```python
from .plot_emitters import emit_json_single_plots, emit_png_plots
```

(Replace the previous import line with the combined import.)

- [ ] **Step 3: Delete the now-unused `add_plot` helper**

The old `add_plot` function in `optimizer.py` (the one that writes to `result` and conditionally calls `plt.savefig` with `debug`) is no longer referenced. Delete it.

```bash
grep -n "^def add_plot\|add_plot(" optimizerapi/optimizer.py
```
Expected after deletion: no output for `^def add_plot` and no remaining call sites.

- [ ] **Step 4: Run the equivalence test + full suite**

```bash
env/bin/python -m pytest tests/test_optimizer.py::test_equivalence_with_and_without_pickled_multi_objective -v
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: equivalence PASS; full suite unchanged.

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/plot_emitters.py optimizerapi/optimizer.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
refactor(optimizer): move PNG plot emission to plot_emitters, drop add_plot

PNG plot rendering, the unused debug=True branch of add_plot, and the
duplicate expected_minimum block are folded into emit_png_plots /
_set_expected_minimum.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Move pareto-data emission to `plot_emitters.py`

**Files:**
- Modify: `optimizerapi/plot_emitters.py`
- Modify: `optimizerapi/optimizer.py`

- [ ] **Step 1: Add `emit_pareto_data` to `plot_emitters.py`**

```python
from ProcessOptimizer.plots import get_Brownie_Bee_Pareto
from ProcessOptimizer.utils.utils import get_Pareto_front_compromise


def emit_pareto_data(plots: list["Plot"], optimizer: object) -> None:
    """Append the pareto-front payload (multi-objective only)."""
    front_x_data, front_y_data, obj1_error, obj2_error = get_Brownie_Bee_Pareto(
        optimizer, n_points=200
    )
    best_idx = get_Pareto_front_compromise(front_y_data)
    pareto_data = {
        "front_x_data": front_x_data.tolist(),
        "front_y_data": front_y_data.tolist(),
        "obj1_error": obj1_error.tolist(),
        "obj2_error": obj2_error.tolist(),
        "best_idx": best_idx,
    }
    plots.append({"id": "pareto_data", "plot": json_tricks.dumps(pareto_data)})
```

Add the `import` to the top of `plot_emitters.py` if not already there.

- [ ] **Step 2: Use it in `process_result`**

Find the pareto-computation block:

```python
            if optimizer.n_objectives == 2 and (
                "pareto" in graphs_to_return or "single" in graphs_to_return
            ):
                front_x_data, front_y_data, obj1_error, obj2_error = (
                    get_Brownie_Bee_Pareto(optimizer, n_points=200)
                )
                best_idx = get_Pareto_front_compromise(front_y_data)
                if "pareto" in graphs_to_return:
                    pareto_data = {
                        "front_x_data": front_x_data.tolist(),
                        "front_y_data": front_y_data.tolist(),
                        "obj1_error": obj1_error.tolist(),
                        "obj2_error": obj2_error.tolist(),
                        "best_idx": best_idx,
                    }
                    plots.append(
                        {
                            "id": "pareto_data",
                            "plot": json_tricks.dumps(pareto_data),
                        }
                    )
```

Replace with:

```python
            if optimizer.n_objectives == 2 and "pareto" in graphs_to_return:
                emit_pareto_data(plots, optimizer)
```

**Notice the simplification:** the original `if` was `pareto OR single` but only emitted when `pareto` was actually in the list. The `OR single` was dead — the original outer condition gated a block where only the inner `if "pareto"` actually mattered. We drop the misleading OR.

(If a future need arises to compute the pareto front for plotting reasons beyond `"pareto"`, this can come back. Right now it doesn't.)

Update the import line:

```python
from .plot_emitters import emit_json_single_plots, emit_pareto_data, emit_png_plots
```

Remove now-unused imports from `optimizer.py`:

```bash
grep -n "from ProcessOptimizer.plots import\|get_Pareto_front_compromise" optimizerapi/optimizer.py
```

If `get_Brownie_Bee_Pareto`, `plot_brownie_bee_frontend`, `plot_convergence`, `plot_objective`, or `get_Pareto_front_compromise` are no longer used in `optimizer.py`, remove them from the imports. (`_get_brownie_bee_1d_plot_safe` still lives in `optimizer.py` and is re-imported by `plot_emitters.py` — leave that alone for now.)

- [ ] **Step 3: Run the equivalence test + full suite**

```bash
env/bin/python -m pytest tests/test_optimizer.py::test_equivalence_with_and_without_pickled_multi_objective -v
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: equivalence PASS; full suite unchanged.

- [ ] **Step 4: Commit**

```bash
git add optimizerapi/plot_emitters.py optimizerapi/optimizer.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
refactor(optimizer): move emit_pareto_data to plot_emitters

Also drops the misleading 'pareto OR single' outer condition — only
'pareto' was ever load-bearing for the actual emission.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Final shrink + mypy + lint

By this point `process_result` should be close to 60 lines. The body still has the local-alias reassignments from Task 1; drop them now that the function is small enough to use `parsed.X` directly throughout.

**Files:**
- Modify: `optimizerapi/optimizer.py`

- [ ] **Step 1: Drop the local-alias block in `process_result`**

Find:

```python
    parsed = _parse_extras(extras, logging.getLogger(__name__))
    graph_format = parsed.graph_format
    max_quality = parsed.max_quality
    graphs_to_return = parsed.graphs_to_return
    objective_pars = parsed.objective_pars
    pickle_model = parsed.include_model
    selected_point = parsed.selected_point
    experiment_suggestion_count = parsed.experiment_suggestion_count
```

Replace with:

```python
    parsed = _parse_extras(extras, logging.getLogger(__name__))
```

Then update every reference in the body from the bare name to `parsed.X`. For example:

- `graph_format == "png"` → `parsed.graph_format == "png"`
- `experiment_suggestion_count` → `parsed.experiment_suggestion_count`
- `selected_point` → `parsed.selected_point`
- `graphs_to_return` → `parsed.graphs_to_return`
- `max_quality` → `parsed.max_quality`
- `objective_pars` → `parsed.objective_pars`
- `pickle_model` → `parsed.include_model`

The body should now be small enough to inspect that no references are missed. Run pytest after the substitution.

- [ ] **Step 2: Run mypy on `optimizer.py`**

```bash
env/bin/mypy optimizerapi/optimizer.py 2>&1 | tail -20
```
Expected: significantly fewer errors than the Phase 3 baseline. The new helpers are typed; the dispatcher uses typed inputs. Fix anything that mypy now flags as a real issue (typically forgotten-import, attribute-access on a wider type than intended).

- [ ] **Step 3: Run flake8**

```bash
env/bin/flake8 optimizerapi/optimizer.py optimizerapi/plot_emitters.py --max-line-length=127
```
Expected: clean.

- [ ] **Step 4: Run the equivalence test and full suite one final time**

```bash
env/bin/python -m pytest tests/test_optimizer.py::test_equivalence_with_and_without_pickled_multi_objective -v
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: equivalence PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/optimizer.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
refactor(optimizer): drop local aliases; use parsed.X directly

Final shrink of process_result after the extractions land. The
dispatcher is now under ~80 lines and walks each path in order:
extras → next → models → graph branches → pickled → extras tail.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Check the LOC delta**

```bash
wc -l optimizerapi/optimizer.py optimizerapi/plot_emitters.py
```

Reasonable target: `optimizer.py` under 350 lines (was 565), `plot_emitters.py` under 200 lines. The total may be similar or slightly larger — the win is in distribution and readability, not raw line count.

---

## Acceptance criteria

- `optimizerapi/optimizer.py:process_result` is under ~80 lines.
- `optimizerapi/plot_emitters.py` exists and owns all plot emission.
- `emit_json_single_plots` is called three times from `process_result` (single-obj single, multi-obj objective_1, multi-obj objective_2) — i.e. the duplication is gone.
- The PNG path in `process_result` is a single call to `emit_png_plots`.
- `add_plot` and its `debug=True` branch are deleted (no callers remain).
- `_get_brownie_bee_1d_plot_safe`, `round_to_length_scales`, `process_model`, `add_version_info`, `convert_number_type` continue to live in `optimizer.py` — they don't fit the plot-emitters split.
- `test_equivalence_with_and_without_pickled_multi_objective` passes after every commit in this phase.
- Full pytest run is green.
- `mypy optimizerapi/optimizer.py optimizerapi/plot_emitters.py` is clean.
- `flake8 optimizerapi --max-line-length=127` introduces no new violations.

## Out of scope

- Annotating every internal helper (most are now small enough to be obvious).
- Removing `_get_brownie_bee_1d_plot_safe` from `optimizer.py` (it's the workaround for the upstream bug; moving it would cost more clarity than it gains).
- Async / streaming responses (a Phase 6+ idea, if it ever happens).
- Changing the OpenAPI response shape (this whole phase is behavior-preserving).
