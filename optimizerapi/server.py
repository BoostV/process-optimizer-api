"""
FastAPI server for Process Optimizer API
"""
import os
import re
import traceback
import time
import json
import hashlib
import asyncio
from fastapi import FastAPI, Depends, HTTPException, Request
from typing import Dict, Any, Optional
from starlette.middleware.cors import CORSMiddleware
import uvicorn
from .securepickle import get_crypto
from .auth import get_api_key
from .models import Experiment, Result, Error
from .optimizer import run as optimizer_run

# RQ worker imports (conditional based on USE_WORKER)
try:
    from rq import Queue
    from rq.job import Job
    from rq.exceptions import NoSuchJobError
    from rq.command import send_stop_job_command
    from redis import Redis
    RQ_AVAILABLE = True
except ImportError:
    RQ_AVAILABLE = False

# Initialize crypto at module level (preserve current behavior)
get_crypto()

# RQ worker configuration
USE_WORKER = "USE_WORKER" in os.environ and os.environ["USE_WORKER"]
redis: Optional[Redis] = None
queue: Optional[Queue] = None
TTL = 500
WORKER_TIMEOUT = 180

if USE_WORKER:
    if not RQ_AVAILABLE:
        raise RuntimeError("RQ not available but USE_WORKER is set")
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
    print("Connecting to " + REDIS_URL)
    redis = Redis.from_url(REDIS_URL)
    TTL = int(os.environ.get("REDIS_TTL", "500"))
    WORKER_TIMEOUT = int(os.environ.get("WORKER_TIMEOUT", "180"))
    queue = Queue(connection=redis)

app = FastAPI(
    title="Process Optimizer API",
    version="1.0"
)

# Configure CORS based on environment variable
# Preserve exact Flask-CORS behavior
DEVELOPMENT = "development"
env = os.getenv("FLASK_ENV", DEVELOPMENT)
development = env == DEVELOPMENT

# Allow all origins in development, disable by default in production
ALLOW_ALL_ORIGINS = ".*"
cors_origin = os.getenv("CORS_ORIGIN", ALLOW_ALL_ORIGINS if development else None)

if cors_origin:
    try:
        # FastAPI's CORSMiddleware expects allow_origins as a list or string pattern
        # We support regex patterns like Flask-CORS does
        # When using regex, FastAPI requires allow_origin_regex parameter
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=cors_origin,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_credentials=True,
        )
        print("CORS: " + cors_origin)
    except re.error:
        print("CORS: failed - the regex might be malformed.")
else:
    print("CORS: disabled")


@app.get("/v1.0/health")
async def health(token_info: Dict[str, Any] = Depends(get_api_key)):
    """Health check endpoint"""
    return "OK"


@app.post(
    "/v1.0/optimizer",
    response_model=Result,
    responses={400: {"model": Error}, 500: {"model": Error}}
)
async def optimizer(
    body: Experiment,
    request: Request,
    token_info: Dict[str, Any] = Depends(get_api_key)
):
    """Execute the ProcessOptimizer
    
    Parameters
    ----------
    body : Experiment
        Experiment configuration with data, optimizerConfig, and optional extras
    request : Request
        Starlette Request object for disconnect detection
    token_info : dict
        Authentication info from get_api_key dependency
        
    Returns
    -------
    Result
        Optimization results with plots and result data
        
    Raises
    ------
    HTTPException
        400 for IOError/TypeError/ValueError
        500 for unknown errors
    """
    try:
        # Convert Pydantic model to dict with proper serialization:
        # - mode='json': Convert Enums to string values
        # - by_alias=True: Use 'from' instead of 'from_'
        # - exclude_none=True: Match optimizer.py expectations
        body_dict = body.model_dump(mode='json', by_alias=True, exclude_none=True)
        
        if USE_WORKER:
            # Worker mode: enqueue job in Redis and poll for completion
            # Generate deterministic job ID (bug fix: add sort_keys=True)
            if redis is None or queue is None:
                raise RuntimeError("Redis not configured but USE_WORKER is set")
            
            body_hash = hashlib.new("sha256")
            body_hash.update(json.dumps(body_dict, sort_keys=True).encode())
            job_id = body_hash.hexdigest()
            
            try:
                job = Job.fetch(job_id, connection=redis)
                print("Found existing job")
            except NoSuchJobError:
                print(f"Creating new job (WORKER_TIMEOUT={WORKER_TIMEOUT})")
                job = queue.enqueue(
                    optimizer_run,
                    body_dict,
                    job_id=job_id,
                    result_ttl=TTL,
                    job_timeout=WORKER_TIMEOUT,
                )
            
            # Poll for job completion with disconnect detection
            while job.return_value() is None:
                if await request.is_disconnected():
                    try:
                        print(f"Client disconnected, cancelling job {job.id}")
                        job.cancel()
                        send_stop_job_command(redis, job.id)
                        job.delete()
                    except Exception:
                        pass
                    return {}
                await asyncio.sleep(0.2)
            
            return job.return_value()
        else:
            # Direct mode: execute immediately without worker
            result = optimizer_run(body_dict)
            return result
    except IOError as err:
        raise HTTPException(
            status_code=400,
            detail={"message": "I/O error", "error": str(err)}
        )
    except TypeError as err:
        raise HTTPException(
            status_code=400,
            detail={"message": "Type error", "error": str(err)}
        )
    except ValueError as err:
        raise HTTPException(
            status_code=400,
            detail={"message": "Validation error", "error": str(err)}
        )
    except Exception as err:
        # Log unknown exceptions to support debugging
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={"message": "Unknown error", "error": str(err)}
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9099)
