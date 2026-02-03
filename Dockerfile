ARG GITHUB_REF_NAME=develop
ARG GITHUB_SHA=local
# First stage
FROM python:3.9-bullseye AS builder

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --upgrade pip

COPY pyproject.toml .
RUN pip install .

# Second stage

FROM python:3.9-bullseye
ARG GITHUB_REF_NAME
ARG GITHUB_SHA
COPY --from=builder /opt/venv /opt/venv
WORKDIR /code
ENV VERSION=${GITHUB_REF_NAME}
ENV SHA=${GITHUB_SHA}

# add non-root user
RUN addgroup --system user && adduser --system --no-create-home --group user
RUN chown -R user:user /code && chmod -R 755 /code
RUN mkdir -p /code/mapplotlib

USER user

COPY --from=builder /pyproject.toml /code/pyproject.toml
#COPY version.txt /code
RUN echo "${VERSION}-${SHA}" > /code/version.txt
COPY optimizerapi/ /code/optimizerapi

ENV FLASK_ENV=production
ENV MPLCONFIGDIR=/tmp/mapplotlib

ENV PATH=/opt/venv/bin:${PATH}
VOLUME /code/matplotlib

CMD [ "python", "-m", "optimizerapi.server" ]