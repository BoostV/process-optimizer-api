"""
Worker that will run all tasks published to redis using RQ
"""
import os
from rq import Queue, Worker
from redis import Redis


if "REDIS_URL" in os.environ:
    REDIS_URL = os.environ["REDIS_URL"]
else:
    REDIS_URL = "redis://localhost:6379"

if "WORKER_TIMEOUT" in os.environ:
    WORKER_TIMEOUT = int(os.environ["WORKER_TIMEOUT"])
else:
    WORKER_TIMEOUT = 180

if __name__ == "__main__":
    redis = Redis.from_url(REDIS_URL)
    queue = Queue(connection=redis)
    Worker(queue).work()
