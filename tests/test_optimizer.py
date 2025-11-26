"""
Test main optimizer module
"""

from unittest.mock import patch
import copy
import collections.abc
from optimizerapi import optimizer_handler as optimizer

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
    assert len(result["plots"]) == 2


def test_generates_convergence_plots():
    convergence_config = copy.deepcopy(sampleConfig)
    convergence_config["extras"] = {"graphs": ["convergence"]}
    result = optimizer.run(
        body={"data": sampleData, "optimizerConfig": convergence_config}
    )
    validateResult(result)
    assert len(result["result"]["models"]) > 0
    assert len(result["plots"]) == 2
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
    assert len(result["plots"]) == 2


def test_specifying_empty_extras_preserve_legacy_plotting():
    result = optimizer.run(
        body={"data": sampleData, "optimizerConfig": sampleConfig, "extras": {}}
    )
    validateResult(result)
    assert len(result["result"]["models"]) > 0
    assert len(result["plots"]) == 2


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
        body={"data": sampleMultiObjectiveData, "optimizerConfig": sampleConfig}
    )
    validateResult(result)
    assert len(result["result"]["models"]) > 1
    assert len(result["plots"]) == 5


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
