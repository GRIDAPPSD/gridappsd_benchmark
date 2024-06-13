from datetime import datetime
import sys
import time

from gridappsd import GridAPPSD


subscriber_name = 'subscriber'
def on_message(header: dict, message: dict):
    # print(f"Received: {message}")
    ts_now = datetime.utcnow().timestamp()
    taken = ts_now - message['start']
    sys.stdout.write(','.join([subscriber_name, str(message['start']), str(ts_now), str(taken)]) + "\n")
    sys.stdout.flush()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("subscriber", type=str)
    parser.add_argument("--gridappsd-address", default="localhost", type=str)
    parser.add_argument("--gridappsd-port", default=61613, type=int)
    parser.add_argument("--subscription-topic", default="/topic/pmu.data", type=str)
    parser.add_argument("--username", default="system")
    parser.add_argument("--password", default="manager")
    opts = parser.parse_args()

    #sys.stderr.write("This is before gapps\n")
    gapps = GridAPPSD(stomp_address=opts.gridappsd_address,
                      stomp_port=opts.gridappsd_port,
                      username=opts.username,
                      password=opts.password)

    #sys.stderr.write("This is after gapps\n")
    subscriber_name = opts.subscriber
    gapps.subscribe(opts.subscription_topic, on_message)
    # Requirement for protocol this will kick off to the parent caller.
    sys.stdout.write("Starting Subscription\n")
    sys.stdout.flush()

    while True:
        #sys.stderr.write("While waiting!\n")
        time.sleep(0.000001)

