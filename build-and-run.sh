#!/bin/sh

docker build -t process-optimizer-api . && \
docker run \
--rm \
-it \
-p 9090:9090 \
-e FLASK_ENV="development" \
process-optimizer-api