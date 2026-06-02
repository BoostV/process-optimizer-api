"""
End-to-end tests for the pareto front exploration feature.

These tests hit the actual HTTP layer using Flask's test client,
verifying the full request/response cycle including authentication,
validation, and the pareto front exploration workflow.
"""

import copy
import json
import pytest

# Multi-objective test data from docs/api-usage.md
MULTI_OBJECTIVE_DATA = [
    {"xi": [16.7, 500, 250, 20, "None"], "yi": [-2, -17]},
    {"xi": [50, 833, 150, 60, "Whipped cream"], "yi": [-3, -6]},
    {"xi": [58.3, 22, 85, 6, "Frosting"], "yi": [-6, -25]},
]

MULTI_OBJECTIVE_CONFIG = {
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

# Numeric-only multi-objective data (the built-in "CFPS multi objective"
# example). Unlike MULTI_OBJECTIVE_DATA above it has no categorical factor, so
# it exercises the all-numeric code path of get_Brownie_Bee_1d_plot — where the
# score histogram (predicted-score distribution at the selected point) used to
# be computed on the *raw* (untransformed) point and therefore never changed
# between Pareto points.
NUMERIC_MULTI_OBJECTIVE_DATA = [
    {"xi": [1, 40, 0.5], "yi": [0.608, 0.0833]},
    {"xi": [5, 120, 2.5], "yi": [1.9085, 2.0833]},
    {"xi": [3, 80, 1.5], "yi": [1.3638, 0.75]},
    {"xi": [5.5, 30, 0.25], "yi": [1.1523, 0.8542]},
    {"xi": [2, 140, 2], "yi": [1.0272, 1.5556]},
    {"xi": [0, 100, 1], "yi": [0.3739, 0.5556]},
    {"xi": [4, 60, 2.75], "yi": [1.2057, 1.3958]},
    {"xi": [3.5, 130, 0.75], "yi": [1.6283, 1.2431]},
    {"xi": [1.5, 70, 2.25], "yi": [0.8189, 0.7986]},
    {"xi": [0.5, 90, 0], "yi": [0.4268, 0.3472]},
]

NUMERIC_MULTI_OBJECTIVE_CONFIG = {
    "baseEstimator": "GP",
    "acqFunc": "EI",
    "initialPoints": 4,
    "kappa": 1.96,
    "xi": 0.01,
    "space": [
        {"type": "continuous", "name": "Magnesium", "from": 0, "to": 6},
        {"type": "discrete", "name": "Potassium", "from": 20, "to": 140},
        {"type": "continuous", "name": "DTT", "from": 0, "to": 3},
    ],
    "constraints": [],
}


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
class TestE2EParetoFront:
    """End-to-end tests for pareto front exploration via HTTP."""

    BASE_URL = "/v1.0/optimizer"

    @pytest.fixture
    def api_key(self):
        """Return the test API key."""
        return "none"

    def build_request(self, data, optimizer_config, extras=None):
        """Build a request payload."""
        payload = {
            "data": data,
            "optimizerConfig": optimizer_config,
        }
        if extras:
            payload["extras"] = extras
        return payload

    def test_health_endpoint(self, app_client):
        """Test that the health endpoint is reachable."""
        response = app_client.get("/v1.0/health")
        assert response.status_code == 200

    def test_initial_multi_objective_run_returns_pareto_data(self, app_client, api_key):
        """Test that an initial multi-objective run includes pareto_data in plots."""
        payload = self.build_request(
            data=MULTI_OBJECTIVE_DATA,
            optimizer_config=MULTI_OBJECTIVE_CONFIG,
            extras={
                "experimentSuggestionCount": 1,
                "graphs": ["pareto", "single"],
                "graphFormat": "json",
            },
        )

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload,
            content_type="application/json",
        )

        assert response.status_code == 200
        result = response.get_json()

        # Verify response structure
        assert "plots" in result
        assert "result" in result
        assert "next" in result["result"]
        assert "pickled" in result["result"]

        # Verify pareto_data plot is present
        plot_ids = [p["id"] for p in result["plots"]]
        assert "pareto_data" in plot_ids, "pareto_data plot should be present in multi-objective response"

        # Verify pareto_data has expected structure
        pareto_plot = next(p for p in result["plots"] if p["id"] == "pareto_data")
        pareto_data = json.loads(pareto_plot["plot"])
        assert "front_y_data" in pareto_data
        assert "front_x_data" in pareto_data
        assert "best_idx" in pareto_data

    def test_pareto_front_x_data_matches_input_dimensions(self, app_client, api_key):
        """Test that front_x_data points have the same dimensionality as the space."""
        payload = self.build_request(
            data=MULTI_OBJECTIVE_DATA,
            optimizer_config=MULTI_OBJECTIVE_CONFIG,
            extras={
                "graphs": ["pareto"],
                "graphFormat": "json",
            },
        )

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload,
            content_type="application/json",
        )

        assert response.status_code == 200
        result = response.get_json()

        pareto_plot = next(p for p in result["plots"] if p["id"] == "pareto_data")
        pareto_data = json.loads(pareto_plot["plot"])

        space_dim = len(MULTI_OBJECTIVE_CONFIG["space"])
        for point in pareto_data["front_x_data"]:
            assert len(point) == space_dim, (
                f"front_x_data point has {len(point)} dimensions, expected {space_dim}"
            )

    def test_selectedPoint_highlights_correct_point(self, app_client, api_key):
        """Test that selectedPoint correctly highlights a specific point in plots."""
        # First, get the pareto front
        payload = self.build_request(
            data=MULTI_OBJECTIVE_DATA,
            optimizer_config=MULTI_OBJECTIVE_CONFIG,
            extras={
                "graphs": ["pareto", "single"],
                "graphFormat": "json",
                "includeModel": "true",
            },
        )

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload,
            content_type="application/json",
        )
        assert response.status_code == 200
        run1 = response.get_json()

        # Extract a point from the pareto front
        pareto_plot = next(p for p in run1["plots"] if p["id"] == "pareto_data")
        pareto_data = json.loads(pareto_plot["plot"])
        selected_point = pareto_data["front_x_data"][0]

        # Now request with selectedPoint
        payload_with_selection = self.build_request(
            data=MULTI_OBJECTIVE_DATA,
            optimizer_config=MULTI_OBJECTIVE_CONFIG,
            extras={
                "graphs": ["single"],
                "graphFormat": "json",
                "selectedPoint": selected_point,
                "includeModel": "false",
            },
        )

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload_with_selection,
            content_type="application/json",
        )
        assert response.status_code == 200
        run2 = response.get_json()

        # Verify selectedPoint is reflected in objective_1_0 plot (dimension 0).
        # In get_Brownie_Bee_1d_plot's output shape, index 3 is the x-coord of
        # the highlight point for the dimension.
        obj1_dim0 = next(p for p in run2["plots"] if p["id"] == "objective_1_0")
        plot_data = json.loads(obj1_dim0["plot"])
        assert plot_data["data"][3] == selected_point[0], (
            "selectedPoint should be reflected in the single plot highlight"
        )

    def test_score_histogram_tracks_selected_point_numeric_space(
        self, app_client, api_key
    ):
        """The score histogram must follow the selected Pareto point.

        Regression for the "histograms never change when clicking the Pareto
        front" bug: get_Brownie_Bee_1d_plot computed the histogram mean/std via
        model.predict() on the *raw* point, but the GP is fitted in transformed
        space. For an all-numeric space the raw point sits far outside the
        normalized domain, so every point collapsed to the prior mean — the
        histogram was identical regardless of selection (while the per-factor
        plots, which transform x_eval themselves, did move).
        """

        def histogram_for(selected_point):
            payload = self.build_request(
                data=NUMERIC_MULTI_OBJECTIVE_DATA,
                optimizer_config=NUMERIC_MULTI_OBJECTIVE_CONFIG,
                extras={
                    "graphs": ["single"],
                    "graphFormat": "json",
                    "selectedPoint": selected_point,
                },
            )
            response = app_client.post(
                f"{self.BASE_URL}?apikey={api_key}",
                json=payload,
                content_type="application/json",
            )
            assert response.status_code == 200
            plots = response.get_json()["plots"]
            # The histogram is the last entry per objective: one plot per space
            # dimension (3) followed by the histogram at index 3.
            out = {}
            for obj in ("objective_1", "objective_2"):
                hist_plot = next(p for p in plots if p["id"] == f"{obj}_3")
                out[obj] = json.loads(hist_plot["plot"])["histogram"]
            return out

        # First fetch the Pareto front and pick two genuinely different
        # trade-offs: best quality vs best cost.
        front_payload = self.build_request(
            data=NUMERIC_MULTI_OBJECTIVE_DATA,
            optimizer_config=NUMERIC_MULTI_OBJECTIVE_CONFIG,
            extras={"graphs": ["pareto"], "graphFormat": "json"},
        )
        front_resp = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=front_payload,
            content_type="application/json",
        )
        assert front_resp.status_code == 200
        pareto = json.loads(
            next(p for p in front_resp.get_json()["plots"] if p["id"] == "pareto_data")[
                "plot"
            ]
        )
        front_x = pareto["front_x_data"]
        front_y = pareto["front_y_data"]
        i_best_quality = min(range(len(front_y)), key=lambda i: front_y[i][0])
        i_best_cost = min(range(len(front_y)), key=lambda i: front_y[i][1])

        # Sanity: the front must actually offer a trade-off, else the test is
        # vacuous.
        assert front_y[i_best_quality][0] != front_y[i_best_cost][0]
        assert front_y[i_best_quality][1] != front_y[i_best_cost][1]

        at_quality = histogram_for(front_x[i_best_quality])
        at_cost = histogram_for(front_x[i_best_cost])

        for obj in ("objective_1", "objective_2"):
            assert at_quality[obj]["mean"] != at_cost[obj]["mean"], (
                f"{obj} histogram mean did not change between two different "
                f"Pareto points (frozen histogram bug)"
            )

        # And the histogram mean should track the predicted score at the
        # selected point (front_y), not collapse to a constant prior mean.
        assert at_quality["objective_1"]["mean"] == pytest.approx(
            front_y[i_best_quality][0], abs=0.1
        )
        assert at_cost["objective_2"]["mean"] == pytest.approx(
            front_y[i_best_cost][1], abs=0.1
        )

    def test_full_pareto_exploration_workflow(self, app_client, api_key):
        """
        Test the complete pareto exploration workflow:
        1. Initial run to get pareto front and pickled state
        2. User selects a point from pareto front
        3. Re-request with selectedPoint + pickled for fast response
        4. Verify pickledUsed is True (fast path engaged)
        """
        # Step 1: Initial run
        payload = self.build_request(
            data=MULTI_OBJECTIVE_DATA,
            optimizer_config=MULTI_OBJECTIVE_CONFIG,
            extras={
                "experimentSuggestionCount": 1,
                "graphs": ["pareto", "single"],
                "graphFormat": "json",
                "includeModel": "true",
            },
        )

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload,
            content_type="application/json",
        )
        assert response.status_code == 200
        run1 = response.get_json()

        # Verify initial run used full training (not cache)
        assert run1["result"]["extras"]["pickledUsed"] is False, (
            "Initial run should not use pickled cache"
        )

        # Extract pickled and a point from pareto front
        pickled_value = run1["result"]["pickled"]
        assert len(pickled_value) > 0, "pickled should be present in response"

        pareto_plot = next(p for p in run1["plots"] if p["id"] == "pareto_data")
        pareto_data = json.loads(pareto_plot["plot"])
        selected_point = pareto_data["front_x_data"][0]

        # Step 2: Re-request with selectedPoint + pickled
        payload_with_cache = self.build_request(
            data=MULTI_OBJECTIVE_DATA,
            optimizer_config=MULTI_OBJECTIVE_CONFIG,
            extras={
                "experimentSuggestionCount": 1,
                "graphs": ["pareto", "single"],
                "graphFormat": "json",
                "selectedPoint": selected_point,
                "pickled": pickled_value,
                "includeModel": "true",
            },
        )

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload_with_cache,
            content_type="application/json",
        )
        assert response.status_code == 200
        run2 = response.get_json()

        # Verify fast path was used
        assert run2["result"]["extras"]["pickledUsed"] is True, (
            "Second run with pickled should use fast path"
        )

        # Verify response is valid and selectedPoint is applied
        assert "next" in run2["result"]
        assert len(run2["result"]["next"]) > 0

        # Index 3 is the highlight x-coord in get_Brownie_Bee_1d_plot's output.
        obj1_dim0 = next(p for p in run2["plots"] if p["id"] == "objective_1_0")
        plot_data = json.loads(obj1_dim0["plot"])
        assert plot_data["data"][3] == selected_point[0]

    def test_equivalence_with_and_without_pickled(self, app_client, api_key):
        """
        Test that pickled vs no-pickled produce identical plots when
        selectedPoint, data, and config are the same.
        """
        base_payload = self.build_request(
            data=MULTI_OBJECTIVE_DATA,
            optimizer_config=MULTI_OBJECTIVE_CONFIG,
            extras={
                "graphs": ["single", "pareto"],
                "graphFormat": "json",
                "selectedPoint": [50, 833, 150, 60, "Whipped cream"],
                "includeModel": "true",
            },
        )

        # Run without pickled
        response_no_pickle = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=base_payload,
            content_type="application/json",
        )
        assert response_no_pickle.status_code == 200
        result_no_pickle = response_no_pickle.get_json()

        # Get pickled from the response for the next request
        pickled_value = result_no_pickle["result"]["pickled"]

        # Run with pickled
        payload_with_pickle = copy.deepcopy(base_payload)
        payload_with_pickle["extras"]["pickled"] = pickled_value

        response_with_pickle = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload_with_pickle,
            content_type="application/json",
        )
        assert response_with_pickle.status_code == 200
        result_with_pickle = response_with_pickle.get_json()

        # Verify fast path was engaged
        assert result_with_pickle["result"]["extras"]["pickledUsed"] is True
        assert result_no_pickle["result"]["extras"]["pickledUsed"] is False

        # Equivalence contract (docs §8): same plots and same next.
        assert result_no_pickle["result"]["next"] == result_with_pickle["result"]["next"], (
            "result.next should be identical with and without pickled"
        )

        plots_no_pickle = {p["id"]: p["plot"] for p in result_no_pickle["plots"]}
        plots_with_pickle = {p["id"]: p["plot"] for p in result_with_pickle["plots"]}

        assert set(plots_no_pickle.keys()) == set(plots_with_pickle.keys()), (
            "Plot IDs should match between pickled and non-pickled runs"
        )

        for plot_id in plots_no_pickle:
            assert plots_no_pickle[plot_id] == plots_with_pickle[plot_id], (
                f"Plot {plot_id} content should be identical with and without pickled"
            )

    def test_pareto_data_structure(self, app_client, api_key):
        """Test the detailed structure of pareto_data response."""
        payload = self.build_request(
            data=MULTI_OBJECTIVE_DATA,
            optimizer_config=MULTI_OBJECTIVE_CONFIG,
            extras={
                "graphs": ["pareto"],
                "graphFormat": "json",
            },
        )

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload,
            content_type="application/json",
        )
        assert response.status_code == 200
        result = response.get_json()

        pareto_plot = next(p for p in result["plots"] if p["id"] == "pareto_data")
        pareto_data = json.loads(pareto_plot["plot"])

        # All fields emit_pareto_data writes (docs §7 "per-objective uncertainty"
        # corresponds to obj1_error / obj2_error).
        assert set(pareto_data.keys()) >= {
            "front_x_data",
            "front_y_data",
            "obj1_error",
            "obj2_error",
            "best_idx",
        }

        # front_y_data is a list of [y_obj1, y_obj2] for each pareto point
        assert isinstance(pareto_data["front_y_data"], list)
        assert len(pareto_data["front_y_data"]) > 0  # At least one point on pareto front
        num_front_points = len(pareto_data["front_y_data"])
        for point in pareto_data["front_y_data"]:
            assert isinstance(point, list)
            assert len(point) == 2, f"Each point should have 2 objectives, got {len(point)}"

        # front_x_data should have shape (num_points, num_dimensions)
        assert isinstance(pareto_data["front_x_data"], list)
        assert len(pareto_data["front_x_data"]) == num_front_points, (
            "front_x_data and front_y_data should have same number of points"
        )
        for point in pareto_data["front_x_data"]:
            assert len(point) == len(MULTI_OBJECTIVE_CONFIG["space"])

        # Per-objective uncertainty arrays line up with the front
        assert isinstance(pareto_data["obj1_error"], list)
        assert isinstance(pareto_data["obj2_error"], list)
        assert len(pareto_data["obj1_error"]) == num_front_points
        assert len(pareto_data["obj2_error"]) == num_front_points

        # best_idx should be a valid index
        assert 0 <= pareto_data["best_idx"] < num_front_points

    def test_pareto_with_png_format(self, app_client, api_key):
        """PNG mode never emits pareto_data (it is JSON-only)."""
        payload = self.build_request(
            data=MULTI_OBJECTIVE_DATA,
            optimizer_config=MULTI_OBJECTIVE_CONFIG,
            extras={
                "graphs": ["pareto", "single"],
                "graphFormat": "png",
            },
        )

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload,
            content_type="application/json",
        )
        assert response.status_code == 200
        result = response.get_json()

        plot_ids = [p["id"] for p in result["plots"]]
        # PNG path produces single plots per model, never a pareto_data entry.
        assert "pareto_data" not in plot_ids
        assert len(result["plots"]) > 0
        assert "next" in result["result"]

    def test_empty_data_with_pareto_request(self, app_client, api_key):
        """Empty data + pareto in graphs returns initial-point suggestions without crashing.

        Note: with data=[] there are no yi vectors, so n_objectives defaults to 1
        and the pareto code path is never entered. This test only guards the
        empty-data path; the pareto-specific behavior is covered elsewhere.
        """
        payload = self.build_request(
            data=[],  # No data yet
            optimizer_config=MULTI_OBJECTIVE_CONFIG,
            extras={
                "graphs": ["pareto", "single"],
                "graphFormat": "json",
            },
        )

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload,
            content_type="application/json",
        )

        # Should return 200 with initial point suggestions
        assert response.status_code == 200
        result = response.get_json()
        assert "result" in result
        assert "next" in result["result"]

    def test_missing_api_key_returns_401(self, app_client):
        """Test that missing API key is rejected with 401 Unauthorized."""
        payload = self.build_request(
            data=MULTI_OBJECTIVE_DATA,
            optimizer_config=MULTI_OBJECTIVE_CONFIG,
            extras={"graphs": ["pareto"]},
        )

        # No apikey query parameter
        response = app_client.post(
            self.BASE_URL,
            json=payload,
            content_type="application/json",
        )

        assert response.status_code == 401

    def test_invalid_optimizer_config_returns_400(self, app_client, api_key):
        """Missing required optimizerConfig fields are rejected at validation time as 400."""
        payload = {
            "data": MULTI_OBJECTIVE_DATA,
            "optimizerConfig": {
                "invalid_field": "value",
                # Missing required fields (space, baseEstimator, ...)
            },
        }

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload,
            content_type="application/json",
        )

        assert response.status_code == 400
        result = response.get_json()
        # Connexion returns RFC 7807 problem+json
        assert "title" in result and "detail" in result
        assert result.get("status") == 400

    def test_single_objective_does_not_include_pareto(self, app_client, api_key):
        """Test that single-objective optimization doesn't include pareto_data."""
        single_objective_data = [
            {"xi": [651, 56, 722, "Ræv"], "yi": [1]},
            {"xi": [651, 42, 722, "Ræv"], "yi": [0.2]},
        ]

        single_objective_config = {
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

        payload = self.build_request(
            data=single_objective_data,
            optimizer_config=single_objective_config,
            extras={
                "graphs": ["single", "pareto"],  # Requesting pareto but it's single-objective
                "graphFormat": "json",
            },
        )

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload,
            content_type="application/json",
        )

        assert response.status_code == 200
        result = response.get_json()

        # pareto_data should NOT be present for single-objective
        plot_ids = [p["id"] for p in result["plots"]]
        assert "pareto_data" not in plot_ids, (
            "pareto_data should not be present for single-objective optimization"
        )
