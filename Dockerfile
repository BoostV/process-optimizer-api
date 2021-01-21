# First stage
FROM python:3.9.1 AS builder

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN pip install --upgrade pip && pip install pip-tools

COPY requirements.txt .
RUN pip install -r requirements.txt

# Second stage
FROM python:3.9.1-slim
COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
WORKDIR /code

# add non-root user
RUN addgroup --system user && adduser --system --no-create-home --group user
RUN chown -R user:user /code && chmod -R 755 /code

USER user

COPY src/ /code

ENV PATH=/opt/venv/bin:${PATH}

CMD [ "python", "./server.py" ]