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
