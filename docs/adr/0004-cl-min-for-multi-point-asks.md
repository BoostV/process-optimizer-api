# 0004. Use constant-liar (cl_min) for all multi-point asks

- **Status:** accepted
- **Date:** 2026-06-07
- **Deciders:** Jakob Langdal

## Context

`POST /optimizer` with `extras.experimentSuggestionCount > 1` asks
ProcessOptimizer for a batch of next experiments via `optimizer.ask(n_points=N)`.
Until now we only passed an explicit strategy on the *constrained* branch
(`strategy="cl_min"`, added because Steinerberger sampling raises with
constraints — see issue #83); the *unconstrained* branch fell through to
ProcessOptimizer's default, `strategy="stbr_fill"`.

For `N > 1` on a model that is already fitted (`#data ≥ initialPoints`),
`stbr_fill` routes points 2…N through `stbr_scipy()` — a Steinerberger
space-filling solver that runs 20 SciPy `minimize` restarts over the
**one-hot-transformed** space, re-transforming every observation on each
objective evaluation. The cost is dominated by the one-hot expansion of
categorical variables. On a real experiment with 5 continuous + 5 categorical
variables (31 transformed dimensions) a single count-2 request consumed ~30
minutes of CPU — effectively a hang synchronously, or a `WORKER_TIMEOUT` failure
behind the worker. Low-dimensional bundled examples (Catapult: 4 dims, Brownie:
7) masked it because the same path is cheap there.

The first suggestion is unaffected (it is always `optimizer._ask()`), and the
LHS-based initialization phase is unaffected; only the 2nd…Nth points of a
fitted-model batch took the slow path.

## Decision

`cl_min` (constant liar) is the **default** strategy for multi-point asks in
`optimizer._compute_next_experiments`. For `n_points == 1` the strategy is
irrelevant (ProcessOptimizer returns `_ask()` directly), so single-suggestion
behaviour is byte-for-byte unchanged. Constant-liar optimizes the acquisition
function through the GP — which handles categorical dimensions natively —
instead of solving a high-dimensional Steinerberger problem, so it stays fast
(sub-second to a few seconds) regardless of categorical cardinality.

We still **opt into `stbr_fill`** (Steinerberger space-filling, the nicer
exploration spread for extra batch points) when it is affordable: the request is
unconstrained, `n_points > 1`, and a deterministic cost estimate is within a
wall-clock budget (`STBR_TIME_BUDGET_SECONDS`, default 10s). The estimate
(`_estimate_stbr_seconds`) is calibrated from benchmarks: cost is dominated
*super-linearly* by categorical one-hot dimensions, mildly by continuous/discrete
dimensions, and ~linearly by `n_points - 1`. It is a pure function of the space
and batch size — **not** a wall-clock measurement — so the chosen strategy, and
therefore the suggestions, stay reproducible across machines and load. Anything
over budget (e.g. the motivating 31-dimension experiment) falls back to `cl_min`.

## Consequences

- **Performance:** the count-2 hang is gone (~30 min → ~3 s on the motivating
  experiment); cost now scales gently with batch size rather than exploding with
  categorical dimensionality.
- **Behaviour change (single objective, count > 1, fitted model, no
  constraint):** the extra suggestions change character — from space-filling
  *exploration* (Steinerberger) to acquisition-driven *batch BO* with the
  constant-liar penalty. This is the conventional batch-BO behaviour and matches
  what the constrained path always did, but it is a real change for anyone who
  relied on the exploration spread. Count 1 is unchanged.
- **Unblocks constrained batches:** constrained multi-point asks via `cl_min`
  are fast and respect the constraint (verified: every suggested point satisfies
  the `SumEquals`). The frontend previously capped constrained experiments to a
  single suggestion because constrained multi-point was unsupported (it errored
  on the Steinerberger default); that cap can now be lifted.
- Steinerberger space-filling is retained for cheap experiments via the
  server-side budget gate, so low-dimensional experiments keep the nicer
  exploration spread while categorical-heavy ones stay fast on `cl_min`. The
  cost is a calibrated heuristic (`_estimate_stbr_seconds`) that must be
  re-checked if the ProcessOptimizer/SciPy stack or reference hardware changes
  materially.

## Alternatives considered

- **Always `cl_min`, drop Steinerberger entirely.** Simplest, but loses the
  exploration spread for the small experiments where it is both nice and cheap.
  Rejected in favour of the budget gate.
- **A wall-clock time budget** (run-then-timeout, or probe-one-restart and
  extrapolate). Adapts to hardware, but makes the chosen strategy — and thus the
  suggestions — depend on CPU speed and load, breaking reproducibility for a
  seeded optimizer. Rejected in favour of a deterministic structural estimate.
- **Gate on raw `transformed_n_dims`.** Rejected: continuous dimensions are
  cheap (20 continuous dims ≈ 3s) while categorical one-hot dimensions are not
  (10 one-hot ≈ 17s), so a single transformed-dimension threshold mis-predicts.
  The estimate weights categorical load specifically.
- **Expose `strategy` as a request/`extras` option** (default `cl_min`). Pushes
  a performance-critical, easily-misused knob to clients for a capability almost
  no caller needs; rejected in favour of a safe server-side default.
