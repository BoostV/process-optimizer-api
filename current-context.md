# Current Context — pareto branch, design checkpoint

> Temporary working doc. Captures where the `pareto` branch sits today (2026-05-18) and what the next brainstorm needs to settle. Delete after the brainstorm produces an updated plan.

## TL;DR

The `pareto-point-selection` plan was fully implemented and QA-approved on 2026-03-27, but the `pareto` branch has **not** been merged. A UI is being built in parallel and will inform changes to the API. Before merging, we need a design brainstorm focused on the **ergonomics of `selectedPoint` / `pickled` / `includeModel`** — driven by one north-star principle the user has now articulated:

> **The pickled model is an *efficiency* feature only. The full round-trip (user clicks a pareto point → server re-renders single plots) must work without pickled, just slower.**

This principle was not stated in the original plan and contradicts at least one of its design decisions (see "Tensions" below).

## What's on the branch today

- Two features shipped (commits `5e13f92` → `590b09e`):
  - `extras.selectedPoint` — list of X-space coords; overrides `x_eval` in `_get_brownie_bee_1d_plot_safe` at 3 sites in `optimizer.py`. JSON graphFormat only.
  - `extras.pickled` — round-trip string; payload format `{"result", "next", "optimizer"}`. Silent fallback to full run on bad/old-format input.
- OpenAPI schema updated with both fields under `extras`.
- `_get_brownie_bee_1d_plot_safe()` wraps a known ProcessOptimizer v1.1.1 bug where `get_Brownie_Bee_1d_plot(x_eval=...)` with categoricals creates a string-dtype numpy array.
- `includeModel` is unchanged from before: `extras.includeModel` is a **stringly-typed** boolean parsed via `json.loads(extras.get("includeModel", "true").lower())` at `optimizer.py:224`. Controls whether the response `pickled` field is populated.
- 29 tests pass. One pre-existing failure (`test_multi_objective_json_single_plots`) is unrelated and explicitly out of scope.

Full trace lives under `.sisyphus/`: `plans/pareto-point-selection.md`, `notepads/pareto-point-selection/{decisions,issues,learnings}.md`, and `evidence/` (including `final-qa/qa-summary.txt`).

## UI flow driving the redesign

User clicks a point on the pareto plot → UI re-requests the optimizer endpoint with that point set as `selectedPoint` → wants single plots refreshed quickly. `pickled` is the speed lever, not a correctness requirement.

## Loose ends in the working tree

- `scripts/multi-blank-first-run.curl`, `scripts/multi-blank-second-run.curl` — untracked. 4-dim space (water/temperature/angle/color, categorical), first has empty `data`, second has 5 points × 2 objectives. Hand-rolled smoke tests, not bug repros. Different shape from the existing `sample-multi.curl` (5-dim) and `sample-multi-with-selection.curl`.
- `result.json` — untracked, 0 bytes. Placeholder.
- `CLAUDE.md` — untracked.
- Branch is unmerged; QA approval is six weeks old; behavior may need to shift based on UI findings.

## Tensions to resolve in the brainstorm

These are the concrete things to argue out — not yet decided.

1. **"Pickled overrides data" vs "pickled is efficiency only"**
   Original plan decision #23 said pickled overrides the request `data` field. The current implementation actually passes `data` through to `process_result` regardless, so the contract is unclear. Under the new principle, the same request *with* and *without* `extras.pickled` should produce equivalent output — just at different speeds. That means `data` must be authoritative and the client should always send it. Confirm and document; possibly enforce.

2. **`includeModel=false` + `extras.pickled` sent in**
   Today this consumes the incoming state but returns an empty `pickled` field — silently breaking the next iteration's fast path. Options: warn, auto-override to true, forbid, or accept as-is and document.

3. **`includeModel` typing**
   String `"true"`/`"false"` parsed via `json.loads`. Cheap to fix to a real boolean in the OpenAPI spec; would touch every existing client. Decide whether to bundle with the redesign or leave alone.

4. **`selectedPoint` as raw coordinates vs index**
   UI currently has to read `pareto_data.front_x_data`, pick an element, and round-trip the coordinate list. An index reference would be tighter but couples the request to the prior response shape. Open.

5. **Pickled payload size and shape**
   The pickled string is large enough that `sample-multi-with-selection.curl` documents it as "paste manually". Round-tripping it through the browser is workable but ugly. A server-side session cache + short ID is an option; not requested, but worth flagging since the UI will surface this pain.

6. **PNG path has no `selectedPoint` support**
   Deliberate exclusion in the original plan. If the UI ever wants PNG fallback, this becomes a gap.

## Out of scope for the brainstorm (do not reopen)

- Fixing the pre-existing `test_multi_objective_json_single_plots` failure.
- Modifying `ProcessOptimizer` source.
- Changing `expected_minimum` computation.
- The `_get_brownie_bee_1d_plot_safe` workaround — it works.

## Open questions for the user (to bring into the brainstorm)

- What does the UI need from a *failed* fast path? Silent fallback (current), explicit error, or a "stale" flag in the response?
- Is the long-term plan to keep optimizer state strictly client-managed (stateless server), or is a session/cache acceptable?
- Are there UI affordances already designed that lock us into a particular extras shape (e.g., is the UI already sending `selectedPoint` as coordinates)?
- What's the merge target / timeline once the brainstorm settles?

## Suggested next move

Run `superpowers:brainstorming` against this doc as the seed. Goal: produce a revised plan that replaces the relevant TODOs in `.sisyphus/plans/pareto-point-selection.md` (or a fresh plan file) and clarifies the principle above in writing before any more code lands.
