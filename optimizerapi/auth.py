"""Authenitcation module

This module will verify tokens provided bt a Keycloak OpenID server
"""
import logging  # noqa: F401 – used by Task 4 (_LOG)
import os
import secrets

from keycloak import KeycloakOpenID

AUTH_API_KEY = os.getenv("AUTH_API_KEY", "none")
AUTH_SERVER = os.getenv("AUTH_SERVER", None)
AUTH_CLIENT_ID = os.getenv("AUTH_CLIENT_ID", None)
AUTH_CLIENT_SECRET = os.getenv("AUTH_CLIENT_SECRET", None)
AUTH_REALM_NAME = os.getenv("AUTH_REALM_NAME", None)

keycloak_openid = KeycloakOpenID(
    server_url=AUTH_SERVER,
    realm_name=AUTH_REALM_NAME,
    client_id=AUTH_CLIENT_ID,
    client_secret_key=AUTH_CLIENT_SECRET,
)


def token_info(access_token) -> dict:
    """Verify token with authentication server

    Returns
    -------
    dict
        a dictionary containing sub and scope
        None in case of invalid token
    """
    print(access_token)
    if not AUTH_SERVER:
        return {"scope": []}
    token = access_token
    token_data = keycloak_openid.introspect(token)
    if "active" in token_data and token_data["active"]:
        print("OK")
        return token_data
    print("NOT OK")
    print(token_data)
    return None


def apikey_handler(access_token: str) -> dict | None:
    """Verify the API key passed by the client.

    Returns
    -------
    dict
        ``{"scope": []}`` if the supplied key matches the configured
        ``AUTH_API_KEY``.
    None
        If the key is wrong, or if no static-key auth is configured.
    """
    if AUTH_SERVER:
        # OIDC is configured; static-key path is disabled.
        return None
    expected = AUTH_API_KEY.encode("utf-8")
    provided = (access_token or "").encode("utf-8")
    if secrets.compare_digest(expected, provided):
        return {"scope": []}
    return None
