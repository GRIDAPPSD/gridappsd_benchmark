from multiprocessing import Process, Event
import threading
from gridappsd import GridAPPSD
from argparse import Namespace
import time
from datetime import datetime
from queue import Queue, Empty

DONE_SENTINAL = "Done"

def write_queue(thequeue: Queue, filename: str):

    fp = open(filename, 'w')
    while data := thequeue.get():
        if data == DONE_SENTINAL:
            break
        fp.write(f"{data}\n")

    fp.close()

def run_subscriber(subscriber: int, opts: Namespace):
    print(f"Starting Subscriber: {subscriber}")


    gapps = GridAPPSD(stomp_port=opts.gridappsd_port,
                    stomp_address=opts.gridappsd_address,
                    username=opts.username,
                    password=opts.password)
    message_queue: Queue = Queue()
    thread = threading.Thread(target=write_queue, args=[message_queue, f"subscriber{subscriber}.txt"], daemon=True)
    thread.start()

    def received_message(header, message):
        ts_now = datetime.utcnow().timestamp()
        taken = ts_now - message['start']
        message_queue.put(dict(sent=message['start'], received=ts_now, took=taken))
        print(f"thread: {threading.current_thread}: message: {message}")

    gapps.subscribe(opts.subscription_topic, received_message)

    try:
        while True:
            time.sleep(0.00001)
    except KeyboardInterrupt:
        message_queue.put(DONE_SENTINAL)
        thread.join()

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("subscriber_number", help="A numerical identifier of a subscriber.")
    parser.add_argument("--gridappsd-address", default="localhost", type=str)
    parser.add_argument("--gridappsd-port", default=61613, type=int)
    parser.add_argument("--subscription-topic", default="pmu.data", type=str)
    parser.add_argument("--username", default="system")
    parser.add_argument("--password", default="manager")
    opts = parser.parse_args()

    run_subscriber(subscriber=opts.subscriber_number, opts=opts)
