"""Shared pytest fixtures and session-level configuration."""

import os

import pytest

# A fixed Fernet key used by all tests so that encrypt/decrypt round-trips
# remain stable across multiple get_crypto() calls within a test session.
# Never use this value in production.
_TEST_PICKLE_KEY = "y3kUY6D3DAVy1NR8oK8Q7mmYkuvLtE8buQEO4IMSvOk="


@pytest.fixture(autouse=True, scope="session")
def stable_pickle_key():
    """Set a fixed PICKLE_KEY for all tests.

    Without this, get_crypto() generates a new ephemeral Fernet key on every
    call, so encrypt/decrypt round-trips across two optimizer.run_optimizer() calls (or
    between run_optimizer() and a direct unpickleFromString() call in a test) will fail
    with InvalidToken.  A stable key makes the test environment mirror a real
    deployment where PICKLE_KEY is set in the environment.
    """
    original = os.environ.get("PICKLE_KEY")
    os.environ["PICKLE_KEY"] = _TEST_PICKLE_KEY
    yield _TEST_PICKLE_KEY
    if original is None:
        os.environ.pop("PICKLE_KEY", None)
    else:
        os.environ["PICKLE_KEY"] = original


@pytest.fixture(scope="session")
def app():
    """Create the Flask application for testing.

    This fixture creates a Connexion app with the same configuration
    as the production server, but in test mode.
    """
    from pathlib import Path
    import connexion
    from optimizerapi.securepickle import get_crypto

    # Initialize crypto with the stable key
    get_crypto()

    # Use absolute path to the openapi spec
    api_spec_dir = Path(__file__).parent.parent / "optimizerapi" / "openapi"

    app = connexion.FlaskApp(
        __name__,
        specification_dir=str(api_spec_dir),
    )
    app.add_api("specification.yml", strict_validation=True, validate_responses=True)
    app.app.config["TESTING"] = True

    return app


@pytest.fixture(scope="session")
def app_client(app):
    """Create a test client for the Flask application.

    This client can be used to make HTTP requests to the API endpoints
    as if they were being served by a real HTTP server.
    """
    with app.app.test_client() as client:
        yield client
