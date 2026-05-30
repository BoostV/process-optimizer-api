# Audit Phase 2 — Logging Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every `print()` call in `optimizerapi/` with a properly-scoped `logging` call routed through a single `basicConfig` set up at server startup. Remove dead `# print(...)` comments.

**Architecture:** Centralize log configuration in `optimizerapi/server.py` (run before any handlers fire). Each module uses `logging.getLogger(__name__)`, so loggers fall into the natural module hierarchy (`optimizerapi.server`, `optimizerapi.optimizer_handler`, etc.) and can be filtered/routed individually in production.

**Tech Stack:** Standard library `logging`.

**Audit reference:** §4 of the audit. `print` calls remain in `server.py`, `optimizer_handler.py`, and dead-code comments in `optimizer.py`. Phase 1 already removed prints from `auth.py` and `secure.py`.

**Prereq:** Phase 1 complete (`auth.py` and `secure.py` are already on `logging`).

---

## File Map

- **Modify:** `optimizerapi/server.py` — add `logging.basicConfig`, convert 3 prints.
- **Modify:** `optimizerapi/optimizer_handler.py` — convert ~4 prints.
- **Modify:** `optimizerapi/optimizer.py` — delete 2 dead `# print(...)` comments.
- **Modify:** `tests/test_no_prints.py` (new) — enforce the no-print rule under `optimizerapi/`.

---

### Task 1: Centralize log config in `server.py`

**Files:**
- Modify: `optimizerapi/server.py`

- [ ] **Step 1: Edit `optimizerapi/server.py`**

The existing file starts with:

```python
"""
Main server
"""
import os
import re
import connexion
from waitress import serve
from flask_cors import CORS
from .securepickle import get_crypto
```

Replace with:

```python
"""
Main server
"""
import logging
import os
import re

import connexion
from flask_cors import CORS
from waitress import serve

from .securepickle import get_crypto

_LOG = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure root logging once, before any handler is dispatched.

    Level defaults to INFO. Override with the LOG_LEVEL environment
    variable (e.g. LOG_LEVEL=DEBUG for local debugging).
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
```

Then, inside the existing `if __name__ == "__main__":` block, add a call to `_configure_logging()` as the very first statement:

Find:
```python
if __name__ == "__main__":
    # Initialize crypto
    get_crypto()
```

Replace with:
```python
if __name__ == "__main__":
    _configure_logging()
    # Initialize crypto
    get_crypto()
```

Then replace the three CORS-related `print` lines.

Find:
```python
            print("CORS: " + cors_origin)
        except re.error:
            print("CORS: failed - the regex might be malformed.")
    else:
        print("CORS: disabled")
```

Replace with:
```python
            _LOG.info("CORS: %s", cors_origin)
        except re.error:
            _LOG.warning("CORS: failed - the regex might be malformed.")
    else:
        _LOG.info("CORS: disabled")
```

- [ ] **Step 2: Smoke-test the server boots and emits log lines**

```bash
LOG_LEVEL=INFO timeout 5 env/bin/python -m optimizerapi.server 2>&1 | head -15 || true
```

Expected: At least one line of the form `2026-... INFO optimizerapi.server: CORS: ...` appears. The Phase-1 `_LOG.warning("No PICKLE_KEY set...")` line from `securepickle.secure` is also routed through this config and appears with the right format.

- [ ] **Step 3: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 48 passed (unchanged from end of Phase 1).

- [ ] **Step 4: Commit**

```bash
git add optimizerapi/server.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
refactor(server): central logging.basicConfig + CORS prints to logger

LOG_LEVEL env var (default INFO) controls verbosity. All module loggers
inherit this single basicConfig, so per-module routing is now possible
in production.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Convert prints in `optimizer_handler.py`

**Files:**
- Modify: `optimizerapi/optimizer_handler.py`

- [ ] **Step 1: Audit the existing prints**

Run:
```bash
grep -n "print(" optimizerapi/optimizer_handler.py
```

Expected output (lines may shift slightly):
```
25:print("Connecting to" + REDIS_URL)
67:            print("Found existing job")
69:            print(f"Creating new job (WORKER_TIMEOUT={WORKER_TIMEOUT})")
80:                    print(f"Client disconnected, cancelling job {job.id}")
```

- [ ] **Step 2: Edit the file**

At the top, the existing import block looks like:

```python
import os
import time
import json
import traceback
import hashlib
from rq import Queue
from rq.job import Job
```

Add `import logging` (alphabetical, with the other stdlib imports):

```python
import hashlib
import json
import logging
import os
import time
import traceback

from rq import Queue
from rq.job import Job
```

Right after the imports, add the module logger and replace the module-level connection print.

Find:
```python
if "REDIS_URL" in os.environ:
    REDIS_URL = os.environ["REDIS_URL"]
else:
    REDIS_URL = "redis://localhost:6379"
print("Connecting to" + REDIS_URL)
redis = Redis.from_url(REDIS_URL)
```

Replace with:
```python
_LOG = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
_LOG.info("Connecting to %s", REDIS_URL)
redis = Redis.from_url(REDIS_URL)
```

(The `os.environ.get(..., default)` collapse and the formatted-arg log are idiomatic; the latter also fixes the missing space between "to" and the URL in the previous line.)

Then inside `run(body)`, replace:

```python
        try:
            job = Job.fetch(job_id, connection=redis)

            print("Found existing job")
        except NoSuchJobError:
            print(f"Creating new job (WORKER_TIMEOUT={WORKER_TIMEOUT})")
```

with:

```python
        try:
            job = Job.fetch(job_id, connection=redis)
            _LOG.info("Found existing job %s", job_id)
        except NoSuchJobError:
            _LOG.info("Creating new job (WORKER_TIMEOUT=%s)", WORKER_TIMEOUT)
```

And the disconnect print:

```python
                    print(f"Client disconnected, cancelling job {job.id}")
```

with:

```python
                    _LOG.warning("Client disconnected, cancelling job %s", job.id)
```

- [ ] **Step 3: Verify no print remains**

```bash
grep -n "print(" optimizerapi/optimizer_handler.py
```
Expected: no output.

- [ ] **Step 4: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 48 passed.

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/optimizer_handler.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
refactor(handler): use logging in place of print

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Remove dead `# print(...)` comments in `optimizer.py`

**Files:**
- Modify: `optimizerapi/optimizer.py`

- [ ] **Step 1: Find the dead comments**

```bash
grep -n "# print(" optimizerapi/optimizer.py
```
Expected output:
```
<line>:    # print(str(response))
<line>:    # print("IMAGE: " + str(pic_hash, "utf-8"))
```

- [ ] **Step 2: Delete those two lines.**

Edit the file and remove exactly those two `# print(...)` lines. Do not touch surrounding code.

- [ ] **Step 3: Confirm clean**

```bash
grep -n "print(" optimizerapi/optimizer.py
```
Expected: no output.

- [ ] **Step 4: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 48 passed.

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/optimizer.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
chore(optimizer): drop two dead # print debug comments

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Enforce no-print rule with a unit test

This locks in the migration so future regressions are caught.

**Files:**
- Create: `tests/test_no_prints.py`

- [ ] **Step 1: Write the test**

Create `tests/test_no_prints.py`:

```python
"""Lint test: no stray print() in production code.

Tests in this repo configure their own logging; production code MUST
route everything through ``logging`` so operators can filter, level-
gate, and route messages in production. ``print`` calls bypass that.
"""

import ast
import pathlib

import pytest

OPTIMIZERAPI_ROOT = pathlib.Path(__file__).parent.parent / "optimizerapi"


def _all_python_files() -> list[pathlib.Path]:
    return [p for p in OPTIMIZERAPI_ROOT.rglob("*.py") if p.is_file()]


@pytest.mark.parametrize("path", _all_python_files(), ids=lambda p: str(p.relative_to(OPTIMIZERAPI_ROOT.parent)))
def test_no_print_calls(path):
    """No `print()` call is allowed under optimizerapi/."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]
    assert not offenders, (
        f"{path}: found print() calls at line(s) {offenders}. "
        "Use logging.getLogger(__name__) instead."
    )
```

- [ ] **Step 2: Run the test**

```bash
env/bin/python -m pytest tests/test_no_prints.py -v
```
Expected: PASS for every file under `optimizerapi/`.

If anything fails, find the missed `print` and convert it. The error message will say which file and line.

- [ ] **Step 3: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 48+N passed where N is the number of `.py` files under `optimizerapi/` (the parametrize generates one test per file).

- [ ] **Step 4: Commit**

```bash
git add tests/test_no_prints.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
test: enforce no print() under optimizerapi/

Locks in the logging migration with an AST-based lint test so future
regressions fail loudly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Acceptance criteria

- `grep -rn "print(" optimizerapi/` returns nothing.
- `tests/test_no_prints.py` passes for every module.
- Server still boots; log lines appear under the new `2026-... LEVEL name: message` format.
- Full pytest run is green.
