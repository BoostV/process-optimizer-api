"""
End-to-end tests for the pareto front exploration feature.

These tests hit the actual HTTP layer using Flask's test client,
verifying the full request/response cycle including authentication,
validation, and the pareto front exploration workflow.
"""

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

        # Verify selectedPoint is reflected in objective_1_0 plot (dimension 0)
        obj1_dim0 = next(p for p in run2["plots"] if p["id"] == "objective_1_0")
        plot_data = json.loads(obj1_dim0["plot"])
        assert plot_data["data"][3] == selected_point[0], (
            "selectedPoint should be reflected in the single plot highlight"
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
        payload_with_pickle = json.loads(json.dumps(base_payload))  # deep copy
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

        # Compare plots - should be identical
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

        # Required fields
        assert "front_y_data" in pareto_data
        assert "front_x_data" in pareto_data
        assert "best_idx" in pareto_data

        # front_y_data is a list of [y_obj1, y_obj2] for each pareto point
        assert isinstance(pareto_data["front_y_data"], list)
        assert len(pareto_data["front_y_data"]) > 0  # At least one point on pareto front
        # Each point should have 2 objectives
        for point in pareto_data["front_y_data"]:
            assert isinstance(point, list)
            assert len(point) == 2, f"Each point should have 2 objectives, got {len(point)}"

        # front_x_data should have shape (num_points, num_dimensions)
        assert isinstance(pareto_data["front_x_data"], list)
        assert len(pareto_data["front_x_data"]) == len(pareto_data["front_y_data"]), (
            "front_x_data and front_y_data should have same number of points"
        )
        for point in pareto_data["front_x_data"]:
            assert len(point) == len(MULTI_OBJECTIVE_CONFIG["space"])

        # best_idx should be a valid index
        num_front_points = len(pareto_data["front_x_data"])
        assert 0 <= pareto_data["best_idx"] < num_front_points

    def test_pareto_with_png_format(self, app_client, api_key):
        """Test that pareto plots work with PNG format (base64 encoded)."""
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

        # Pareto plot is included in PNG mode
        plot_ids = [p["id"] for p in result["plots"]]
        # In non-JSON mode (graphFormat: png), the pareto plot is included but in PNG format
        # Check that we have plots and response is valid
        assert len(result["plots"]) > 0
        assert "result" in result
        assert "next" in result["result"]

    def test_empty_data_with_pareto_request(self, app_client, api_key):
        """Test that requesting pareto with empty data is handled gracefully."""
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

    def test_invalid_optimizer_config_returns_500(self, app_client, api_key):
        """Test that invalid optimizer config (missing required fields) returns 500.
        
        Note: The server currently returns 500 for missing required fields in optimizerConfig.
        This is a known limitation - the validation could be improved to return 400.
        """
        payload = {
            "data": MULTI_OBJECTIVE_DATA,
            "optimizerConfig": {
                "invalid_field": "value",
                # Missing required "space" field
            },
        }

        response = app_client.post(
            f"{self.BASE_URL}?apikey={api_key}",
            json=payload,
            content_type="application/json",
        )

        # Server returns 500 for this type of validation error
        assert response.status_code == 500
        result = response.get_json()
        # Connexion returns a standard problem+json shape with title/detail
        assert "title" in result and "detail" in result

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
