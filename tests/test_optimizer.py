"""
Test main optimizer module
"""

from unittest.mock import patch
import copy
import collections.abc
import json
from optimizerapi import optimizer_handler as optimizer
from optimizerapi.securepickle import get_crypto, pickleToString, unpickleFromString

#  {'data': [{'xi': [651, 56, 722, 'Ræv'], 'yi': 1}, {'xi': [651, 42, 722, 'Ræv'], 'yi': 0.2}], 'optimizerConfig': {'baseEstimator': 'GP', 'acqFunc': 'gp_hedge', 'initialPoints': 5, 'kappa': 1.96, 'xi': 0.012, 'space': [{'type': 'numeric', 'name': 'Sukker', 'from': 0, 'to': 1000}, {'type': 'numeric', 'name': 'Peber', 'from': 0, 'to': 1000}, {'type': 'numeric', 'name': 'Hvedemel', 'from': 0, 'to': 1000}, {'type': 'category', 'name': 'Kunde', 'categories': ['Mus', 'Ræv']}]}}
#   'data': [{'xi': [0, 5, 'Rød'], 'yi': 10}, {'xi': [5, 8.33, 'Hvid'], 'yi': 3}, {'xi': [10, 1.66, 'Rød'], 'yi': 5}],
#   'optimizerConfig': {'baseEstimator': 'GP', 'acqFunc': 'gp_hedge', 'initialPoints': 3, 'kappa': 1.96, 'xi': 0.01,
#   'space': [{'type': 'discrete', 'name': 'Alkohol', 'from': 0, 'to': 10}, {'type': 'continuous', 'name': 'Vand', 'from': 0, 'to': 10}, {'type': 'category', 'name': 'Farve', 'categories': ['Rød', 'Hvid']}]}}                                                                                                                                                  Received extras {'experimentSuggestionCount': 2}

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
    result = optimizer.run(body={"data": [], "optimizerConfig": sampleConfig})
    validateResult(result)
    assert len(result["plots"]) == 0


def test_generates_plots_when_run_with_more_than_initialPoints_samples():
    result = optimizer.run(body={"data": sampleData, "optimizerConfig": sampleConfig})
    validateResult(result)
    assert len(result["result"]["models"]) > 0
    assert len(result["plots"]) == 7


def test_generates_convergence_plots():
    convergence_config = copy.deepcopy(sampleConfig)
    result = optimizer.run(
        body={"data": sampleData, "optimizerConfig": convergence_config, "extras": {"graphs": ["convergence"]}}
    )
    validateResult(result)
    assert len(result["result"]["models"]) > 0
    assert len(result["plots"]) == 1
    assert result["plots"][0]["id"] == "convergence_0"


def test_specifying_png_plots():
    result = optimizer.run(
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
    result = optimizer.run(
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
    result = optimizer.run(
        body={"data": sampleData, "optimizerConfig": sampleConfig, "extras": {}}
    )
    validateResult(result)
    assert len(result["result"]["models"]) > 0
    assert len(result["plots"]) == 7


def test_deselecting_plots():
    # If graphFormat is none, no plots should be returned. This should be faster.
    result = optimizer.run(
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
    result = optimizer.run(
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
    result = optimizer.run(
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
    result = optimizer.run(
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
    result = optimizer.run(
        body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"includeModel": "true"},
        }
    )
    assert "pickled" in result["result"]
    assert len(result["result"]["pickled"]) > 0


def test_expected_minimum_contains_std_deviation():
    result = optimizer.run(body={"data": sampleData, "optimizerConfig": sampleConfig})
    assert "expected_minimum" in result["result"]
    expected_minimum = result["result"]["expected_minimum"]
    assert isinstance(expected_minimum[1], collections.abc.Sequence)


@patch("optimizerapi.optimizer.Optimizer")
def test_when_using_constraints_set_constraints_should_be_called(mock):
    instance = mock.return_value
    request = brownie_with_constraints
    optimizer.run(body=request)
    instance.set_constraints.assert_called_once()


@patch("optimizerapi.optimizer.Optimizer")
def test_when_not_using_constraints_set_constraints_should_not_be_called(mock):
    instance = mock.return_value
    request = brownie_without_constraints
    optimizer.run(body=request)
    instance.set_constraints.assert_not_called()


@patch("optimizerapi.optimizer.Optimizer")
def test_when_using_constraints_strategy_cl_min_should_be_used(mock):
    instance = mock.return_value
    request = brownie_with_constraints
    optimizer.run(body=request)
    instance.ask.assert_called_once_with(n_points=3, strategy="cl_min")


@patch("optimizerapi.optimizer.Optimizer")
def test_when_not_using_constraints_standard_strategy_should_be_used(mock):
    instance = mock.return_value
    request = brownie_without_constraints
    optimizer.run(body=request)
    instance.ask.assert_called_once_with(n_points=3)


def test_selectedPoint_single_objective_json():
    default_result = optimizer.run(body={
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
    result = optimizer.run(body={
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
    result = optimizer.run(body={
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


def test_no_selectedPoint_preserves_default():
    result = optimizer.run(body={
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
    default_result = optimizer.run(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"graphFormat": "json", "graphs": ["single"], "includeModel": "false"},
    })
    selected_point = [651, 56, 722, "Ræv"]
    result_with_selection = optimizer.run(body={
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
    first_result = optimizer.run(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true"},
    })
    pickled_value = first_result["result"]["pickled"]
    assert len(pickled_value) > 0

    # Second run with pickled - tell() should NOT be called
    with patch("optimizerapi.optimizer.Optimizer.tell") as mock_tell:
        second_result = optimizer.run(body={
            "data": sampleData,
            "optimizerConfig": sampleConfig,
            "extras": {"pickled": pickled_value, "includeModel": "false"},
        })
        mock_tell.assert_not_called()

    assert "result" in second_result
    assert "next" in second_result["result"]
    assert len(second_result["result"]["next"]) > 0


def test_old_format_pickled_falls_back():
    """Test that old-format pickled (list) causes fallback — server returns valid response"""
    old_format_data = ["some", "old", "data"]
    old_pickled = pickleToString(old_format_data, get_crypto())
    result = optimizer.run(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"pickled": old_pickled, "includeModel": "false"},
    })
    assert "result" in result
    assert "next" in result["result"]
    assert len(result["result"]["next"]) > 0


def test_invalid_pickled_falls_back():
    """Test that invalid pickled string causes silent fallback to full training run"""
    result = optimizer.run(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"pickled": "this_is_not_valid_pickled_data_at_all", "includeModel": "false"},
    })
    assert "result" in result
    assert "next" in result["result"]
    assert len(result["result"]["next"]) > 0


def test_pickled_response_is_dict_format():
    """Test that pickled response is a dict with keys result, next, optimizer"""
    result = optimizer.run(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true"},
    })
    pickled_value = result["result"]["pickled"]
    assert len(pickled_value) > 0
    unpickled = unpickleFromString(pickled_value, get_crypto())
    # Currently pickled is a list - this should FAIL
    assert isinstance(unpickled, dict), f"Expected dict, got {type(unpickled)}"
    assert "result" in unpickled
    assert "next" in unpickled
    assert "optimizer" in unpickled


def test_pickled_round_trip():
    """Test that pickled from run 1 can be sent as extras.pickled in run 2"""
    # Run 1
    first_result = optimizer.run(body={
        "data": sampleData,
        "optimizerConfig": sampleConfig,
        "extras": {"includeModel": "true"},
    })
    pickled_value = first_result["result"]["pickled"]
    assert len(pickled_value) > 0

    # Run 2 with pickled - should produce a valid response
    second_result = optimizer.run(body={
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
    run1_result = optimizer.run(body={
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
    run2_result = optimizer.run(body={
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
    run1_result = optimizer.run(body={
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
    run2_result = optimizer.run(body={
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


def test_selectedPoint_with_no_data():
    """Integration test: selectedPoint with empty data — server handles gracefully"""
    selected_point = [50, 833, 150, 60, "Whipped cream"]
    result = optimizer.run(body={
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
