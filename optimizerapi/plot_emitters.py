"""Plot emission for the optimizer API response.

Two output formats are supported:
- ``emit_png_plots`` — base64 PNG plots, used by the legacy UI.
- ``emit_json_single_plots`` / ``emit_pareto_data`` — structured JSON
  plot data, used by the React-based UI.
"""

import base64
import io
from typing import TYPE_CHECKING, Any

import json_tricks
import matplotlib.pyplot as plt
import numpy
from ProcessOptimizer.plots import (
    get_Brownie_Bee_1d_plot,
    get_Brownie_Bee_Pareto,
    plot_brownie_bee_frontend,
    plot_convergence,
    plot_objective,
)
from ProcessOptimizer.utils.utils import get_Pareto_front_compromise

if TYPE_CHECKING:
    from .types import Plot


def _get_brownie_bee_1d_plot_safe(result, x_eval=None, **kwargs):
    """Workaround for ProcessOptimizer bug: model.predict must receive space.transform output,
    not a raw list containing categorical strings."""
    if x_eval is None:
        return get_Brownie_Bee_1d_plot(result, x_eval=x_eval, **kwargs)

    space = result.space
    has_categoricals = any(
        not isinstance(v, (int, float)) for v in x_eval
    )
    if not has_categoricals:
        return get_Brownie_Bee_1d_plot(result, x_eval=x_eval, **kwargs)

    model = result.models[-1]
    x_transformed = space.transform([x_eval])
    original_predict = model.predict

    def _predict_with_transform(X, **predict_kwargs):
        arr = numpy.array(X)
        if arr.dtype.kind in ("U", "S", "O"):
            return original_predict(x_transformed, **predict_kwargs)
        return original_predict(X, **predict_kwargs)

    model.predict = _predict_with_transform
    try:
        return get_Brownie_Bee_1d_plot(result, x_eval=x_eval, **kwargs)
    finally:
        model.predict = original_predict


def emit_json_single_plots(
    plots: "list[Plot]",
    *,
    result: Any,
    prefix: str,
    selected_point: "list[str | float] | None",
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


def emit_png_plots(
    plots: "list[Plot]",
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


def emit_pareto_data(plots: "list[Plot]", optimizer: object) -> "list | None":
    """Append the pareto-front payload (multi-objective only).

    Returns the x-space coordinates of the model's compromise/optimal point
    (``front_x_data[best_idx]``) so the caller can use it as the default
    ``selected_point`` for the per-objective 1D plots — without it, each
    objective's plots default to its own expected minimum and the two rows end
    up describing different settings. Returns ``None`` if no front is available.
    """
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

    if best_idx is None or len(front_x_data) == 0:
        return None
    return front_x_data[best_idx].tolist()


def _figure_to_b64(figure) -> str:
    buf = io.BytesIO()
    figure.savefig(buf, format="png")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _emit_current_figure(plots: "list[Plot]", plot_id: str) -> None:
    """Snapshot the current matplotlib figure into ``plots`` and clear it."""
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plots.append({"id": plot_id, "plot": base64.b64encode(buf.read()).decode("utf-8")})
    plt.clf()
