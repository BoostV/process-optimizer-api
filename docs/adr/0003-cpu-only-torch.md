# 0003. Pin torch to the CPU-only wheel

- **Status:** accepted
- **Date:** 2026-05-30
- **Deciders:** Jakob Langdal

## Context

ProcessOptimizer (a core dependency, installed from a git ref) pulls `torch` in
transitively. On Linux, the default `torch` wheel on PyPI is the CUDA build,
which drags in the full NVIDIA CUDA stack (`nvidia-cublas`, `cudnn`, `nccl`,
`cusolver`, `cusparse`, ...) — roughly 5 GB. The API only ever runs CPU
inference, so none of that is used. It was the dominant cost behind slow Docker
builds and produced a ~6 GB image.

## Decision

We will pin `torch` to PyTorch's CPU-only index. See `pyproject.toml`
(`[[tool.uv.index]]` `pytorch-cpu` + `[tool.uv.sources]`) and commit `aa490b0`.

A subtlety drove the shape of this: **uv's `[tool.uv.sources]` index pins apply
only to _direct_ dependencies, not transitive ones** (verified empirically). So
we also declare `torch` explicitly in `[project.dependencies]` (unconstrained,
so uv unifies it with ProcessOptimizer's requirement) and map it to the
`pytorch-cpu` index via `[tool.uv.sources]`. Resolution then yields
`torch==2.12.0+cpu` with zero CUDA packages.

## Consequences

- Image drops from ~6 GB to ~1.42 GB; builds and CI are markedly faster. The fix
  applies uniformly to the Docker image, CI, and local dev because all three
  install via uv from the same `pyproject.toml`.
- The build now depends on `download.pytorch.org` **and** `download-r2.pytorch.org`
  (PyTorch redirects the actual wheel/metadata blobs to its R2 backend) being
  reachable — relevant only where egress is filtered.
- `torch` is now a direct dependency we must keep loosely in step with what
  ProcessOptimizer expects; leaving it unconstrained lets uv resolve the unified
  version.
- If GPU inference is ever wanted, this pin must be revisited.

## Alternatives considered

- **Accept the default CUDA `torch`.** Rejected: ~5 GB of libraries we never use,
  for a CPU-only workload.
- **`[tool.uv.sources]` pin without declaring `torch` directly.** Rejected: source
  pins don't apply to transitive dependencies, so it had no effect on resolution
  (confirmed by testing).
- **Install CPU `torch` only inside the Dockerfile** (e.g. `uv pip install torch
  --index-url .../cpu` before the project). Rejected: it would slim the image but
  leave dev and CI installs on the CUDA build. The `pyproject.toml` approach fixes
  all three in one place.
