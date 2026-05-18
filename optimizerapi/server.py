"""
Main server
"""
import logging
import os
import re

import connexion
from flask_cors import CORS
from waitress import serve

from .securepickle import get_crypto

_LOG = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure root logging once, before any handler is dispatched.

    Level defaults to INFO. Override with the LOG_LEVEL environment
    variable (e.g. LOG_LEVEL=DEBUG for local debugging).
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


if __name__ == "__main__":
    _configure_logging()
    # Initialize crypto
    get_crypto()
    app = connexion.FlaskApp(
        __name__, specification_dir="./openapi/")
    app.add_api("specification.yml", strict_validation=True,
                validate_responses=True)

    DEVELOPMENT = "development"
    flask_env = os.getenv("FLASK_ENV", DEVELOPMENT)
    development = flask_env == DEVELOPMENT
    if development:
        os.environ["FLASK_DEBUG"] = DEVELOPMENT

    # It should be easy to get started developing locally which is the reason
    # why we allow for all origins in development mode.
    ALLOW_ALL_ORIGINS = ".*"
    cors_origin = os.getenv(
        "CORS_ORIGIN", ALLOW_ALL_ORIGINS if development else None)

    # By default we do not want to enable CORS. That should be a conscious
    # descision from the host of the API server. This way we do not expose any
    # additional vulnerabilities by default.
    if cors_origin:
        try:
            # https://connexion.readthedocs.io/en/latest/cookbook.html?highlight=cors#cors-support
            # https://flask-cors.readthedocs.io/en/latest/configuration.html#default-values
            CORS(
                app.app,
                # OPTIONS is required for the preflight request when doing CORS.
                # The HEAD, GET and POST is functionality we want exposed.
                methods=["HEAD", "OPTIONS", "GET", "POST"],
                # re.compile allows for quite complex origin definitions through
                # our environment variable. The List would be cumbersome to
                # parse and the simple string is not enough functionality for
                # what we want to support.
                origins=re.compile(cors_origin),
            )
            _LOG.info("CORS: %s", cors_origin)
        except re.error:
            _LOG.warning("CORS: failed - the regex might be malformed.")
    else:
        _LOG.info("CORS: disabled")

    if development:
        app.run(port=9090)
    else:
        serve(app, listen="*:9090", channel_request_lookahead=1, threads=50)
