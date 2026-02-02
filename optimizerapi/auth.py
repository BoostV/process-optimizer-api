"""Authentication module for FastAPI

This module provides authentication via:
- Keycloak OAuth2 token introspection
- API key authentication (query parameter or header)
"""
import os
from typing import Optional
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyQuery, APIKeyHeader
from keycloak import KeycloakOpenID

# Environment variables
AUTH_API_KEY = os.getenv("AUTH_API_KEY", "none")
AUTH_SERVER = os.getenv("AUTH_SERVER", None)
AUTH_CLIENT_ID = os.getenv("AUTH_CLIENT_ID", None)
AUTH_CLIENT_SECRET = os.getenv("AUTH_CLIENT_SECRET", None)
AUTH_REALM_NAME = os.getenv("AUTH_REALM_NAME", None)

# Lazy initialization of Keycloak client
_keycloak_openid: Optional[KeycloakOpenID] = None


def get_keycloak_client() -> KeycloakOpenID | None:
    """Get or create Keycloak OpenID client (lazy initialization)
    
    Returns
    -------
    KeycloakOpenID | None
        Keycloak client if AUTH_SERVER is set, None otherwise
    """
    global _keycloak_openid
    if AUTH_SERVER is None:
        return None
    
    if _keycloak_openid is None:
        _keycloak_openid = KeycloakOpenID(
            server_url=AUTH_SERVER,
            realm_name=AUTH_REALM_NAME,
            client_id=AUTH_CLIENT_ID,
            client_secret_key=AUTH_CLIENT_SECRET,
        )
    return _keycloak_openid


# FastAPI Security schemes
api_key_query = APIKeyQuery(name="apikey", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_oauth2_token(access_token: str) -> dict | None:
    """Verify OAuth2 token with Keycloak introspection
    
    Parameters
    ----------
    access_token : str
        Bearer token to verify
        
    Returns
    -------
    dict | None
        Token data if valid and active, None otherwise
    """
    keycloak_client = get_keycloak_client()
    if keycloak_client is None:
        return None
    
    try:
        print(access_token)
        token_data = keycloak_client.introspect(access_token)
        if "active" in token_data and token_data["active"]:
            print("OK")
            return token_data
        print("NOT OK")
        print(token_data)
        return None
    except Exception as e:
        print(f"Token introspection error: {e}")
        return None


def verify_api_key(api_key: str) -> bool:
    """Verify API key against environment variable
    
    Parameters
    ----------
    api_key : str
        API key to verify
        
    Returns
    -------
    bool
        True if API key matches AUTH_API_KEY, False otherwise
    """
    return AUTH_API_KEY != "none" and AUTH_API_KEY == api_key


async def get_api_key(
    query_key: Optional[str] = Security(api_key_query),
    header_key: Optional[str] = Security(api_key_header)
) -> dict:
    """FastAPI dependency for authentication
    
    Tries API key authentication (query parameter or header) first.
    If no AUTH_SERVER is configured, allows bypass.
    
    Parameters
    ----------
    query_key : str | None
        API key from query parameter (?apikey=...)
    header_key : str | None
        API key from header (X-API-Key: ...)
        
    Returns
    -------
    dict
        Token info dictionary (empty dict for API key auth or bypass)
        
    Raises
    ------
    HTTPException
        401 Unauthorized if authentication fails
    """
    # Auth bypass when AUTH_SERVER not set and no API key configured
    if not AUTH_SERVER and AUTH_API_KEY == "none":
        return {"scope": []}
    
    # Try API key from query parameter
    if query_key and verify_api_key(query_key):
        return {"scope": []}
    
    # Try API key from header
    if header_key and verify_api_key(header_key):
        return {"scope": []}
    
    # No valid authentication provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key"
    )
