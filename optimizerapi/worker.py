"""
Worker that will run all tasks published to redis using RQ
"""
import os
from rq import Connection, Queue, Worker
from redis import Redis


if "REDIS_URL" in os.environ:
    REDIS_URL = os.environ["REDIS_URL"]
else:
    REDIS_URL = "redis://localhost:6379"

if __name__ == "__main__":
    with Connection(Redis.from_url(REDIS_URL)):
        queue = Queue()
        Worker(queue).work()
