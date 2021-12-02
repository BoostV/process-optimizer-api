from rq import Connection, Queue, Worker
from redis import Redis

if __name__ == '__main__':
    # Tell rq what Redis connection to use
    with Connection():
        q = Queue(connection=Redis())
        Worker(q).work()