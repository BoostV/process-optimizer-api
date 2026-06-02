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


class _FakeModel:
    def predict(self, X, return_std=False):
        # Make the histogram depend on the transformed point so the test would
        # catch a regression that ignored it.
        value = float(numpy.ravel(X)[0])
        return numpy.array([value]), numpy.array([0.5])


class _FakeResult:
    """Minimal stand-in for an OptimizeResult with a transform + model."""

    def __init__(self):
        self.models = [_FakeModel()]
        self.space = self

    def transform(self, points):
        # Identity transform; just records that it was called with the point.
        return numpy.asarray(points, dtype=float)


def test_emit_json_single_plots_passes_selected_point_through(monkeypatch):
    captured = {}

    def _stub(result, x_eval=None):
        captured["x_eval"] = x_eval
        return _FakePlotData.make(n_dims=2)

    monkeypatch.setattr(
        "optimizerapi.plot_emitters._get_brownie_bee_1d_plot_safe", _stub
    )

    plots: list = []
    sp = [50, 833]
    emit_json_single_plots(
        plots, result=_FakeResult(), prefix="single_0", selected_point=sp
    )
    assert captured["x_eval"] == sp
    # With a selected point the histogram is predicted at the transformed point,
    # not taken from get_Brownie_Bee_1d_plot's (buggy) last entry.
    histogram_payload = json.loads(plots[-1]["plot"])
    assert histogram_payload["histogram"]["mean"] == 50.0
