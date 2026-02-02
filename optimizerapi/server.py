"""
FastAPI server for Process Optimizer API
"""
import os
import re
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import uvicorn
from .securepickle import get_crypto

# Initialize crypto at module level (preserve current behavior)
get_crypto()

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
async def health():
    """Health check endpoint"""
    return "OK"


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9099)
