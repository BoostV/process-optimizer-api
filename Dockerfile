# syntax=docker/dockerfile:1
ARG GITHUB_REF_NAME=develop
ARG GITHUB_SHA=local

# ---- Builder: resolve and install dependencies with uv (matches dev/CI) ----
FROM python:3.13-slim-bookworm AS builder

# git is required to install ProcessOptimizer from its git ref (see pyproject.toml).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# uv: fast, parallel resolver — the same tool used locally and in CI.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV VIRTUAL_ENV=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
RUN uv venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /src
# setuptools needs the readme (project metadata) and the package source
# (tool.setuptools.packages.find) to build the project; copy both before install.
COPY pyproject.toml README.md ./
COPY optimizerapi/ ./optimizerapi/
# Cache mount keeps uv's download/build cache across builds even when this layer
# is rebuilt, so the ProcessOptimizer git dependency isn't re-fetched every time.
RUN --mount=type=cache,target=/root/.cache/uv uv pip install .

# ---- Runtime ----
FROM python:3.13-slim-bookworm
ARG GITHUB_REF_NAME
ARG GITHUB_SHA

WORKDIR /code
ENV VERSION=${GITHUB_REF_NAME} \
    SHA=${GITHUB_SHA} \
    FLASK_ENV=production \
    MPLCONFIGDIR=/tmp/matplotlib \
    PATH=/opt/venv/bin:${PATH}

# Dependencies come from the builder venv; the app itself runs from /code where
# the full source tree (incl. optimizerapi/openapi/specification.yml) is present.
COPY --from=builder /opt/venv /opt/venv
COPY pyproject.toml /code/pyproject.toml
COPY optimizerapi/ /code/optimizerapi

# Run as a non-root user with a version stamp baked in.
RUN addgroup --system user \
    && adduser --system --no-create-home --group user \
    && echo "${VERSION}-${SHA}" > /code/version.txt \
    && chown -R user:user /code

USER user

CMD [ "python", "-m", "optimizerapi.server" ]
