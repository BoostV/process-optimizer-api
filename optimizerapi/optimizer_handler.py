"""ProcessOptimizer web request handler

This file contains the main HTTP request handlers for exposing the ProcessOptimizer API.
NOTE: This module is kept for backward compatibility with tests.
The actual FastAPI server is in server.py and calls optimizer.run() directly.
"""

import os
import traceback
from .optimizer import run as handle_run


def run(body) -> dict:
    """Executes the ProcessOptimizer (legacy wrapper for tests)

    Returns
    -------
    dict
        a JSON encodable dictionary representation of the result.
    """
    return do_run_work(body)


def do_run_work(body) -> dict:
    """Handle the run request"""
    try:
        return handle_run(body)
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
