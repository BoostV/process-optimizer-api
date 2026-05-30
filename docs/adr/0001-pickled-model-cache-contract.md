# 0001. Pickled model is an advisory, fingerprint-validated cache hint

- **Status:** accepted
- **Date:** 2026-05-30
- **Deciders:** Jakob Langdal

## Context

The pareto-point UI flow re-renders single plots whenever a user clicks a point
on the front. Re-running the Bayesian optimizer (GP `tell` / retraining) on
every such request is expensive, so the API lets a client round-trip an opaque
`extras.pickled` blob produced by a previous response to skip that work.

The risk is that `pickled` carries optimizer state that could silently diverge
from the request's authoritative inputs (`data`, `optimizerConfig`) — a corrupt
blob, a stale one from a different dataset, or one encrypted under a rotated
`PICKLE_KEY`. If the server trusted that state, two requests with identical
inputs could return different results depending on whether a cache hint was
attached, which is impossible to debug from the client side.

## Decision

We will treat the pickled model as an **efficiency feature only**, never as
authoritative state. See `optimizerapi/pickled_state.py` and its use in
`optimizerapi/optimizer.py:run`.

- **Equivalence guarantee.** For any request `R`, the responses to `R` and to
  `R ∪ {extras.pickled: P}` are observably equivalent (ignoring `result.pickled`
  and timing), provided `P` came from an earlier response whose `data` and
  `optimizerConfig` matched `R`. The full round-trip MUST work without `pickled`,
  just slower. The client always sends `data`; the server never reads inputs out
  of the blob.
- **Fingerprint validation.** The blob stores
  `sha256_hex(canonical_json({data, optimizerConfig}))`. On an incoming
  `pickled`, the server decrypts → checks structure → compares the fingerprint
  to the current request, and only then takes the fast path. Any failure falls
  through to a full run with a single `warning` tagged `decrypt_failed`,
  `bad_structure`, or `fingerprint_mismatch`.
- **Observability.** `result.extras.pickledUsed` (boolean) reports whether the
  fast path was taken, so the UI need not infer it from timing.
- **No in-tree payload versioning.** Rotating `PICKLE_KEY` makes pre-existing
  blobs undecryptable, and the decrypt-failure fall-through handles them — so no
  migration code is carried.
- **Adjacent request semantics** fixed at the same time: `selectedPoint` is
  honored only on the `graphFormat: "json"` path (logged-and-ignored on PNG),
  and `includeModel: "false"` with `pickled` is honored verbatim (fast path,
  empty `result.pickled`, warning logged) rather than auto-overridden.

## Consequences

- Identical inputs always produce identical results; `pickled` can only make a
  response faster, never different. This is enforceable by an equivalence test.
- Fall-through is safe by construction, so a bad or stale blob degrades to a
  correct (slower) answer instead of an error or wrong output.
- Fingerprinting on the raw request fields keeps the contract stable across
  internal refactors of `space` / `hyperparams` / `constraints`.
- Cost: every fast path pays a decrypt + sha256 + structural check, and the blob
  is opaque and bound to the current key — clients cannot reuse it across a key
  rotation. Accepted as cheap relative to a GP refit.

## Alternatives considered

- **Trust optimizer state inside `pickled`.** Rejected: breaks the equivalence
  guarantee and makes client-visible behavior depend on an opaque blob.
- **`selectedPoint` as an index into the prior response's `front_x_data`.**
  Rejected in favor of raw X-space coordinates: stateless, no coupling to prior
  response shape, no dependency on deterministically re-deriving the front.
- **A payload `version` field with in-tree migration.** Rejected: key rotation
  plus fall-through already covers stale blobs without migration code.
- **Server-side session cache keyed by a short `pickleHandle`.** Deferred (out
  of scope); the opaque-blob contract leaves a clean swap path if needed later.
