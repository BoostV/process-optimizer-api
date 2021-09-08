# First stage
FROM python:3.9.1 AS builder

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --upgrade pip && pip install pip-tools && pip install --upgrade pip

COPY requirements-freeze.txt .
RUN cat requirements-freeze.txt | grep --invert-match pkg_resources > requirements-fixed.txt
RUN pip install -r requirements-fixed.txt

# Second stage
FROM python:3.9.1-slim
COPY --from=builder /opt/venv /opt/venv
WORKDIR /code

# add non-root user
RUN addgroup --system user && adduser --system --no-create-home --group user
RUN chown -R user:user /code && chmod -R 755 /code

USER user

COPY --from=builder /requirements-fixed.txt /code/requirements-freeze.txt
COPY version.txt /code
COPY optimizerapi/ /code

ENV FLASK_ENV=production

ENV PATH=/opt/venv/bin:${PATH}

CMD [ "python", "./server.py" ]