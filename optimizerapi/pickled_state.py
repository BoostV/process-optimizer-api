"""Pickled-state cache: fingerprint a request, pack/unpack pickled payloads.

The fingerprint binds a pickled blob to the request that produced it, so a
client that sends a stale pickled along with newer data gets a clean fall-
through to a full run instead of silently buggy reuse.
"""

import hashlib
import json
import logging

from .securepickle import pickleToString, unpickleFromString

_LOG = logging.getLogger(__name__)

_REQUIRED_KEYS = ("fingerprint", "result", "next", "optimizer")


def compute_fingerprint(data, optimizer_config):
    """Return sha256 hex of the canonical-JSON of (data, optimizerConfig).

    Canonical JSON: sorted keys, no whitespace. Numbers are emitted as Python's
    default JSON representation, which is stable for the integer / float values
    that flow through the API.
    """
    payload = {"data": data, "optimizerConfig": optimizer_config}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def pack(*, result, next_points, optimizer, fingerprint, crypto):
    """Encrypt a pickled cache payload for the given fingerprint."""
    payload = {
        "fingerprint": fingerprint,
        "result": result,
        "next": next_points,
        "optimizer": optimizer,
    }
    return pickleToString(payload, crypto)


def unpack_if_valid(blob, *, expected_fingerprint, crypto):
    """Decrypt and validate a pickled cache payload.

    Returns the payload dict on success, or None if anything is off. Any
    failure is logged once at WARNING with a reason tag in the message:
    decrypt_failed | bad_structure | fingerprint_mismatch.
    """
    if not blob:
        return None
    try:
        payload = unpickleFromString(blob, crypto)
    except Exception:
        _LOG.warning("pickled cache ignored: decrypt_failed")
        return None
    if not isinstance(payload, dict) or not all(k in payload for k in _REQUIRED_KEYS):
        _LOG.warning("pickled cache ignored: bad_structure")
        return None
    if payload["fingerprint"] != expected_fingerprint:
        _LOG.warning("pickled cache ignored: fingerprint_mismatch")
        return None
    return payload
