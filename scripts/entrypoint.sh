#!/bin/bash

python ../scripts/configure_api.py
# ensure docker user has access to api specification 
#chown user:user optimizerapi/openapi/specification.yml
exec "$@"
