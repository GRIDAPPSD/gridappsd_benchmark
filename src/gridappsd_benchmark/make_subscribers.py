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

def run_subscriber(subscriber: int, opts: Namespace, done_evnt: Event):
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
        done_evnt.wait()
    except KeyboardInterrupt:
        message_queue.put(DONE_SENTINAL)
        pass

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("num_subscribers", type=int, help="How many subscribers should be started.  Must be >= 1")
    parser.add_argument("--gridappsd-address", default="localhost", type=str)
    parser.add_argument("--gridappsd-port", default=61613, type=int)
    parser.add_argument("--subscription-topic", default="pmu.data", type=str)
    parser.add_argument("--username", default="system")
    parser.add_argument("--password", default="manager")
    opts = parser.parse_args()

    done_evnt = Event()
    procs: list[Process] = []

    for p in range(opts.num_subscribers):
        proc = Process(target=run_subscriber, args=[p, opts, done_evnt])
        proc.daemon = True
        proc.start()
        procs.append(proc)


    while True:
        try:
            time.sleep(0.1)
        except KeyboardInterrupt:
            done_evnt.set()
            for proc in procs:
                #proc.kill()
                proc.join()

            break
