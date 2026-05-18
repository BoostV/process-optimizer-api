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
import traceback
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
    try:
        if "waitress.client_disconnected" in connexion.request.environ:
            disconnect_check = connexion.request.environ["waitress.client_disconnected"]
        else:

            def disconnect_check():
                return False

    except RuntimeError:

        def disconnect_check():
            return False

    if "USE_WORKER" in os.environ and os.environ["USE_WORKER"]:
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


def do_run_work(body: "RequestBody") -> "ResponseEnvelope | tuple[dict[str, str], int]":
    """Handle the run request."""
    try:
        # Phase 4 narrows optimizer.run return type to ResponseEnvelope
        return handle_run(body)  # type: ignore[return-value]
    except IOError as err:
        return ({"message": "I/O error", "error": str(err)}, 400)
    except TypeError as err:
        return ({"message": "Type error", "error": str(err)}, 400)
    except ValueError as err:
        return ({"message": "Validation error", "error": str(err)}, 400)
    except Exception as err:
        # Log unknown exceptions to support debugging
        traceback.print_exc()
        return ({"message": "Unknown error", "error": str(err)}, 500)
