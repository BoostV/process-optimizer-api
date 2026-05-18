"""ProcessOptimizer executor

This file contains the central logic for executing the optimizer requests.
It should only depend on ProcessOptimizer specifics and json related features.
"""

import importlib.metadata
import json
import logging
import os
import platform
import subprocess
from dataclasses import dataclass
from time import strftime

import json_tricks
import matplotlib.pyplot as plt
import numpy
from ProcessOptimizer import Optimizer, expected_minimum
from ProcessOptimizer.space import Real
from ProcessOptimizer.space.constraints import SumEquals

from typing import TYPE_CHECKING, Any

from .securepickle import get_crypto
from .pickled_state import compute_fingerprint, pack, unpack_if_valid
from .plot_emitters import emit_json_single_plots, emit_pareto_data, emit_png_plots

if TYPE_CHECKING:
    from .types import Extras, OptimizerConfig, Plot, RequestBody

numpy.random.seed(42)
plt.switch_backend("Agg")


@dataclass(frozen=True)
class _ParsedExtras:
    graph_format: str
    max_quality: int
    graphs_to_return: list[str]
    objective_pars: str
    include_model: bool
    selected_point: "list[str | float] | None"
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
        graphs_to_return=list(extras.get(
            "graphs", ["objective", "convergence", "pareto", "single"]
        )),
        objective_pars=extras.get("objectivePars", "result"),
        include_model=_parse_bool(extras.get("includeModel", "true")),
        selected_point=selected_point,
        experiment_suggestion_count=int(extras.get("experimentSuggestionCount", 1)),
    )


def _compute_next_experiments(
    optimizer: Any,
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


def run(body: "RequestBody") -> dict:
    """Handle the run request.

    Returns the response envelope as a plain ``dict`` — the json_tricks
    round-trip at the bottom of the function drops NumPy types, which is
    why we cannot return ``ResponseEnvelope`` directly without an
    explicit cast.
    """
    data = [(run["xi"], run["yi"]) for run in body["data"]]
    cfg = body["optimizerConfig"]
    constraints = cfg.get("constraints", [])
    extras = body.get("extras", {})
    use_actual_measurement_histogram = json.loads(
        extras.get("useActualMeasurementHistogram", "true").lower()
    )
    space = [
        (
            (
                convert_number_type(x["from"], x["type"]),
                convert_number_type(x["to"], x["type"]),
            )
            if x["type"] in ("discrete", "continuous")
            else tuple(x["categories"])
        )
        for x in cfg["space"]
    ]
    dimensions = [x["name"] for x in cfg["space"]]
    hyperparams = {
        "base_estimator": cfg["baseEstimator"],
        "acq_func": cfg["acqFunc"],
        "n_initial_points": cfg["initialPoints"],
        "acq_func_kwargs": {"kappa": cfg["kappa"], "xi": cfg["xi"]},
    }

    Xi = []
    Yi = []
    if data:
        Xi, Yi = map(list, zip(*data))

    n_objectives = 1
    if len(Yi) > 0:
        n_objectives = len(Yi[0])

    request_fingerprint = compute_fingerprint(body["data"], cfg)
    pickled_input = extras.get("pickled", "")
    if pickled_input:
        include_model_str = str(extras.get("includeModel", "true")).lower()
        if include_model_str == "false":
            logging.getLogger(__name__).warning(
                "includeModel=false with extras.pickled present — if the cache hint is used, "
                "the next call will not have one to reuse"
            )
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

    if constraints is not None and len(constraints) > 0:
        optimizer = Optimizer(
            space, **hyperparams, lhs=False, n_objectives=n_objectives
        )
        parsed_constraints = [
            SumEquals(dimensions=x["dimensions"], value=x["value"]) for x in constraints
        ]
        optimizer.set_constraints(parsed_constraints)
    else:
        optimizer = Optimizer(space, **hyperparams, n_objectives=n_objectives)

    if data:
        if n_objectives == 1:
            Yi = [elm[0] for elm in Yi]
        result = optimizer.tell(Xi, Yi)
        if n_objectives == 1 and len(result.models) > 0:
            if use_actual_measurement_histogram:
                optimizer.add_observational_noise()
                result = optimizer.get_result()
            result = [result]
    else:
        result = []

    response = process_result(
        result, optimizer, dimensions, cfg, extras, data, space,
        request_fingerprint=request_fingerprint, pickled_used=False,
    )

    response["result"]["extras"]["parameters"] = {
        "dimensions": dimensions,
        "space": space,
        "hyperparams": hyperparams,
        "Xi": Xi,
        "Yi": Yi,
        "extras": extras,
    }

    # It is necesarry to convert response to a json string and then back to
    # dictionary because NumPy types are not serializable by default
    return json.loads(json_tricks.dumps(response))


def convert_number_type(value, num_type):
    """Converts input value to either integer or float depending on the string supplied in numType"""
    if num_type == "discrete":
        return int(value)
    return float(value)


def process_result(
    result: Any,
    optimizer: Any,
    dimensions: list[str],
    cfg: "OptimizerConfig",
    extras: "Extras",
    data: list[tuple[list[str | float], list[float]]],
    space: list,
    *,
    request_fingerprint: str,
    pickled_used: bool,
) -> dict:
    """Extracts results from the OptimizerResult.

    Parameters
    ----------
    result : OptimizerResult
        The result as it is returned from Optimizer.tell
    optimizer : ProcessOptimizer
        The instance used during the run. It contains the run configuration
        and parameters used.
    dimensions : list
        List of dimension names ordered to match space descriptor
    cfg : dict
        The configuration part of the user request
    extras: dict
        A dictionary containing "extra" non-specified values received from the client
    data : list
        The data points that have been used in the result
    space : list
        The input space definition

    Returns
    -------
    dict
        a dictionary containing results and plots.
        The dictionary has this structure:
        {
            plots: [{id: plotname, plot: BASE64 encoded png}],
            result: { dict with relevant properties, e.g.,
                suggestions for next experiment,
                model representation etc.}
        }
    """
    result_details = {"next": [], "models": [], "pickled": "", "extras": {}}
    plots: "list[Plot]" = []
    response = {"plots": plots, "result": result_details}
    # GraphFormat should, at the moment, be either "png" or "none". Default (legacy)
    # behavior is "png", so the API returns png images. Any other input is interpreted
    # as "None" at the moment.
    parsed = _parse_extras(extras, logging.getLogger(__name__))

    result_details["next"] = _compute_next_experiments(
        optimizer, cfg, parsed.experiment_suggestion_count
    )

    if len(data) >= cfg["initialPoints"]:
        # Some calculations are only possible if the model has
        # processed more than "initialPoints" data points
        result_details["models"] = [process_model(model, optimizer) for model in result]
        if parsed.graph_format == "png":
            emit_png_plots(
                plots,
                result=result,
                dimensions=dimensions,
                graphs=parsed.graphs_to_return,
                max_quality=parsed.max_quality,
                objective_pars=parsed.objective_pars,
            )
            if optimizer.n_objectives == 1:
                _set_expected_minimum(result_details, result[0], optimizer.space)
        elif parsed.graph_format == "json":
            for idx, model in enumerate(result):
                if "single" in parsed.graphs_to_return and optimizer.n_objectives != 2:
                    emit_json_single_plots(
                        plots,
                        result=result[idx],
                        prefix=f"single_{idx}",
                        selected_point=parsed.selected_point,
                    )
            # convergence and objective plots are PNG-only; nothing to emit here.

            if optimizer.n_objectives == 1:
                _set_expected_minimum(result_details, result[0], optimizer.space)

            if optimizer.n_objectives == 2 and "pareto" in parsed.graphs_to_return:
                emit_pareto_data(plots, optimizer)

            if optimizer.n_objectives == 2 and "single" in parsed.graphs_to_return:
                emit_json_single_plots(
                    plots,
                    result=result[0],
                    prefix="objective_1",
                    selected_point=parsed.selected_point,
                )
                emit_json_single_plots(
                    plots,
                    result=result[1],
                    prefix="objective_2",
                    selected_point=parsed.selected_point,
                )

    if parsed.include_model:
        result_details["pickled"] = pack(
            result=result,
            next_points=result_details["next"],
            optimizer=optimizer,
            fingerprint=request_fingerprint,
            crypto=get_crypto(),
        )

    add_version_info(result_details["extras"])
    result_details["extras"]["pickledUsed"] = pickled_used

    _flatten_expected_minima(response["result"]["models"])
    return response


def process_model(model, optimizer):
    """Extract model specific results.

    Parameters
    ----------
    model : object
        The model as returned by the optimizer

    Returns
    -------
    dict
        a dictionary containing the model specific results.
    """
    result_details = {"expected_minimum": [], "extras": {}}
    minimum = expected_minimum(model)
    result_details["expected_minimum"] = [
        round_to_length_scales(minimum[0], optimizer.space),
        round(minimum[1], 2),
    ]
    return result_details


def round_to_length_scales(x, space):
    """Rounds a suggested experiment to to the length scales of each dimension

    For each dimension the length of the dimension is calculated and the
    length scale is defined as 1/1000th of the length.
    The precision is the n in 10^n which is the closest to the
    length_scale (rounded) up .
    The suggested experiment value is then rounded to n decimals

    This function should be called after asking for a new experiment and before
    adding it to resultDetails.
    Note that this function will only round Real dimensions

    Parameters
    ----------
    x : list or list of lists
        The suggested experiment(s)
    space : ProcessOptimizer.space.space.Space
        The space of the optimizer. Contains information about each dimension
        of the space
    """
    for i, dim in enumerate(space.dimensions):
        # Checking if dimension is real. Else do nothing
        if isinstance(dim, Real):
            length = dim.high - dim.low
            # Length scale of the dimension is 1/1000 of the dimension length
            length_scale = length / 1000
            # The precision is found by taking the
            # negative log10 to the length scale ceiled
            precision = int(numpy.ceil(-numpy.log10(length_scale)))

            # If multiple experiments round dimension values for all experiments
            # else round dimension value
            if any(isinstance(el, list) for el in x):
                for exp in x:
                    exp[i] = round(exp[i], precision)
            else:
                x[i] = round(x[i], precision)
    return x


def add_version_info(extras):
    """Add various version information to the dictionary supplied.

    Parameters
    ----------
    extras : dict
            The dictionary to hold the version information
    """

    extras["libraries"] = sorted(
        [
            f"{dist.metadata['Name']}=={dist.version}"
            for dist in importlib.metadata.distributions()
        ]
    )

    extras["pythonVersion"] = platform.python_version()

    if os.path.isfile("version.txt"):
        with open("version.txt", "r", encoding="utf-8") as version_file:
            extras["apiVersion"] = version_file.readline().rstrip()
    else:
        try:
            extras["apiVersion"] = (
                subprocess.check_output(["git", "describe", "--always"])
                .strip()
                .decode()
            )
        except IOError:
            extras["apiVersion"] = "Unknown development version"

    extras["timeOfExecution"] = strftime("%Y-%m-%d %H:%M:%S")
