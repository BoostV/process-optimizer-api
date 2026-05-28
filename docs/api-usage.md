# Using the Process Optimizer API

This document walks through the end-to-end process of driving an experiment with the Process Optimizer API. It covers the request shape, the response shape, the suggested experiment loop, multi-objective workflows with pareto-point exploration, and the performance contract around cached model state.

The API is OpenAPI-first. For machine-readable details and an interactive sandbox, see the Swagger UI at `http://localhost:9090/v1.0/ui/`. This document describes the *process* of using the API — what to send, what comes back, and how successive calls fit together.

## 1. What the API does

The Process Optimizer API wraps [ProcessOptimizer](https://github.com/novonordisk-research/ProcessOptimizer) — a Bayesian optimization library — behind a single REST endpoint:

```
POST /v1.0/optimizer
```

You describe an experiment space and the data you've collected so far, and the server returns the next experiment(s) to run, plus diagnostic plots of the model's current beliefs. Each call is stateless: the full history is sent in the request body. A cache hint (`extras.pickled`) lets you skip retraining on repeat calls without affecting correctness.

The endpoint is the same for single- and multi-objective experiments — multi-objective is inferred from the shape of `yi`.

## 2. Running the server

For development:

```bash
pip install -e .
python -m optimizerapi.server
```

The server listens on port `9090` with Swagger UI at `/v1.0/ui/`. See `README.md` for production deployment, Redis-backed job queueing, CORS, and auth configuration.

## 3. Authentication

The endpoint accepts either of:

- **Static API key** as the `apikey` query parameter. Set `AUTH_API_KEY` on the server; clients add `?apikey=<key>` to the URL.
- **Keycloak OIDC** bearer token in `Authorization: Bearer <token>`. See `README.md` for the relevant `AUTH_*` env vars.

If neither is configured, the server still requires the `apikey` query parameter — pass any value (e.g. `?apikey=none`) for local development.

## 4. The request body

The endpoint accepts a JSON object with three top-level fields:

```json
{
  "data":            [ ... measurement history ... ],
  "optimizerConfig": { ... search space and BO hyperparameters ... },
  "extras":          { ... output and caching options ... }
}
```

`data` and `optimizerConfig` are **authoritative inputs** — together they define what the server computes. `extras` shapes the output (which plots, which format) and provides a cache hint to make repeat calls faster; it never affects correctness.

### 4.1 `optimizerConfig` — the search space and BO hyperparameters

```jsonc
{
  "baseEstimator":  "GP",         // "GP" or another ProcessOptimizer base estimator
  "acqFunc":        "EI",         // "EI" | "PI" | "LCB" | "gp_hedge" ...
  "initialPoints":  3,            // # of random samples before model takes over
  "kappa":          1.96,         // exploration weight for LCB
  "xi":             0.01,         // improvement threshold for EI / PI
  "space":          [ ... ],      // list of dimensions, see below
  "constraints":    [ ... ]       // optional, see below
}
```

Each dimension in `space` has one of three types:

```jsonc
// continuous (float)
{ "type": "continuous", "name": "Sugar",       "from": 0,   "to": 100 }

// discrete (integer)
{ "type": "discrete",   "name": "Temperature", "from": 0,   "to": 300 }

// categorical
{ "type": "category",   "name": "Finish",      "categories": ["None", "Frosting", "Whipped cream"] }
```

`constraints` is an optional list of sum-constraints across dimensions:

```jsonc
[
  { "type": "sum", "dimensions": [0, 1], "value": 200 }   // dim[0] + dim[1] == 200
]
```

### 4.2 `data` — the measurement history

A list of `{xi, yi}` pairs. `xi` is one experiment's coordinates in the same order as `space`. `yi` is a **list** of measured outcomes — length 1 for single-objective, length ≥ 2 for multi-objective. The optimizer minimizes each `yi` component.

```jsonc
{
  "data": [
    { "xi": [50,   833, 150, 60, "Whipped cream"], "yi": [-3, -6] },
    { "xi": [16.7, 500, 250, 20, "None"],          "yi": [-2, -17] }
  ]
}
```

For the very first call you have no measurements yet — send `"data": []`. The server returns initial-point suggestions instead.

> **Maximize instead of minimize?** Negate the value client-side. The optimizer always minimizes.

### 4.3 `extras` — output and cache options

All fields are optional. The most useful ones:

| Field                         | Meaning                                                                                       | Default                                       |
| ----------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------- |
| `experimentSuggestionCount`   | How many next-experiments to return                                                           | `1`                                           |
| `graphFormat`                 | `"png"` (base64-encoded images) or `"json"` (structured plot data)                            | `"png"`                                       |
| `graphs`                      | Which plots to compute: subset of `["objective", "convergence", "pareto", "single"]`          | `["objective", "convergence", "pareto", "single"]` |
| `maxQuality`                  | Render quality for PNG plots                                                                  | `5`                                           |
| `objectivePars`               | `"result"` or `"expected_minimum"` — where to evaluate the objective plot                     | `"result"`                                    |
| `includeModel`                | String `"true"` / `"false"` — whether to populate `result.pickled` in the response            | `"true"`                                      |
| `selectedPoint`               | Override the highlight point in single plots with explicit X-space coordinates. JSON only.    | none                                          |
| `pickled`                     | Cache hint from a previous response. The server validates it against the current request.    | none                                          |

Notes on a few less-obvious knobs:

- `graphFormat` controls the plot encoding. `"png"` produces classic image plots and is intended for human-facing UIs that display PNGs. `"json"` returns structured per-dimension series for clients that render plots themselves (e.g. a React-based UI).
- `selectedPoint` is honored **only** on the JSON path. On the PNG path it is logged-and-ignored.
- `includeModel: "false"` skips serializing the model into the response, saving bandwidth. The next call then has to do a full retrain (no cache available) — the server logs a warning when it sees `includeModel: "false"` together with an incoming `pickled`, since this combination silently breaks the cache chain.

## 5. The response body

```jsonc
{
  "plots": [
    { "id": "single_0_0",    "plot": "<base64 or JSON string>" },
    { "id": "convergence_0", "plot": "<...>" },
    { "id": "pareto_data",   "plot": "<...>" }
    // ... more
  ],
  "result": {
    "next":             [ [50, 833, 150, 60, "Whipped cream"] ],   // suggested experiments
    "models":           [ { "expected_minimum": [...], "extras": {} } ],
    "expected_minimum": [...],
    "pickled":          "<opaque cache blob>",
    "extras": {
      "pickledUsed": false,                                         // fast path engaged?
      "parameters":  { ... echo of the request inputs ... },
      "version":     "..."
    }
  }
}
```

Plot ids by mode:

| Mode                            | Plot ids                                                                      |
| ------------------------------- | ----------------------------------------------------------------------------- |
| Single-objective, `png`         | `single_0`, `convergence_0`, `objective` plots (when available)               |
| Single-objective, `json`        | `single_0_0`, `single_0_1`, ..., `single_0_<N-1>` (per-dim series), `single_0_<N>` (histogram entry) |
| Multi-objective                 | `pareto_data` plus per-objective single/objective plots (`objective_1_*`, `objective_2_*`) |

The `next` field is what you feed back into the next iteration: run those experiments, record the results, append to `data`, and call again.

## 6. The optimization loop

A typical sequence:

1. **Round 1 — no data yet.** POST with `"data": []` and your `optimizerConfig`. The server returns one or more initial-point suggestions in `result.next`.
2. **Run the experiments.** Measure `yi` for each suggested `xi`.
3. **Round 2..N.** POST again with the accumulated `data` (all prior `{xi, yi}` pairs). The server fits a model, returns plots, and proposes the next experiment in `result.next`.
4. **(Optional) Pass the cache hint.** On rounds 2..N, include the previous response's `result.pickled` as `extras.pickled`. The server validates that the data and config still match what produced that cache; if they match, model fitting is skipped and the response comes back faster.
5. **Stop when you're satisfied** — when convergence flattens, your budget is exhausted, or `result.expected_minimum` is good enough.

A minimal curl call for round 1:

```bash
curl 'http://localhost:9090/v1.0/optimizer?apikey=none' \
  -X POST \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "extras":          {"experimentSuggestionCount": 1},
    "data":            [],
    "optimizerConfig": {
      "baseEstimator": "GP",
      "acqFunc":       "gp_hedge",
      "initialPoints": 3,
      "kappa":         1.96,
      "xi":            0.01,
      "space": [
        {"type": "continuous", "name": "Red",   "from": 0, "to": 255},
        {"type": "continuous", "name": "Green", "from": 0, "to": 255},
        {"type": "discrete",   "name": "Blue",  "from": 0, "to": 255}
      ]
    }
  }'
```

Pre-built sample requests live in `scripts/`:

- `sample.curl` — minimal single-objective, JSON plot format
- `sample-multi.curl` — multi-objective with multiple data points
- `sample-multi-with-selection.curl` — multi-objective with `selectedPoint` + `pickled` (the pareto-exploration flow)

## 7. Multi-objective and pareto-point exploration

When `yi` is a list of length ≥ 2, the optimizer runs in multi-objective mode. The response then includes:

- A `pareto_data` plot entry with the pareto front in objective space (`front_y_data`), the corresponding points in X-space (`front_x_data`), per-objective uncertainty, and a `best_idx` highlighting a recommended compromise.
- Per-objective single plots (`objective_1_*`, `objective_2_*`).

A common UI flow:

1. Render the pareto front from `pareto_data`.
2. The user clicks a point on the pareto front. The UI looks up the corresponding `front_x_data[i]`.
3. The UI re-requests the optimizer endpoint with that coordinate list as `extras.selectedPoint` (and `graphFormat: "json"`). The server re-renders the single plots highlighting that point.
4. To keep this responsive, the UI also sends back the previous response's `result.pickled` as `extras.pickled` — the server skips the GP retraining step.

The full process, end-to-end, is the curl pair shown in `scripts/sample-multi-with-selection.curl`.

## 8. The pickled cache contract

The `pickled` field is a performance optimization. Two guarantees:

- **Equivalence.** For any request `R`, the response to `R` and to `R ∪ {extras.pickled: P}` are observably equivalent — same plots, same `next`, same `expected_minimum` — provided `P` was produced by an earlier response whose `data` and `optimizerConfig` matched `R`. Only `result.pickled` itself and the timing differ.
- **Fingerprint-validated.** The server embeds a hash of `(data, optimizerConfig)` inside the pickled blob at pack time. On a subsequent request the server recomputes the fingerprint and compares it to the one inside the blob. If they don't match — because the client sent a stale cache or changed the config — the cache is silently ignored and a full run is performed.

`result.extras.pickledUsed` tells you which path the server took: `true` for the fast path, `false` for a full run. The UI can use this to surface latency expectations without measuring.

Three things can cause a fall-through to a full run (each logs a single `WARNING`):

| Reason                  | When                                                                                | Logger / tag                          |
| ----------------------- | ----------------------------------------------------------------------------------- | ------------------------------------- |
| `decrypt_failed`        | Blob cannot be decrypted (rotated `PICKLE_KEY`, corrupted bytes)                    | `optimizerapi.pickled_state`          |
| `bad_structure`         | Blob decrypts but isn't the expected `{fingerprint, result, next, optimizer}` shape | `optimizerapi.pickled_state`          |
| `fingerprint_mismatch`  | Blob decrypts and is well-formed, but the embedded fingerprint differs from the request | `optimizerapi.pickled_state`     |

Two other warnings, not cache fall-throughs, surface useful misuse signals:

- `optimizerapi.optimizer`: `"selectedPoint ignored on png path"` — `selectedPoint` was sent with `graphFormat: "png"`. The field is JSON-only; on the PNG path it does nothing.
- `optimizerapi.optimizer`: `"includeModel=false with extras.pickled — next call will pay the full cost"` — the client used the cache to take the fast path but suppressed the new cache from the response, so the next call cannot reuse it.

None of these conditions are errors. The HTTP response is always valid in all five cases.

> **Why fingerprinting?** It guarantees the equivalence property mechanically: a client can never accidentally short-circuit the optimizer with a cache that was produced from different data, because such a cache is detected and ignored.

## 9. Error handling

The endpoint returns three status codes:

- `200 OK` — Success. Body is the result schema described in §5.
- `400 Bad Request` — Validation, type, or I/O error in the request.
- `500 Internal Server Error` — Unexpected server error.

Both error responses use the RFC 7807 problem+json shape produced by Connexion:

```jsonc
{
  "title":  "Bad request",          // or "Internal server error"
  "detail": "<error message>",      // exception message or validator output
  "status": 400,                    // or 500
  "type":   "about:blank"
}
```

For health checks: `GET /v1.0/health` returns `200` if the service is reachable.

## 10. End-to-end example: pareto-point exploration

This is the same flow as `scripts/sample-multi-with-selection.curl`, narrated step by step.

### Step 1 — initial multi-objective run

The client sends 3 measurements and asks for JSON pareto and single plots. The server returns plots, a next-experiment suggestion, and a `result.pickled` cache blob.

```bash
curl 'http://localhost:9090/v1.0/optimizer?apikey=none' \
  -X POST \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "extras": {
      "experimentSuggestionCount": 1,
      "graphs":                    ["pareto", "single"],
      "graphFormat":               "json"
    },
    "data": [
      {"xi": [16.7, 500, 250, 20, "None"],          "yi": [-2, -17]},
      {"xi": [50,   833, 150, 60, "Whipped cream"], "yi": [-3, -6]},
      {"xi": [58.3, 22,  85,  6,  "Frosting"],      "yi": [-6, -25]}
    ],
    "optimizerConfig": {
      "baseEstimator": "GP",
      "acqFunc":       "EI",
      "initialPoints": 3,
      "kappa":         1.96,
      "xi":            2,
      "space": [
        {"type": "continuous", "name": "Sugar",       "from": 0, "to": 100},
        {"type": "continuous", "name": "Flour",       "from": 0, "to": 1000},
        {"type": "discrete",   "name": "Temperature", "from": 0, "to": 300},
        {"type": "discrete",   "name": "Time",        "from": 0, "to": 120},
        {"type": "category",   "name": "Finish",      "categories": ["None", "Frosting", "Whipped cream"]}
      ],
      "constraints": []
    }
  }'
```

The response contains, among other things:

- A `pareto_data` plot entry the UI uses to render the pareto front.
- `result.pickled` — store this for the next call.
- `result.extras.pickledUsed: false` — this was a full run.

### Step 2 — the user clicks a pareto point

The UI takes the coordinates of the clicked point (read from `pareto_data.front_x_data[i]`) and re-requests with `selectedPoint` set, including the previous `pickled` for speed:

```bash
curl 'http://localhost:9090/v1.0/optimizer?apikey=none' \
  -X POST \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "extras": {
      "experimentSuggestionCount": 1,
      "graphs":                    ["pareto", "single"],
      "graphFormat":               "json",
      "selectedPoint":             [50, 833, 150, 60, "Whipped cream"],
      "pickled":                   "<paste result.pickled from step 1>"
    },
    "data":            [ ... same as step 1 ... ],
    "optimizerConfig": { ... same as step 1 ... }
  }'
```

If `data` and `optimizerConfig` match what produced the cache, `result.extras.pickledUsed` comes back `true` and the single plots are re-rendered with the new highlight point — without retraining the GP. If anything has drifted, the server silently falls through to a full run and the response is still correct (just slower).

That's the loop: keep accumulating measurements, keep round-tripping `pickled`, and reach for `selectedPoint` whenever a UI interaction needs a fresh single-plot view.

## 11. Quick reference

- **Endpoint:** `POST /v1.0/optimizer`
- **Auth:** `?apikey=<key>` or `Authorization: Bearer <token>`
- **Request:** `{data, optimizerConfig, extras}`
- **Response:** `{plots[], result: {next, models, expected_minimum, pickled, extras: {pickledUsed, parameters, version}}}`
- **Health:** `GET /v1.0/health`
- **Swagger UI:** `http://localhost:9090/v1.0/ui/`
- **Sample requests:** `scripts/sample.curl`, `scripts/sample-multi.curl`, `scripts/sample-multi-with-selection.curl`
- **Design notes:** `docs/superpowers/specs/2026-05-18-pareto-extras-redesign-design.md`
