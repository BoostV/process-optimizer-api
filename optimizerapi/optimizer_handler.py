"""ProcessOptimizer web request handler

This file contains the main HTTP request handlers for exposing the ProcessOptimizer API.
The handler functions are mapped to the OpenAPI specification through the "operationId" field
in the specification.yml file found in the folder "openapi" in the root of this project.
"""

import hashlib
import json
import logging
import os
import time
from typing import TYPE_CHECKING

from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError
from rq.command import send_stop_job_command
from redis import Redis
import connexion
from .optimizer import run as handle_run

if TYPE_CHECKING:
    from .types import RequestBody, ResponseEnvelope


def _parse_env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean-ish env var.

    Accepts "true", "1", "yes" (case-insensitive) as True.
    Anything else — including unset or "false" — is False.
    """
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("true", "1", "yes")


def _resolve_disconnect_check():
    """Return a callable that reports whether the client has disconnected.

    Outside of a request context (e.g. unit tests) or when running under
    a server that doesn't expose ``waitress.client_disconnected``, this
    returns a no-op that always says "still connected".
    """
    try:
        env = connexion.request.environ
    except RuntimeError:
        return lambda: False
    return env.get("waitress.client_disconnected", lambda: False)


_LOG = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
_LOG.info("Connecting to %s", REDIS_URL)
redis = Redis.from_url(REDIS_URL)
if "REDIS_TTL" in os.environ:
    TTL = int(os.environ["REDIS_TTL"])
else:
    TTL = 500
if "WORKER_TIMEOUT" in os.environ:
    WORKER_TIMEOUT = os.environ["WORKER_TIMEOUT"]
else:
    WORKER_TIMEOUT = "180"

queue = Queue(connection=redis)


def run(body: "RequestBody") -> "ResponseEnvelope | tuple[dict[str, str], int]":
    """Executes the ProcessOptimizer

    Returns
    -------
    dict
        a JSON encodable dictionary representation of the result.
    """
    disconnect_check = _resolve_disconnect_check()

    if _parse_env_bool("USE_WORKER"):
        body_hash = hashlib.new("sha256")
        body_hash.update(json.dumps(body).encode())
        job_id = body_hash.hexdigest()
        try:
            job = Job.fetch(job_id, connection=redis)
            _LOG.info("Found existing job %s", job_id)
        except NoSuchJobError:
            _LOG.info("Creating new job (WORKER_TIMEOUT=%s)", WORKER_TIMEOUT)
            job = queue.enqueue(
                do_run_work,
                body,
                job_id=job_id,
                result_ttl=TTL,
                job_timeout=WORKER_TIMEOUT,
            )
        while job.return_value() is None:
            if disconnect_check():
                try:
                    _LOG.warning("Client disconnected, cancelling job %s", job.id)
                    job.cancel()
                    send_stop_job_command(redis, job.id)
                    job.delete()
                except Exception:
                    pass
                return {}  # type: ignore[return-value]  # empty sentinel on client disconnect
            time.sleep(0.2)
        return job.return_value()  # type: ignore[return-value]  # RQ returns Any; narrowed in Phase 4
    return do_run_work(body)


def do_run_work(body: "RequestBody") -> "ResponseEnvelope":
    """Handle the run request.

    On error we return a Connexion ``problem`` response, which serialises
    to the OpenAPI-declared 400 / 500 response shape.
    """
    try:
        # Phase 4 narrows optimizer.run return type to ResponseEnvelope
        return handle_run(body)  # type: ignore[return-value]
    except (IOError, TypeError, ValueError) as err:
        _LOG.warning("client error: %s", err)
        return connexion.problem(400, "Bad request", str(err))  # type: ignore[no-any-return]
    except Exception as err:
        _LOG.exception("unexpected error during optimizer run")
        return connexion.problem(500, "Internal server error", str(err))  # type: ignore[no-any-return]
