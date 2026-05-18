"""Fernet crypto handle factory.

Resolution order for the key:
    1. ``key`` argument (highest priority).
    2. ``PICKLE_KEY`` environment variable.
    3. Generate a new ephemeral key and log a WARNING.

The ephemeral path is intended for local development only. In any
environment where pickled state must survive a restart, ``PICKLE_KEY``
must be set explicitly. This function no longer mutates ``os.environ``,
so caller environments are unchanged.
"""

import logging
import os

from cryptography.fernet import Fernet

_LOG = logging.getLogger(__name__)


def get_crypto(key=None):
    """Return a Fernet crypto handle.

    See the module docstring for the key-resolution order.
    """
    if key is None:
        key = os.getenv("PICKLE_KEY")
    if key is None:
        key = Fernet.generate_key()
        _LOG.warning(
            "No PICKLE_KEY set; generated an ephemeral key. Set "
            "PICKLE_KEY=%s in the environment to persist pickled state "
            "across restarts.",
            key.decode("utf-8"),
        )
    return Fernet(key)
