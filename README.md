# Process Optimizer REST API #

This project expose a REST based API for [ProcessOptimizer](https://github.com/novonordisk-research/ProcessOptimizer)

# How do I get started

If you have Docker installed the API can be started locally by running the script `build-and-run.sh`

Alternatively the project can be build and run with the following commands:

    python3 -m venv env
    source env/bin/activate
    pip install --upgrade pip
    
    pip install -r requirements.txt
    python optimizerapi/server.py

Now open [http://localhost:9090/v1.0/ui/](http://localhost:9090/v1.0/ui/) in a browser to explore the API through Swagger UI
# Running tests

Unit tetsts are located in the "tests" folder and can be run witht the following command

    python -m pytest

# Building docker container

    docker build -t process-optimizer-api .
# Obtain encryption key

Run server once and extract a fresh encryption key from the logs.

    python optimizerapi/server.py

or using docker

    docker run --rm -it process-optimizer-api
# Running in production

Running using python

    FLASK_ENV=production PICKLE_KEY=<key from previous step> python optimizerapi/server.py

or use docker

    docker run -d --name process-optimizer-api --env PICKLE_KEY=<key from previous step> -p 9090:9090 process-optimizer-api:latest
