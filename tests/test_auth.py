"""Tests for the API-key handler."""

from unittest.mock import patch


def test_correct_apikey_returns_scope_dict():
    """A request with the configured API key returns a scope dict."""
    with patch("optimizerapi.auth.AUTH_API_KEY", "secret-key"), \
         patch("optimizerapi.auth.AUTH_SERVER", None):
        from optimizerapi import auth
        result = auth.apikey_handler("secret-key")
    assert result == {"scope": []}


def test_wrong_apikey_returns_none():
    """An incorrect API key is rejected."""
    with patch("optimizerapi.auth.AUTH_API_KEY", "secret-key"), \
         patch("optimizerapi.auth.AUTH_SERVER", None):
        from optimizerapi import auth
        result = auth.apikey_handler("not-the-key")
    assert result is None


def test_apikey_handler_uses_constant_time_comparison():
    """The handler must compare keys via secrets.compare_digest."""
    from optimizerapi import auth
    import secrets

    with patch("optimizerapi.auth.AUTH_API_KEY", "secret-key"), \
         patch("optimizerapi.auth.AUTH_SERVER", None), \
         patch.object(secrets, "compare_digest", wraps=secrets.compare_digest) as mock_cmp:
        auth.apikey_handler("secret-key")
    assert mock_cmp.called, "apikey_handler must use secrets.compare_digest"
