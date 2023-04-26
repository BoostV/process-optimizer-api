"""
Main server
"""
import os
import re
import connexion
from waitress import serve
from flask_cors import CORS
from .securepickle import get_crypto

if __name__ == "__main__":
    # Initialize crypto
    get_crypto()
    app = connexion.FlaskApp(
        __name__, port=9090, specification_dir="./openapi/")
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
            print("CORS: " + cors_origin)
        except re.error:
            print("CORS: failed - the regex might be malformed.")
    else:
        print("CORS: disabled")

    if development:
        app.run()
    else:
        serve(app, listen="*:9090", channel_request_lookahead=1)
