"""Pickled-state cache: fingerprint a request, pack/unpack pickled payloads.

The fingerprint binds a pickled blob to the request that produced it, so a
client that sends a stale pickled along with newer data gets a clean fall-
through to a full run instead of silently buggy reuse.
"""

import hashlib
import json


def compute_fingerprint(data, optimizer_config):
    """Return sha256 hex of the canonical-JSON of (data, optimizerConfig).

    Canonical JSON: sorted keys, no whitespace. Numbers are emitted as Python's
    default JSON representation, which is stable for the integer / float values
    that flow through the API.
    """
    payload = {"data": data, "optimizerConfig": optimizer_config}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
