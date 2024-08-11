from redis import Redis
from rq import Worker, Queue, Connection

listen = ["message_queue"]

redis_conn = Redis()

if __name__ == "__main__":
    with Connection(redis_conn):
        worker = Worker(map(Queue, listen))
        worker.work()
