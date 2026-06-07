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

We will pass `strategy="cl_min"` for **all** multi-point asks, unconstrained and
constrained alike, in `optimizer._compute_next_experiments`. For `n_points == 1`
the strategy is irrelevant (ProcessOptimizer returns `_ask()` directly), so the
single-suggestion behaviour is byte-for-byte unchanged. The constrained branch
already used `cl_min`; this removes the only remaining caller of the default.

Constant-liar (`cl_min`) optimizes the acquisition function through the GP —
which handles categorical dimensions natively — instead of solving a
high-dimensional Steinerberger problem, so it stays fast (sub-second to a few
seconds for typical batches) regardless of categorical cardinality.

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
- We give up the Steinerberger space-filling option on the unconstrained batch
  path. If we want it back as an *opt-in* for cheap (low-transformed-dimension)
  experiments, that is a follow-up (e.g. a server-side dimensionality/time
  budget gate), not a client choice.

## Alternatives considered

- **Keep `stbr_fill`, but guard it** by transformed-dimensionality or an
  estimated time budget and fall back to `cl_min` when too expensive. More
  faithful to the original exploration intent, but more moving parts and a
  heuristic threshold to maintain; deferred as a possible follow-up.
- **Expose `strategy` as a request/`extras` option** (default `cl_min`). Pushes
  a performance-critical, easily-misused knob to clients for a capability almost
  no caller needs; rejected in favour of a safe server-side default.
