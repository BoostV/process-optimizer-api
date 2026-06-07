"""
Test main optimizer module
"""

from unittest.mock import patch
import copy
import collections.abc
import json
import numpy as np
from ProcessOptimizer import Optimizer
from optimizerapi import optimizer_handler as optimizer
from optimizerapi.optimizer import (
    _choose_ask_strategy,
    _compute_next_experiments,
    _estimate_stbr_seconds,
)
from optimizerapi.securepickle import get_crypto, pickleToString, unpickleFromString

sampleData = [
    {"xi": [651, 56, 722, "Ræv"], "yi": [1]},
    {"xi": [651, 42, 722, "Ræv"], "yi": [0.2]},
]

sampleMultiObjectiveData = [
    {"xi": [651, 56, 722, "Ræv"], "yi": [1, 2]},
    {"xi": [651, 42, 722, "Ræv"], "yi": [0.2, 0.5]},
    {"xi": [652, 41, 722, "Ræv"], "yi": [0.1, 0.5]},
]

sampleConfig = {
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

samplePayload = {"data": sampleData, "optimizerConfig": sampleConfig}

brownie_with_constraints = {
    "extras": {
        "experimentSuggestionCount": 3,
        "graphs": ["single"],
        "includeModel": "false",
        "objectivePars": "expected_minimum",
    },
    "data": [],
    "optimizerConfig": {
        "baseEstimator": "GP",
        "acqFunc": "EI",
        "initialPoints": 3,
        "kappa": 1.96,
        "xi": 5,
        "space": [
            {"type": "continuous", "name": "Cocoa", "from": 18, "to": 56},
            {"type": "continuous", "name": "Powdered sugar", "from": 79, "to": 237},
            {"type": "discrete", "name": "Egg whites", "from": 1, "to": 4},
            {"type": "discrete", "name": "Time", "from": 16, "to": 30},
            {
                "type": "category",
                "name": "Temperature",
                "categories": ["160", "180", "200"],
            },
        ],
        "constraints": [{"type": "sum", "dimensions": [0, 1], "value": 200}],
    },
}
brownie_without_constraints = {
    "extras": {
        "experimentSuggestionCount": 3,
        "graphs": ["single"],
        "includeModel": "false",
        "objectivePars": "expected_minimum",
    },
    "data": [],
    "optimizerConfig": {
        "baseEstimator": "GP",
        "acqFunc": "EI",
        "initialPoints": 3,
        "kappa": 1.96,
        "xi": 5,
        "space": [
            {"type": "continuous", "name": "Cocoa", "from": 18, "to": 56},
            {"type": "continuous", "name": "Powdered sugar", "from": 79, "to": 237},
            {"type": "discrete", "name": "Egg whites", "from": 1, "to": 4},
            {"type": "discrete", "name": "Time", "from": 16, "to": 30},
            {
                "type": "category",
                "name": "Temperature",
                "categories": ["160", "180", "200"],
            },
        ],
        "constraints": [],
    },
}


def validateResult(result):
    assert "plots" in result
    assert "result" in result
    assert "models" in result["result"]
    assert "next" in result["result"]
    assert all(len(x) == len(sampleConfig["space"]) for x in result["result"]["next"])
    assert "pickled" in result["result"]
    assert len(result["result"]["pickled"]) > 1
    if len(result["result"]["models"]) > 0:
        for model in result["result"]["models"]:
            assert "expected_minimum" in model


def test_can_be_run_without_data():
    result = optimizer.run_optimizer(body={"data": [], "optimizerConfig": sampleConfig})
    validateResult(result)
    assert len(result["plots"]) == 0


def test_generates_plots_when_run_with_more_than_initialPoints_samples():
    result = optimizer.run_optimizer(body={"data": sampleData, "optimizerConfig": sampleConfig})
    validateResult(result)
    assert len(result["result"]["models"]) > 0
    assert len(result["plots"]) == 7


def test_generates_convergence_plots():
    convergence_config = copy.deepcopy(sampleConfig)
    result = optimizer.run_optimizer(
        body={"data": sampleData, "optimizerConfig": convergence_config, "extras": {"graphs": ["convergence"]}}
    )
    validateResult(result)
    assert len(result["result"]["models"]) > 0
    assert len(result["plots"]) == 1
    assert result["plots"][0]["id"] == "convergence_0"


def test_specifying_png_plots():
    result = optimizer.run_optimizer(
        body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"graphFormat": "png"},
        }
    )
    validateResult(result)
    assert len(result["result"]["models"]) > 0
    assert len(result["plots"]) == 7


def test_specifying_json_single_plots():
    result = optimizer.run_optimizer(
        body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"graphFormat": "json", "graphs": ["single"], "includeModel": "false"},
        }
    )
    # Don't call validateResult() because includeModel is false, so pickled model won't be included
    assert len(result["result"]["models"]) > 0
    assert len(result["plots"]) == 5

    plot_ids = [p["id"] for p in result["plots"]]

    assert "single_0_0" in plot_ids
    assert "single_0_1" in plot_ids
    assert "single_0_2" in plot_ids
    assert "single_0_3" in plot_ids
    assert "single_0_4" in plot_ids
    assert "single_0" not in plot_ids

    for dim_idx in range(4):
        plot_id = f"single_0_{dim_idx}"
        plot_entry = next(p for p in result["plots"] if p["id"] == plot_id)
        plot_data = json.loads(plot_entry["plot"])

        assert "data" in plot_data
        assert isinstance(plot_data["data"], list)
        assert len(plot_data["data"]) == 4

    histogram_entry = next(p for p in result["plots"] if p["id"] == "single_0_4")
    histogram_data = json.loads(histogram_entry["plot"])

    assert "histogram" in histogram_data
    assert isinstance(histogram_data["histogram"], dict)
    assert "mean" in histogram_data["histogram"]
    assert "std" in histogram_data["histogram"]
    assert isinstance(histogram_data["histogram"]["mean"], (int, float))
    assert isinstance(histogram_data["histogram"]["std"], (int, float))


def test_specifying_empty_extras_preserve_legacy_plotting():
    result = optimizer.run_optimizer(
        body={"data": sampleData, "optimizerConfig": sampleConfig, "extras": {}}
    )
    validateResult(result)
    assert len(result["result"]["models"]) > 0
    assert len(result["plots"]) == 7


def test_deselecting_plots():
    # If graphFormat is none, no plots should be returned. This should be faster.
    result = optimizer.run_optimizer(
        body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"graphFormat": "none"},
        }
    )
    validateResult(result)
    assert len(result["result"]["models"]) > 0
    assert len(result["plots"]) == 0


def test_can_accept_multi_objective_data():
    result = optimizer.run_optimizer(
        body={
            "data": sampleMultiObjectiveData,
            "optimizerConfig": sampleConfig,
            "extras": {
                "experimentSuggestionCount": 1,
                "graphFormat": "json",
                "graphs": ["pareto", "single"],
                "objectivePars": "expected_minimum",
            },
        }
    )
    validateResult(result)
    assert len(result["result"]["models"]) > 1
    assert "pareto_data" in [x["id"] for x in result["plots"]]
    assert len(result["plots"]) == 11


def test_multi_objective_json_single_plots():
    result = optimizer.run_optimizer(
        body={
            "data": sampleMultiObjectiveData,
            "optimizerConfig": sampleConfig,
            "extras": {
                "graphFormat": "json",
                "graphs": ["single", "pareto"],
                "includeModel": "false",
                "experimentSuggestionCount": 1,
                "objectivePars": "expected_minimum",
            },
        }
    )
    assert len(result["result"]["models"]) > 1
    plot_ids = [x["id"] for x in result["plots"]]

    assert len(result["plots"]) == 11

    assert "pareto_data" in plot_ids

    assert "objective_1_data" not in plot_ids
    assert "objective_2_data" not in plot_ids

    for objective_prefix in ["objective_1", "objective_2"]:
        for idx in range(5):
            plot_id = f"{objective_prefix}_{idx}"
            assert plot_id in plot_ids, f"Expected {plot_id} in plot IDs"

    for objective_prefix in ["objective_1", "objective_2"]:
        for dim_idx in range(4):
            plot_id = f"{objective_prefix}_{dim_idx}"
            plot_entry = next(x for x in result["plots"] if x["id"] == plot_id)
            plot_data = json.loads(plot_entry["plot"])

            assert "data" in plot_data
            assert isinstance(plot_data["data"], list)
            assert len(plot_data["data"]) == 4

    for objective_prefix in ["objective_1", "objective_2"]:
        histogram_id = f"{objective_prefix}_4"
        histogram_entry = next(x for x in result["plots"] if x["id"] == histogram_id)
        histogram_data = json.loads(histogram_entry["plot"])

        assert "histogram" in histogram_data
        assert isinstance(histogram_data["histogram"], dict)
        assert "mean" in histogram_data["histogram"]
        assert "std" in histogram_data["histogram"]
        assert isinstance(histogram_data["histogram"]["mean"], (int, float))
        assert isinstance(histogram_data["histogram"]["std"], (int, float))


def test_deselecting_pickled_model():
    # If includeModel is false, pickled data should not be included in result
    result = optimizer.run_optimizer(
        body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"includeModel": "false"},
        }
    )
    assert "pickled" in result["result"]
    assert len(result["result"]["pickled"]) == 0


def test_selecting_pickled_model():
    # If includeModel is true, pickled data should be included in result
    result = optimizer.run_optimizer(
        body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"includeModel": "true"},
        }
    )
    assert "pickled" in result["result"]
    assert len(result["result"]["pickled"]) > 0


def test_expected_minimum_contains_std_deviation():
    result = optimizer.run_optimizer(body={"data": sampleData, "optimizerConfig": sampleConfig})
    assert "expected_minimum" in result["result"]
    expected_minimum = result["result"]["expected_minimum"]
    assert isinstance(expected_minimum[1], collections.abc.Sequence)


@patch("optimizerapi.optimizer.Optimizer")
def test_when_using_constraints_set_constraints_should_be_called(mock):
    instance = mock.return_value
    request = brownie_with_constraints
    optimizer.run_optimizer(body=request)
    instance.set_constraints.assert_called_once()


@patch("optimizerapi.optimizer.Optimizer")
def test_when_not_using_constraints_set_constraints_should_not_be_called(mock):
    instance = mock.return_value
    request = brownie_without_constraints
    optimizer.run_optimizer(body=request)
    instance.set_constraints.assert_not_called()


@patch("optimizerapi.optimizer.Optimizer")
def test_when_using_constraints_strategy_cl_min_should_be_used(mock):
    instance = mock.return_value
    request = brownie_with_constraints
    optimizer.run_optimizer(body=request)
    instance.ask.assert_called_once_with(n_points=3, strategy="cl_min")


def test_choose_ask_strategy_prefers_cl_min_unless_stbr_affordable():
    # single point: strategy is irrelevant, use the safe default
    assert _choose_ask_strategy(1, False, 0.0) == "cl_min"
    # constraints: stbr_fill raises with constraints
    assert _choose_ask_strategy(3, True, 0.1) == "cl_min"
    # unconstrained batch, cheap enough -> opt into Steinerberger
    assert _choose_ask_strategy(2, False, 5.0) == "stbr_fill"
    # unconstrained batch, over budget -> fall back to cl_min
    assert _choose_ask_strategy(2, False, 1000.0) == "cl_min"


def test_estimate_stbr_seconds_dominated_by_categorical_load():
    cont = Optimizer([(0.0, 5.0)] * 4, "GP", n_objectives=1).space
    cat_heavy = Optimizer(
        [(0.0, 5.0)] * 5 + [tuple("abcde")] * 5, "GP", n_objectives=1
    ).space
    cont_20 = Optimizer([(0.0, 5.0)] * 20, "GP", n_objectives=1).space
    # a small continuous space is affordable; a categorical-heavy one is not
    assert _estimate_stbr_seconds(cont, 2) <= 10
    assert _estimate_stbr_seconds(cat_heavy, 2) > 10
    # categorical one-hot load dwarfs an equivalent count of continuous dims
    assert _estimate_stbr_seconds(cat_heavy, 2) > _estimate_stbr_seconds(cont_20, 2)


def test_cheap_unconstrained_batch_uses_steinerberger():
    # 4 continuous dims, fitted model, count 2: cheap -> stbr_fill, returns 2 pts.
    space = [(0.0, 100.0)] * 4
    opt = Optimizer(
        space,
        "GP",
        n_initial_points=4,
        acq_func="EI",
        acq_func_kwargs={"kappa": 1.96, "xi": 0.01},
        n_objectives=1,
    )
    rng = np.random.RandomState(3)
    opt.tell(
        rng.uniform(0, 100, size=(8, 4)).tolist(),
        rng.uniform(0, 1, size=8).tolist(),
    )
    assert (
        _choose_ask_strategy(2, False, _estimate_stbr_seconds(opt.space, 2))
        == "stbr_fill"
    )
    nxt = _compute_next_experiments(opt, 2)
    assert len(nxt) == 2
    assert all(len(point) == len(space) for point in nxt)


def test_multi_suggestion_without_constraints_terminates_quickly():
    # Regression for the stbr_fill hang: a fitted model (data >= initialPoints)
    # with a categorical-heavy space and experimentSuggestionCount > 1 and no
    # constraints. Under the old default strategy this ran for tens of minutes;
    # with cl_min it returns in about a second. Guard with a watchdog so a
    # regression fails fast instead of hanging the suite.
    import signal

    space = [
        {"type": "continuous", "name": "a", "from": 0, "to": 5},
        {"type": "continuous", "name": "b", "from": 0, "to": 5},
        {"type": "continuous", "name": "c", "from": 0, "to": 5},
        {"type": "category", "name": "T", "categories": ["95", "105", "115", "125"]},
        {"type": "category", "name": "pH", "categories": ["4", "5", "6", "7"]},
        {"type": "category", "name": "t", "categories": ["15", "25", "35", "45"]},
    ]
    # initialPoints == 4, supply 5 data points so the model is fitted and
    # _n_initial_points < 1 (the condition that selects the stbr_scipy branch).
    data = [
        {"xi": [1.0, 2.0, 3.0, "95", "4", "15"], "yi": [1.0]},
        {"xi": [2.0, 3.0, 1.0, "105", "5", "25"], "yi": [0.5]},
        {"xi": [3.0, 1.0, 2.0, "115", "6", "35"], "yi": [0.8]},
        {"xi": [4.0, 2.0, 1.0, "125", "7", "45"], "yi": [0.2]},
        {"xi": [0.5, 4.0, 2.0, "95", "5", "35"], "yi": [0.6]},
    ]
    request = {
        "extras": {
            "experimentSuggestionCount": 2,
            "graphs": ["single"],
            "graphFormat": "json",
            "includeModel": "false",
        },
        "data": data,
        "optimizerConfig": {
            "baseEstimator": "GP",
            "acqFunc": "EI",
            "initialPoints": 4,
            "kappa": 1.96,
            "xi": 0.01,
            "space": space,
            "constraints": [],
        },
    }

    def _watchdog(signum, frame):
        raise AssertionError(
            "multi-suggestion run did not terminate within 60s — the slow "
            "stbr_fill/stbr_scipy path has regressed"
        )

    signal.signal(signal.SIGALRM, _watchdog)
    signal.alarm(60)
    try:
        result = optimizer.run_optimizer(body=request)
    finally:
        signal.alarm(0)

    assert len(result["result"]["next"]) == 2
    assert all(len(x) == len(space) for x in result["result"]["next"])


def test_selectedPoint_single_objective_json():
    default_result = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"graphFormat": "json", "graphs": ["single"], "includeModel": "false"},
    })
    default_dim0_plot = next(p for p in default_result["plots"] if p["id"] == "single_0_0")
    default_x_highlight = json.loads(default_dim0_plot["plot"])["data"][3]
    selected_point = [100, 200, 300, "Mus"]
    assert selected_point[0] != default_x_highlight, (
        "selected_point[0] must differ from default highlight for this test to be meaningful"
    )
    result = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {
            "graphFormat": "json",
            "graphs": ["single"],
            "includeModel": "false",
            "selectedPoint": selected_point,
        },
    })
    assert len(result["plots"]) == len(default_result["plots"])
    dim0_plot = next(p for p in result["plots"] if p["id"] == "single_0_0")
    plot_data = json.loads(dim0_plot["plot"])
    assert plot_data["data"][3] == selected_point[0]


def test_selectedPoint_multi_objective_json():
    selected_point = [651, 56, 722, "Ræv"]
    result = optimizer.run_optimizer(body={
        "data": sampleMultiObjectiveData,
        "optimizerConfig": sampleConfig,
        "extras": {
            "graphFormat": "json",
            "graphs": ["single"],
            "includeModel": "false",
            "experimentSuggestionCount": 1,
            "selectedPoint": selected_point,
        },
    })
    obj1_dim0 = next(p for p in result["plots"] if p["id"] == "objective_1_0")
    plot_data = json.loads(obj1_dim0["plot"])
    assert plot_data["data"][3] == selected_point[0]
    obj2_dim0 = next(p for p in result["plots"] if p["id"] == "objective_2_0")
    plot_data2 = json.loads(obj2_dim0["plot"])
    assert plot_data2["data"][3] == selected_point[0]


def test_selectedPoint_with_png_logs_warning_and_is_ignored(caplog):
    import logging as _logging

    with caplog.at_level(_logging.WARNING, logger="optimizerapi.optimizer"):
        result = optimizer.run_optimizer(body={
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


def test_no_selectedPoint_preserves_default():
    result = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"graphFormat": "json", "graphs": ["single"], "includeModel": "false"},
    })
    assert len(result["plots"]) > 0
    single_plots = [p for p in result["plots"] if p["id"].startswith("single_")]
    assert len(single_plots) > 0
    for p in single_plots:
        plot_data = json.loads(p["plot"])
        if "histogram" not in plot_data:
            assert "data" in plot_data
            assert len(plot_data["data"]) == 4


def test_selectedPoint_does_not_change_expected_minimum():
    default_result = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"graphFormat": "json", "graphs": ["single"], "includeModel": "false"},
    })
    selected_point = [651, 56, 722, "Ræv"]
    result_with_selection = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {
            "graphFormat": "json",
            "graphs": ["single"],
            "includeModel": "false",
            "selectedPoint": selected_point,
        },
    })
    assert (
        default_result["result"]["models"][0]["expected_minimum"]
        == result_with_selection["result"]["models"][0]["expected_minimum"]
    )


def test_pickled_consumption_skips_training():
    """Test that providing extras.pickled skips model retraining (tell() not called)"""
    # First run to get pickled
    first_result = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true"},
    })
    pickled_value = first_result["result"]["pickled"]
    assert len(pickled_value) > 0

    # Second run with pickled - tell() should NOT be called
    with patch("optimizerapi.optimizer.Optimizer.tell") as mock_tell:
        second_result = optimizer.run_optimizer(body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"pickled": pickled_value, "includeModel": "false"},
        })
        mock_tell.assert_not_called()

    assert "result" in second_result
    assert "next" in second_result["result"]
    assert len(second_result["result"]["next"]) > 0


def test_old_format_pickled_falls_back(caplog):
    """A pickled payload that decrypts but isn't the new dict shape falls through."""
    import logging as _logging

    old_format_data = ["some", "old", "data"]
    old_pickled = pickleToString(old_format_data, get_crypto())

    with caplog.at_level(_logging.WARNING, logger="optimizerapi.pickled_state"):
        result = optimizer.run_optimizer(body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"pickled": old_pickled, "includeModel": "false", "graphFormat": "json"},
        })

    assert "result" in result
    assert len(result["result"]["next"]) > 0
    assert result["result"]["extras"]["pickledUsed"] is False
    assert any("bad_structure" in r.message for r in caplog.records)


def test_invalid_pickled_falls_back(caplog):
    """An undecodable pickled string falls through to a full run."""
    import logging as _logging

    with caplog.at_level(_logging.WARNING, logger="optimizerapi.pickled_state"):
        result = optimizer.run_optimizer(body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"pickled": "this_is_not_valid_pickled_data_at_all", "includeModel": "false", "graphFormat": "json"},
        })

    assert "result" in result
    assert len(result["result"]["next"]) > 0
    assert result["result"]["extras"]["pickledUsed"] is False
    assert any("decrypt_failed" in r.message for r in caplog.records)


def test_pickled_response_is_dict_format():
    """Test that pickled response is a dict with keys fingerprint, result, next, optimizer"""
    result = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true", "graphFormat": "json"},
    })
    pickled_value = result["result"]["pickled"]
    assert len(pickled_value) > 0
    unpickled = unpickleFromString(pickled_value, get_crypto())
    assert isinstance(unpickled, dict), f"Expected dict, got {type(unpickled)}"
    assert set(unpickled.keys()) >= {"fingerprint", "result", "next", "optimizer"}
    assert isinstance(unpickled["fingerprint"], str) and len(unpickled["fingerprint"]) == 64


def test_pickled_round_trip():
    """Test that pickled from run 1 can be sent as extras.pickled in run 2"""
    # Run 1
    first_result = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true"},
    })
    pickled_value = first_result["result"]["pickled"]
    assert len(pickled_value) > 0

    # Run 2 with pickled - should produce a valid response
    second_result = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"pickled": pickled_value, "includeModel": "false"},
    })
    assert "result" in second_result
    assert "next" in second_result["result"]
    assert len(second_result["result"]["next"]) > 0
    # Verify plot structure is valid
    assert "plots" in second_result


# Multi-objective 5-dim data from sample-multi.curl
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


def test_pickled_with_selectedPoint():
    """Integration test: pickled from run 1 consumed in run 2 with selectedPoint from pareto front"""
    # Run 1: multi-objective JSON request — get pickled
    run1_result = optimizer.run_optimizer(body={
        "data": sampleMultiObjective5DimData,
        "optimizerConfig": sampleMultiObjective5DimConfig,
        "extras": {
            "experimentSuggestionCount": 1,
            "graphs": ["pareto", "single"],
            "graphFormat": "json",
            "includeModel": "true",
        },
    })
    assert "result" in run1_result
    pickled_value = run1_result["result"]["pickled"]
    assert len(pickled_value) > 0

    # Extract a point from pareto front_x_data
    pareto_plot_entry = next(p for p in run1_result["plots"] if p["id"] == "pareto_data")
    pareto_data = json.loads(pareto_plot_entry["plot"])
    front_x_data = pareto_data["front_x_data"]
    assert len(front_x_data) > 0
    selected_point = front_x_data[0]

    # Run 2: same request + pickled + selectedPoint
    run2_result = optimizer.run_optimizer(body={
        "data": sampleMultiObjective5DimData,
        "optimizerConfig": sampleMultiObjective5DimConfig,
        "extras": {
            "experimentSuggestionCount": 1,
            "graphs": ["pareto", "single"],
            "graphFormat": "json",
            "pickled": pickled_value,
            "selectedPoint": selected_point,
        },
    })

    # Assert valid response
    assert "result" in run2_result
    assert "plots" in run2_result
    assert len(run2_result["plots"]) > 0
    assert "next" in run2_result["result"]
    assert len(run2_result["result"]["next"]) > 0

    # Assert new pickled is present
    new_pickled = run2_result["result"]["pickled"]
    assert len(new_pickled) > 0

    # Assert selectedPoint is reflected in objective_1_0 plot
    obj1_dim0 = next(p for p in run2_result["plots"] if p["id"] == "objective_1_0")
    plot_data = json.loads(obj1_dim0["plot"])
    assert plot_data["data"][3] == selected_point[0]


def test_pickled_consumption_with_include_model_false():
    """Integration test: pickled consumed + includeModel=false → pickled suppressed in response"""
    # Run 1: get pickled
    run1_result = optimizer.run_optimizer(body={
        "data": sampleMultiObjective5DimData,
        "optimizerConfig": sampleMultiObjective5DimConfig,
        "extras": {
            "experimentSuggestionCount": 1,
            "graphs": ["pareto", "single"],
            "graphFormat": "json",
            "includeModel": "true",
        },
    })
    pickled_value = run1_result["result"]["pickled"]
    assert len(pickled_value) > 0

    # Run 2: consume pickled + includeModel=false
    run2_result = optimizer.run_optimizer(body={
        "data": sampleMultiObjective5DimData,
        "optimizerConfig": sampleMultiObjective5DimConfig,
        "extras": {
            "experimentSuggestionCount": 1,
            "graphs": ["pareto", "single"],
            "graphFormat": "json",
            "pickled": pickled_value,
            "includeModel": "false",
        },
    })

    # includeModel=false suppresses pickled
    assert "result" in run2_result
    assert "pickled" in run2_result["result"]
    assert run2_result["result"]["pickled"] == ""

    # Response is otherwise valid
    assert "next" in run2_result["result"]
    assert len(run2_result["result"]["next"]) > 0
    assert "plots" in run2_result
    assert len(run2_result["plots"]) > 0


def test_pickled_used_flag_round_trip():
    """First run has pickledUsed=False; second run with returned pickled has pickledUsed=True."""
    first = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true", "graphFormat": "json"},
    })
    assert first["result"]["extras"]["pickledUsed"] is False
    pickled_value = first["result"]["pickled"]
    assert len(pickled_value) > 0

    second = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true", "pickled": pickled_value, "graphFormat": "json"},
    })
    assert second["result"]["extras"]["pickledUsed"] is True


def test_selectedPoint_with_no_data():
    """Integration test: selectedPoint with empty data — server handles gracefully"""
    selected_point = [50, 833, 150, 60, "Whipped cream"]
    result = optimizer.run_optimizer(body={
        "data": [],
        "optimizerConfig": sampleMultiObjective5DimConfig,
        "extras": {
            "experimentSuggestionCount": 1,
            "graphs": ["pareto", "single"],
            "graphFormat": "json",
            "selectedPoint": selected_point,
        },
    })

    # Server handles gracefully — no exception, valid response
    assert "result" in result
    # No data means no models trained, so no plots
    assert "plots" in result


def test_equivalence_with_and_without_pickled_multi_objective():
    """Same selectedPoint, same data: pickled vs no-pickled produce identical plots (all ids)."""
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
    seed = optimizer.run_optimizer(body=copy.deepcopy({
        **base_body,
        "extras": {**base_body["extras"], "selectedPoint": None},
    }))
    pickled_value = seed["result"]["pickled"]
    assert len(pickled_value) > 0

    # Run A: no pickled (full retrain), with selectedPoint.
    body_no_pickle = copy.deepcopy(base_body)
    result_no_pickle = optimizer.run_optimizer(body=body_no_pickle)

    # Run B: same request + pickled.
    body_with_pickle = copy.deepcopy(base_body)
    body_with_pickle["extras"]["pickled"] = pickled_value
    result_with_pickle = optimizer.run_optimizer(body=body_with_pickle)

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


def test_pickled_fingerprint_mismatch_falls_through(caplog):
    """A pickled produced from one data set is ignored when data changes."""
    import logging as _logging

    seed = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true", "graphFormat": "json"},
    })
    pickled_value = seed["result"]["pickled"]
    assert len(pickled_value) > 0

    altered_data = sampleData + [{"xi": [100, 100, 100, "Mus"], "yi": [0.5]}]

    with caplog.at_level(_logging.WARNING, logger="optimizerapi.pickled_state"):
        result = optimizer.run_optimizer(body={
            "data": altered_data,
            "optimizerConfig": sampleConfig,
            "extras": {"includeModel": "true", "pickled": pickled_value, "graphFormat": "json"},
        })

    assert result["result"]["extras"]["pickledUsed"] is False
    assert any("fingerprint_mismatch" in r.message for r in caplog.records)
    # Response still valid — server fell through to a full run.
    assert "next" in result["result"]
    assert len(result["result"]["next"]) > 0


def test_includeModel_false_with_pickled_logs_chain_break_warning(caplog):
    import logging as _logging

    seed = optimizer.run_optimizer(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true", "graphFormat": "json"},
    })
    pickled_value = seed["result"]["pickled"]

    with caplog.at_level(_logging.WARNING, logger="optimizerapi.optimizer"):
        second = optimizer.run_optimizer(body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"pickled": pickled_value, "includeModel": "false", "graphFormat": "json"},
        })

    assert any("includeModel=false with extras.pickled" in r.message for r in caplog.records)
    # Contract preserved: empty pickled returned.
    assert second["result"]["pickled"] == ""
