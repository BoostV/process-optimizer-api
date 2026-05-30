# Pareto `extras` Redesign — Design

**Date:** 2026-05-18
**Branch:** `langdal/ai-handoff-pareto`
**Status:** Design (awaiting plan)
**Supersedes the `extras.pickled` / `extras.selectedPoint` decisions in:** `.sisyphus/plans/pareto-point-selection.md`

## 1. Goal

Lock in the contract for the three `extras` fields that drive the pareto-point UI flow — `selectedPoint`, `pickled`, `includeModel` — under a single north-star principle, and produce a stable, equivalence-checkable API before merging the `pareto` branch.

## 2. North-star principle

> **The pickled model is an *efficiency* feature only. The full round-trip (user clicks a pareto point → server re-renders single plots) MUST work without `pickled`, just slower.**

Made formal:

> **Equivalence guarantee.** For any request `R`, the response to `R` and to `R ∪ {extras.pickled: P}` are observably equivalent — ignoring `result.pickled` and timing — provided `P` was produced by an earlier response whose `data` and `optimizerConfig` matched `R`.

Authoritative inputs are `data` and `optimizerConfig`. The server NEVER trusts state inside `pickled` to override them. The client MUST always send `data`.

## 3. Contract

### 3.1 `extras.selectedPoint`

- **Shape:** unchanged. Raw X-space coordinates as a list mixing numbers and category strings, matching the `space` dimensions in order. Example: `[50, 833, 150, 60, "Whipped cream"]`.
- **Rationale for keeping raw coords (vs. an index into the prior `pareto_data.front_x_data`):** stateless, self-contained, no coupling to prior response shape, no dependency on deterministic re-derivation of the pareto. The UI already has the coords; sending them back is free.
- **Honored when:** `extras.graphFormat == "json"`. PNG path does not support `selectedPoint`.
- **PNG + `selectedPoint`:** a `warning` is logged; the field is ignored; the response is otherwise unchanged. No error.
- **OpenAPI:** description updated to state the `graphFormat: "json"` precondition explicitly.

### 3.2 `extras.pickled`

- **Shape:** opaque string blob, as today. Clients SHOULD treat it as opaque and round-trip it verbatim.
- **Server-side payload structure (Fernet-encrypted, pickled):**
  ```
  {
      "fingerprint": "<sha256-hex of canonical request inputs>",
      "result":     <OptimizerResult or list thereof>,
      "next":       <list of next-point suggestions>,
      "optimizer":  <ProcessOptimizer instance>,
  }
  ```
  No version field — the encryption-key rotation (see §5) makes prior payloads undecryptable, so no in-tree migration logic is required.
- **Fingerprint definition:** `sha256_hex(canonical_json({"data": data, "optimizerConfig": optimizerConfig}))`, where `data` and `optimizerConfig` are the raw top-level request fields. `canonical_json` means sorted keys, no whitespace, stable number representation. The exact serializer choice is an implementation detail and lives in `pickled_state.py`. Fingerprinting on the raw request fields (rather than on internally reconstructed `space` / `hyperparams` / `constraints`) keeps the contract independent of internal refactoring.
- **Validation flow on incoming `extras.pickled`:**
  1. Decrypt with current `PICKLE_KEY`. Failure → fall through.
  2. Unpickle to a dict. Wrong type / missing keys → fall through.
  3. Compare `payload["fingerprint"]` to the fingerprint recomputed from the current request. Mismatch → fall through.
  4. All pass → fast path: reuse `payload["result"]` and `payload["optimizer"]`; skip `optimizer.tell(...)`.
- **Fall-through behavior:** a single `warning` log line with a reason tag (`decrypt_failed`, `bad_structure`, `fingerprint_mismatch`), and a full run is performed. The response is otherwise equivalent to one without `extras.pickled`.

### 3.3 `extras.includeModel`

- **Behavior:** unchanged. Controls whether `result.pickled` is populated in the response.
- **Typing:** unchanged — stringly-typed `"true"`/`"false"` parsed via `json.loads(...lower())`. Tightening to a real boolean is a separate, out-of-scope ticket; existing clients depend on the string form.
- **`includeModel: "false"` + `extras.pickled` sent in:** accepted, documented. The server uses the fast path and returns an empty `result.pickled`. A `warning` is logged so the chain-break is debuggable. The client is asking for exactly what it asked for; no auto-override.

### 3.4 New response field: `result.extras.pickledUsed`

- **Type:** boolean.
- **Set to `True` iff** the fast path was taken (all four validation steps in §3.2 passed).
- **Purpose:** lets the UI tell whether its cache hint was honored without inferring from timing. Optional for callers to read.

### 3.5 Response schema (recap of changes)

- `result.extras.pickledUsed: boolean` added.
- No other response-shape changes.

## 4. Code organization

- New module: `optimizerapi/pickled_state.py`, exposing:
  - `compute_fingerprint(data, optimizerConfig) -> str`
  - `pack(result, next_points, optimizer, fingerprint, crypto) -> str`
  - `unpack_if_valid(blob, expected_fingerprint, crypto) -> Optional[dict]` — returns the inner dict on success, `None` on any failure, and logs the reason on failure.
- `optimizerapi/optimizer.py`:
  - The unpickle block at ~lines 105–129 collapses to a single call to `unpack_if_valid(...)`. The `if/else/except` chain that exists today is replaced.
  - The pickle block at ~line 395 calls `pack(...)` with the request fingerprint computed earlier in `run`.
  - In `process_result`, set `result_details["extras"]["pickledUsed"]` according to whether the fast path ran.
  - Add `warning` logs for:
    - PNG + `selectedPoint` (in `process_result`, where `selected_point` is read).
    - `includeModel: "false"` + `extras.pickled` (in `run`, after the pickled path decision is made).

The point of pulling `pickled_state.py` out is to keep `optimizer.py:run` focused on optimizer-lifecycle code, and to make the fingerprint logic and fall-through paths independently testable.

## 5. Encryption-key rotation (operational)

- Rotate `PICKLE_KEY` in any environment that may hold pre-redesign pickled blobs. Operationally this means: deploy with a new key. No in-tree migration code is required; old blobs simply fail to decrypt and the existing fall-through path takes over.
- There are no in-production users of the `pickled` feature at this point, so this is risk-free.
- Mention the rotation requirement in the PR description / release notes for downstream consumers.

## 6. OpenAPI changes (`specification.yml`)

- `extras.pickled` description tightened to: "Opaque cache hint produced by a previous response. The server validates it matches the current `data` / `optimizerConfig`; on mismatch it is ignored and a full run is performed."
- `extras.selectedPoint` description appended with: "Honored only when `graphFormat` is `\"json\"`. Ignored on the PNG path."
- `result.extras` gains an optional `pickledUsed: boolean`.

## 7. Tests (new)

- **Equivalence test (the binding test for §2).** Run a multi-objective request twice — once without `pickled`, once with the `pickled` from the first response — both with the same `selectedPoint`. Assert that all `single_*` / `objective_*` plot entries are byte-equal (or numerically equal within tolerance for any floating-point reductions).
- **Fingerprint mismatch.** Send `pickled` from a previous response together with a modified `data` array. Assert: response matches a no-`pickled` run for the new `data`; `result.extras.pickledUsed == False`; one `warning` logged with reason `fingerprint_mismatch`.
- **Decrypt-failure fall-through.** Send a garbage `pickled` string. Assert: full run executed; `pickledUsed == False`; warning logged with reason `decrypt_failed`.
- **Bad-structure fall-through.** Decrypt-able but missing keys. Assert fall-through with reason `bad_structure`.
- **`pickledUsed` round-trip.** Two-call sequence: first call sets `pickledUsed == False`; second call (with returned `pickled`) sets `pickledUsed == True`.
- **PNG + `selectedPoint`.** Send PNG + `selectedPoint`. Assert: no error; warning logged; PNG plots returned and unaffected by `selectedPoint` value.
- **`includeModel: "false"` + `pickled`.** Existing `test_pickled_consumption_skips_training` already exercises this. Extend it to also assert that a warning is logged.

Existing tests for `selectedPoint` and old-format pickled should be reviewed: the old-format test (`test_old_format_pickled_falls_back`) likely still passes via the decrypt-failure or bad-structure path under the rotated key, but its assertions may need refreshing.

## 8. Out of scope

- Server-side session cache + short-ID `extras.pickleHandle` (deferred; the opaque-blob contract preserves a clean swap path).
- Migrating `includeModel` to a real boolean.
- Surfacing a structured `pickledRejectedReason` to the UI. Logs are sufficient until proven otherwise.
- Modifying `ProcessOptimizer` source.
- Changing `expected_minimum` computation.
- The `_get_brownie_bee_1d_plot_safe` workaround — it stays.
- The pre-existing `test_multi_objective_json_single_plots` failure.

## 9. Acceptance criteria

A reviewer can verify the work is done by:

1. The equivalence test in §7 passes.
2. All fall-through paths log exactly one `warning` with the documented reason tag.
3. `result.extras.pickledUsed` correctly reflects fast-path vs. full-run on a two-call sequence.
4. `specification.yml` reflects the description and schema changes in §6.
5. `optimizer.py:run` no longer contains inline unpickle/repack logic — it delegates to `pickled_state.py`.
6. PNG path is unchanged in behavior; `selectedPoint` is logged-and-ignored on that path.
7. `python -m pytest` is green except for the documented pre-existing `test_multi_objective_json_single_plots` failure; `flake8 . --max-line-length=127` is clean.
