# Codebase Audit — 5-Phase Improvement Plan

This is the index for the audit-driven improvements identified after the Pareto extras redesign landed. The audit covered structure, idioms, typing, security, logging, and tests. Findings are split into five phases that each ship independent, testable software.

## Ordering rationale

The phases are ordered by risk × dependency:

1. **Security & dependency hygiene** — low blast radius, highest urgency. CVE bumps + fix auth issues. Lays no traps for later phases.
2. **Logging migration** — mechanical sweep; produces no behavior change but cleans up the surface that Phase 1 partly touched.
3. **Boundary types** — adds `TypedDict`s and a static type checker. Acts as a safety net for Phase 4.
4. **Refactor `process_result`** — the biggest behavior-preserving change. Splits ~250 lines into focused helpers. Types from Phase 3 catch mistakes that would otherwise need runtime to surface.
5. **Opportunistic cleanup** — small wins (fixtures, idiomatic Python, dead code) that benefit from the structural work above.

Each phase has its own plan file in this directory.

## Phase plans

| # | Plan                                                                                                                        | Touches                                          |
| - | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| 1 | [`2026-05-18-audit-phase-1-security.md`](./2026-05-18-audit-phase-1-security.md)                                            | `auth.py`, `securepickle/`, `pyproject.toml`     |
| 2 | [`2026-05-18-audit-phase-2-logging.md`](./2026-05-18-audit-phase-2-logging.md)                                              | `server.py`, `auth.py`, `secure.py`, `optimizer_handler.py`, `optimizer.py` |
| 3 | [`2026-05-18-audit-phase-3-boundary-types.md`](./2026-05-18-audit-phase-3-boundary-types.md)                                | new `types.py`, all module signatures, mypy config |
| 4 | [`2026-05-18-audit-phase-4-refactor-process-result.md`](./2026-05-18-audit-phase-4-refactor-process-result.md)               | `optimizer.py`, new `plot_emitters.py`           |
| 5 | [`2026-05-18-audit-phase-5-cleanup.md`](./2026-05-18-audit-phase-5-cleanup.md)                                              | tests, `optimizer_handler.py`, `auth.py`         |

## Out of scope across all phases

- Flask 2 → 3 / Connexion 2 → 3 migration. Connexion 3 is a rewrite (async) — this is its own project, not a cleanup. Phase 1 limits the dependency bumps to libraries that don't ripple through the framework.
- ProcessOptimizer source changes.
- Switching auth providers; redesigning the API contract; multi-tenant features.
- Performance work (async/background queue model). Phase 5 notes the issue but does not fix it.

## Acceptance for the audit as a whole

When all five phases are done:

- `flake8 optimizerapi tests --max-line-length=127` is fully clean (no pre-existing exceptions remain).
- `mypy optimizerapi` (or `pyright`) is clean.
- `python -m pytest` is 43+ passed (no regressions; new tests for security fixes).
- `optimizer.py` is under ~250 lines; `process_result` is under ~80 lines.
- `auth.py` uses `secrets.compare_digest` and never prints tokens.
- `cryptography` is on a current major.
- No `print()` calls in any module under `optimizerapi/`.
- The OpenAPI surface is unchanged (response shape and field names stay the same).
