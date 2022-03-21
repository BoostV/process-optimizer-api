"""
Worker that will run all tasks published to redis using RQ
"""
from rq import Connection, Queue, Worker
from redis import Redis

if __name__ == '__main__':
    # Tell rq what Redis connection to use
    with Connection():
        queue = Queue(connection=Redis())
        Worker(queue).work()
