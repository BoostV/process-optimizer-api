"""Authenitcation module

This module will verify tokens provided bt a Keycloak OpenID server
"""
import logging
import os
import secrets

from keycloak import KeycloakOpenID

AUTH_API_KEY = os.getenv("AUTH_API_KEY", "none")
AUTH_SERVER = os.getenv("AUTH_SERVER", None)
FLASK_ENV = os.getenv("FLASK_ENV", "development")

_DEFAULT_APIKEY = "none"  # sentinel: matches AUTH_API_KEY default; never accept in production
AUTH_CLIENT_ID = os.getenv("AUTH_CLIENT_ID", None)
AUTH_CLIENT_SECRET = os.getenv("AUTH_CLIENT_SECRET", None)
AUTH_REALM_NAME = os.getenv("AUTH_REALM_NAME", None)

keycloak_openid = KeycloakOpenID(
    server_url=AUTH_SERVER,
    realm_name=AUTH_REALM_NAME,
    client_id=AUTH_CLIENT_ID,
    client_secret_key=AUTH_CLIENT_SECRET,
)

_LOG = logging.getLogger(__name__)


def token_info(access_token: str) -> dict | None:
    """Verify a bearer token against the configured Keycloak server.

    Returns
    -------
    dict
        Token data from Keycloak introspection when the token is active.
        If no OIDC server is configured, returns ``{"scope": []}``.
    None
        If the server reports the token as inactive.
    """
    if not AUTH_SERVER:
        return {"scope": []}
    token_data = keycloak_openid.introspect(access_token)
    if token_data.get("active"):
        _LOG.debug("token accepted")
        return token_data
    _LOG.warning("token rejected by Keycloak")
    return None


def apikey_handler(access_token: str) -> dict | None:
    """Verify the API key passed by the client.

    Returns
    -------
    dict
        ``{"scope": []}`` if the supplied key matches the configured
        ``AUTH_API_KEY``.
    None
        If the key is wrong, OIDC is configured (OIDC handles this path),
        or the operator has not configured a real key in production.
    """
    if AUTH_SERVER:
        return None
    # In production we refuse the unconfigured default value, even if it
    # technically matches the request — operators should set a real key.
    if FLASK_ENV == "production" and AUTH_API_KEY == _DEFAULT_APIKEY:
        return None
    expected = AUTH_API_KEY.encode("utf-8")
    provided = (access_token or "").encode("utf-8")
    if secrets.compare_digest(expected, provided):
        return {"scope": []}
    return None
