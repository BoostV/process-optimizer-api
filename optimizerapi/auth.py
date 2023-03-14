"""Authenitcation module

This module will verify tokens provided bt a Keycloak OpenID server
"""
import os
from keycloak import KeycloakOpenID

AUTH_API_KEY = os.getenv("AUTH_API_KEY", '')
AUTH_SERVER = os.getenv("AUTH_SERVER", None)
AUTH_CLIENT_ID = os.getenv("AUTH_CLIENT_ID", None)
AUTH_CLIENT_SECRET = os.getenv("AUTH_CLIENT_SECRET", None)
AUTH_REALM_NAME = os.getenv("AUTH_REALM_NAME", None)

keycloak_openid = KeycloakOpenID(server_url=AUTH_SERVER,
                                 realm_name=AUTH_REALM_NAME,
                                 client_id=AUTH_CLIENT_ID,
                                 client_secret_key=AUTH_CLIENT_SECRET
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
        return {'scope': []}
    token = access_token
    token_data = keycloak_openid.introspect(token)
    if 'active' in token_data and token_data['active']:
        print('OK')
        return token_data
    print('NOT OK')
    print(token_data)
    return None


def apikey_handler(access_token) -> dict:
    """Verify API key based on environment variable

    Returns
    -------
    dict
        a dictionary containing sub and scope
        None in case of invalid token
    """
    if not AUTH_SERVER and AUTH_API_KEY == access_token:
        return {'scope': []}
    return None
