"""
FastAPI server for Process Optimizer API
"""
from fastapi import FastAPI
import uvicorn
from .securepickle import get_crypto

# Initialize crypto at module level (preserve current behavior)
get_crypto()

app = FastAPI(
    title="Process Optimizer API",
    version="1.0"
)


@app.get("/v1.0/health")
async def health():
    """Health check endpoint"""
    return "OK"


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9099)
