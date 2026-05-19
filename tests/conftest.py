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
