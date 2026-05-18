# Audit Phase 1 — Security & Dependency Hygiene

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bump out-of-date crypto dependencies, eliminate auth-related anti-patterns (timing-attack-vulnerable equality, token-logging, default-API-key acceptance), and stop the `securepickle` module from mutating `os.environ` as a side effect.

**Architecture:** Single-shot changes to three files: `pyproject.toml` (dependency bumps), `optimizerapi/auth.py` (constant-time comparison + fail-closed + drop token log), `optimizerapi/securepickle/secure.py` (`is None` + no env mutation + warning). One new test module added: `tests/test_auth.py`. No API contract changes.

**Tech Stack:** Python 3.13 (just bumped), `cryptography`, Flask 2.2.x, connexion 2.14.x, pytest. `secrets.compare_digest` from stdlib for constant-time string comparison.

**Audit reference:** §5 of the audit findings. Specifically `cryptography==3.4.7` (2021, has CVEs), `apikey_handler`'s `==` comparison, the `print(access_token)` line in `auth.py:31`, and the `os.environ` mutation in `securepickle/secure.py`.

---

## File Map

- **Modify:** `pyproject.toml` — bump `cryptography`, `jsonschema`.
- **Modify:** `optimizerapi/auth.py` — `secrets.compare_digest`, drop token print, fail-closed default behavior.
- **Modify:** `optimizerapi/securepickle/secure.py` — `is None`, drop `os.environ` mutation, use `logging` for the no-key-set message.
- **Create:** `tests/test_auth.py` — unit tests for `apikey_handler` covering correct key, wrong key, and fail-closed default.

All work happens on branch `langdal/ai-restructure`. Test commands run via the existing `env/` venv (Python 3.13.13).

---

### Task 1: Bump `cryptography` to a current major

**Files:**
- Modify: `pyproject.toml:32`

- [ ] **Step 1: Check the dependency tree for hidden cryptography constraints**

Run:
```bash
env/bin/pip show python-keycloak python-jose | grep -i "Requires\|cryptography"
```
Expected: lists what other packages need from `cryptography`. Note the highest minor version implied by any constraint.

- [ ] **Step 2: Edit `pyproject.toml`**

Find the line:
```
  "cryptography==3.4.7",
```

Replace with:
```
  "cryptography>=44,<46",
```

The lower bound is the current LTS series; the upper guards against major-version surprises while still letting patch updates land.

- [ ] **Step 3: Reinstall**

Run:
```bash
env/bin/pip install -e ".[dev]" 2>&1 | tail -5
```
Expected: `Successfully installed ... cryptography-44.x.x ...` and no error.

- [ ] **Step 4: Run securepickle tests**

Run:
```bash
env/bin/python -m pytest tests/test_securepickle.py -v
```
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run:
```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 43 passed.

- [ ] **Step 6: Commit**

```bash
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -am "$(cat <<'EOF'
build: bump cryptography to current major (>=44)

cryptography 3.4.7 is from 2021 and has known CVEs. Fernet API surface
has not changed across 3.x→44.x so this is a drop-in bump.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If Step 3 surfaces an irreconcilable conflict (some dep pins `cryptography<X`), narrow the bump to the highest compatible major and report it in the commit message. Do NOT skip the bump entirely without flagging.

---

### Task 2: Bump `jsonschema`

**Files:**
- Modify: `pyproject.toml:31`

- [ ] **Step 1: Edit**

Find:
```
  "jsonschema==4.15.0",
```

Replace with:
```
  "jsonschema>=4.21,<5",
```

- [ ] **Step 2: Reinstall**

```bash
env/bin/pip install -e ".[dev]" 2>&1 | tail -5
```
Expected: jsonschema upgraded, no errors.

- [ ] **Step 3: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 43 passed.

If pytest fails, revert the bump (`git checkout pyproject.toml`) and pin to the highest minor that works. Connexion 2.14.2 uses jsonschema for OpenAPI validation — a bad bump shows up immediately as a validation error on every request.

- [ ] **Step 4: Commit**

```bash
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -am "$(cat <<'EOF'
build: bump jsonschema to 4.21+

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Constant-time API-key comparison

**Files:**
- Modify: `optimizerapi/auth.py:44-55`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_auth.py`:

```python
"""Tests for the API-key handler."""

from unittest.mock import patch


def test_correct_apikey_returns_scope_dict():
    """A request with the configured API key returns a scope dict."""
    with patch("optimizerapi.auth.AUTH_API_KEY", "secret-key"), \
         patch("optimizerapi.auth.AUTH_SERVER", None):
        from optimizerapi import auth
        result = auth.apikey_handler("secret-key")
    assert result == {"scope": []}


def test_wrong_apikey_returns_none():
    """An incorrect API key is rejected."""
    with patch("optimizerapi.auth.AUTH_API_KEY", "secret-key"), \
         patch("optimizerapi.auth.AUTH_SERVER", None):
        from optimizerapi import auth
        result = auth.apikey_handler("not-the-key")
    assert result is None


def test_apikey_handler_uses_constant_time_comparison():
    """The handler must compare keys via secrets.compare_digest."""
    from optimizerapi import auth
    import secrets

    with patch("optimizerapi.auth.AUTH_API_KEY", "secret-key"), \
         patch("optimizerapi.auth.AUTH_SERVER", None), \
         patch.object(secrets, "compare_digest", wraps=secrets.compare_digest) as mock_cmp:
        auth.apikey_handler("secret-key")
    assert mock_cmp.called, "apikey_handler must use secrets.compare_digest"
```

- [ ] **Step 2: Run test to verify some fail**

Run:
```bash
env/bin/python -m pytest tests/test_auth.py -v
```
Expected: the first two PASS (current `==` logic works for those), the third FAILS with `AssertionError: apikey_handler must use secrets.compare_digest`.

- [ ] **Step 3: Edit `optimizerapi/auth.py`**

At the top of the file, the existing imports are:

```python
import os
from keycloak import KeycloakOpenID
```

Add `secrets` and `logging`:

```python
import logging
import os
import secrets

from keycloak import KeycloakOpenID
```

Then replace the existing `apikey_handler`:

```python
def apikey_handler(access_token) -> dict:
    """Verify API key based on environment variable

    Returns
    -------
    dict
        a dictionary containing sub and scope
        None in case of invalid token
    """
    if not AUTH_SERVER and AUTH_API_KEY == access_token:
        return {"scope": []}
    return None
```

with:

```python
def apikey_handler(access_token: str) -> dict | None:
    """Verify the API key passed by the client.

    Returns
    -------
    dict
        ``{"scope": []}`` if the supplied key matches the configured
        ``AUTH_API_KEY``.
    None
        If the key is wrong, or if no static-key auth is configured.
    """
    if AUTH_SERVER:
        # OIDC is configured; static-key path is disabled.
        return None
    expected = AUTH_API_KEY.encode("utf-8")
    provided = (access_token or "").encode("utf-8")
    if secrets.compare_digest(expected, provided):
        return {"scope": []}
    return None
```

- [ ] **Step 4: Run tests**

Run:
```bash
env/bin/python -m pytest tests/test_auth.py -v
```
Expected: all 3 PASS.

Run the full suite:
```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 46 passed (43 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/auth.py tests/test_auth.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
fix(auth): use secrets.compare_digest for API-key comparison

Constant-time comparison protects against timing-side-channel attacks
when the configured AUTH_API_KEY is non-trivial.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Remove access-token logging in `token_info`

**Files:**
- Modify: `optimizerapi/auth.py:22-41`

- [ ] **Step 1: Edit `optimizerapi/auth.py`**

Replace the existing `token_info`:

```python
def token_info(access_token) -> dict:
    """Verify token with authentication server

    Returns
    -------
    dict
        a dictionary containing sub and scope
        None in case of invalid token
    """
    print(access_token)
    if not AUTH_SERVER:
        return {"scope": []}
    token = access_token
    token_data = keycloak_openid.introspect(token)
    if "active" in token_data and token_data["active"]:
        print("OK")
        return token_data
    print("NOT OK")
    print(token_data)
    return None
```

with:

```python
_LOG = logging.getLogger(__name__)


def token_info(access_token: str) -> dict | None:
    """Verify a bearer token against the configured Keycloak server.

    Returns
    -------
    dict
        Token data from Keycloak introspection when the token is active.
        If no OIDC server is configured, returns ``{"scope": []}``.
    None
        If the server reports the token as inactive.
    """
    if not AUTH_SERVER:
        return {"scope": []}
    token_data = keycloak_openid.introspect(access_token)
    if token_data.get("active"):
        _LOG.debug("token accepted")
        return token_data
    _LOG.warning("token rejected by Keycloak")
    return None
```

The four `print` lines (including the one that leaked the raw access token) are gone. `_LOG.debug` / `_LOG.warning` use the standard logger; the token itself is never logged.

- [ ] **Step 2: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 46 passed.

- [ ] **Step 3: Verify no `print` remains in `auth.py`**

Run:
```bash
grep -n "print(" optimizerapi/auth.py
```
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add optimizerapi/auth.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
fix(auth): stop logging raw access tokens to stdout

token_info previously printed the access_token on every request, which
leaks bearer credentials to whatever scrapes the API server's stdout.
Replaced with structured debug/warning logs that don't reference the
token value.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Fail closed when neither auth mechanism is configured

The current default (`AUTH_API_KEY = "none"`, `AUTH_SERVER = None`) means a request with `?apikey=none` succeeds. Convenient in dev, dangerous in prod if either env var is dropped on deploy.

**Files:**
- Modify: `optimizerapi/auth.py`
- Modify: `tests/test_auth.py`

- [ ] **Step 1: Add a failing test**

Append to `tests/test_auth.py`:

```python
def test_default_apikey_value_is_rejected_in_production_mode():
    """When AUTH_API_KEY is the default 'none' and FLASK_ENV is 'production',
    even matching the default value must be rejected."""
    with patch("optimizerapi.auth.AUTH_API_KEY", "none"), \
         patch("optimizerapi.auth.AUTH_SERVER", None), \
         patch("optimizerapi.auth.FLASK_ENV", "production"):
        from optimizerapi import auth
        result = auth.apikey_handler("none")
    assert result is None


def test_default_apikey_value_is_accepted_in_development_mode():
    """In development mode (FLASK_ENV != 'production'), the legacy
    behaviour of accepting AUTH_API_KEY='none' is preserved for ergonomics."""
    with patch("optimizerapi.auth.AUTH_API_KEY", "none"), \
         patch("optimizerapi.auth.AUTH_SERVER", None), \
         patch("optimizerapi.auth.FLASK_ENV", "development"):
        from optimizerapi import auth
        result = auth.apikey_handler("none")
    assert result == {"scope": []}
```

- [ ] **Step 2: Run tests to confirm one fails**

Run:
```bash
env/bin/python -m pytest tests/test_auth.py -v
```
Expected: `test_default_apikey_value_is_rejected_in_production_mode` FAILS (current code accepts it). The other new test PASSES.

- [ ] **Step 3: Edit `optimizerapi/auth.py`**

In the module-level constants block, add `FLASK_ENV`:

Find:
```python
AUTH_API_KEY = os.getenv("AUTH_API_KEY", "none")
AUTH_SERVER = os.getenv("AUTH_SERVER", None)
```

Replace with:
```python
AUTH_API_KEY = os.getenv("AUTH_API_KEY", "none")
AUTH_SERVER = os.getenv("AUTH_SERVER", None)
FLASK_ENV = os.getenv("FLASK_ENV", "development")

_DEFAULT_APIKEY = "none"  # sentinel: matches AUTH_API_KEY default; never accept in production
```

Update `apikey_handler`:

```python
def apikey_handler(access_token: str) -> dict | None:
    """Verify the API key passed by the client.

    Returns
    -------
    dict
        ``{"scope": []}`` if the supplied key matches the configured
        ``AUTH_API_KEY``.
    None
        If the key is wrong, OIDC is configured (OIDC handles this path),
        or the operator has not configured a real key in production.
    """
    if AUTH_SERVER:
        return None
    # In production we refuse the unconfigured default value, even if it
    # technically matches the request — operators should set a real key.
    if FLASK_ENV == "production" and AUTH_API_KEY == _DEFAULT_APIKEY:
        return None
    expected = AUTH_API_KEY.encode("utf-8")
    provided = (access_token or "").encode("utf-8")
    if secrets.compare_digest(expected, provided):
        return {"scope": []}
    return None
```

- [ ] **Step 4: Run tests**

```bash
env/bin/python -m pytest tests/test_auth.py -v
```
Expected: all 5 PASS.

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 48 passed (46 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/auth.py tests/test_auth.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
fix(auth): refuse default AUTH_API_KEY='none' in production

Previously, a server deployed with FLASK_ENV=production but no explicit
AUTH_API_KEY would still accept ?apikey=none. Now that's rejected;
operators must set a real key to enable the static-key path in prod.
Development mode keeps the legacy behaviour for ergonomics.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Fix `== None` in `securepickle/secure.py`

Pre-existing flake8 E711 violations. Trivial fix while we're in this file anyway.

**Files:**
- Modify: `optimizerapi/securepickle/secure.py:6,8`

- [ ] **Step 1: Edit**

Replace:
```python
def get_crypto(key=None):
    if key == None:
        key = os.getenv("PICKLE_KEY", None)
    if key == None:
        print("No key found, generating new key")
        key = Fernet.generate_key()
        os.environ["PICKLE_KEY"] = key.decode("utf-8")
        print("To reuse key for future server runs, set environment variable PICKLE_KEY=" +
              os.environ["PICKLE_KEY"])
    return Fernet(key)
```

with (this also lands Task 7's changes — see step note):

```python
def get_crypto(key=None):
    if key is None:
        key = os.getenv("PICKLE_KEY", None)
    if key is None:
        print("No key found, generating new key")
        key = Fernet.generate_key()
        os.environ["PICKLE_KEY"] = key.decode("utf-8")
        print("To reuse key for future server runs, set environment variable PICKLE_KEY=" +
              os.environ["PICKLE_KEY"])
    return Fernet(key)
```

**Only the two `== None` → `is None` changes here.** Task 7 finishes the rest of the cleanup.

- [ ] **Step 2: Verify lint**

```bash
env/bin/flake8 optimizerapi/securepickle/secure.py --max-line-length=127
```
Expected: only the warning-free output (no E711). May still show other style issues; those are Task 7's job.

- [ ] **Step 3: Commit**

```bash
git add optimizerapi/securepickle/secure.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
style(securepickle): use 'is None' instead of '== None'

Resolves long-standing flake8 E711 violations.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: `get_crypto` no longer mutates `os.environ`, logs instead of prints

**Files:**
- Modify: `optimizerapi/securepickle/secure.py`

- [ ] **Step 1: Edit**

Replace the whole file:

```python
import logging
import os

from cryptography.fernet import Fernet

_LOG = logging.getLogger(__name__)


def get_crypto(key=None):
    """Return a Fernet crypto handle for the given key.

    Resolution order:
        1. ``key`` argument (highest priority).
        2. ``PICKLE_KEY`` environment variable.
        3. Generate a new ephemeral key and warn the operator.

    The ephemeral path is intended for local development only. In any
    environment where pickled state must survive a restart, ``PICKLE_KEY``
    must be set explicitly. This function no longer mutates ``os.environ``
    so caller environments are unchanged.
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
```

Changes from the previous version:

- `os.environ["PICKLE_KEY"] = ...` removed — `get_crypto` is now side-effect-free except for logging.
- `print` → `_LOG.warning` — visible in production logs, can be filtered/routed.
- The warning text is unified into a single message; before it printed two lines.
- Imports reordered (stdlib, then third-party).

- [ ] **Step 2: Run the securepickle tests**

```bash
env/bin/python -m pytest tests/test_securepickle.py -v
```
Expected: PASS.

- [ ] **Step 3: Run the full suite**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 48 passed.

- [ ] **Step 4: Verify behaviour by smoke-testing the server**

```bash
timeout 5 env/bin/python -m optimizerapi.server 2>&1 | head -15 || true
```
Expected: the `_LOG.warning` line about generating a key appears (this used to be two `print` lines). The Flask startup line appears below it.

- [ ] **Step 5: Commit**

```bash
git add optimizerapi/securepickle/secure.py
git -c user.email="jakob.langdal@alexandra.dk" -c user.name="Jakob Langdal" commit -m "$(cat <<'EOF'
refactor(securepickle): use logging, drop os.environ mutation

get_crypto previously printed to stdout and wrote PICKLE_KEY back into
os.environ as a side effect. Both are surprising for a "getter":
- print bypasses log routing/filtering
- env mutation makes the caller's environment opaque to itself

Now it logs a single WARNING and leaves os.environ alone. The behaviour
contract (return a Fernet handle, optionally backed by a freshly
generated key) is unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Final lint + test pass

**Files:** none.

- [ ] **Step 1: flake8**

```bash
env/bin/flake8 optimizerapi tests --max-line-length=127
```
Expected: fewer violations than before. `optimizerapi/securepickle/secure.py` should be fully clean (no E711). `optimizerapi/auth.py` should be clean. `optimizerapi/securepickle/__init__.py` F401s (re-export warnings) and `tests/context.py` F401s remain (those are deferred to Phase 5). `tests/test_optimizer.py:12,15` E501s remain (Phase 5).

- [ ] **Step 2: pytest**

```bash
env/bin/python -m pytest 2>&1 | tail -3
```
Expected: 48 passed.

- [ ] **Step 3: No additional commit required.**

---

## Out of scope (for Phase 1)

- Flask 2 → 3 migration (requires Connexion 3 rewrite; see overview).
- ProcessOptimizer pinning to a release tag (deferred; need a release to exist first).
- `print` cleanup outside `auth.py` and `secure.py` — that's Phase 2.
- `typing` annotations beyond what fits naturally into the auth signatures (`dict | None`) — Phase 3.
- Pre-existing flake8 violations outside the touched files — Phase 5.

## Acceptance criteria

- `cryptography>=44` installed; `tests/test_securepickle.py` passes.
- `apikey_handler` uses `secrets.compare_digest`; a unit test asserts the call.
- `apikey_handler` refuses `AUTH_API_KEY="none"` in production.
- `token_info` no longer prints the access token or any other stdout output.
- `get_crypto` no longer mutates `os.environ` and no longer prints; emits one WARNING when generating an ephemeral key.
- `flake8 optimizerapi/auth.py optimizerapi/securepickle/secure.py` is clean.
- Full suite: 48 passed (43 prior + 5 new auth tests).
