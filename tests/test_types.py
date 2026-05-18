"""Sanity checks for the boundary type definitions."""

from optimizerapi.types import (  # noqa: F401
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
