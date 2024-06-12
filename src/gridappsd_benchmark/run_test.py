from gridappsd import GridAPPSD
from threading import Thread
from argparse import Namespace
from datetime import datetime
import math

import os
from pathlib import Path
import subprocess
import sys
import time

def get_message_to_publish() -> str:
    from synchrophasor.pmu import Pmu
    from synchrophasor.frame import ConfigFrame2, HeaderFrame, DataFrame

    pmu = Pmu(ip="127.0.0.1", port=9991)
    pmu.logger.setLevel("DEBUG")

    ph_v_conversion = int(300000.0 / 32768 * 100000)  # Voltage phasor conversion factor
    ph_i_conversion = int(15000.0 / 32768 * 100000)  # Current phasor conversion factor

    cfg = ConfigFrame2(
        7,  # PMU_ID
        1000000,  # TIME_BASE
        1,  # Number of PMUs included in data frame
        "Station A",  # Station name
        7734,  # Data-stream ID(s)
        (False, False, True,
        False),  # Data format - Check ConfigFrame2 set_data_format()
        14,  # Number of phasors
        3,  # Number of analog values
        1,  # Number of digital status words
        [
            "VA", "VB", "VC", "I1", "VA1", "VB1", "VC1", "I11", "VA2", "VB2",
            "VC2", "I12", "VA3", "VB3", "ANALOG1", "ANALOG2", "ANALOG3",
            "BREAKER 1 STATUS", "BREAKER 2 STATUS", "BREAKER 3 STATUS",
            "BREAKER 4 STATUS", "BREAKER 5 STATUS", "BREAKER 6 STATUS",
            "BREAKER 7 STATUS", "BREAKER 8 STATUS", "BREAKER 9 STATUS",
            "BREAKER A STATUS", "BREAKER B STATUS", "BREAKER C STATUS",
            "BREAKER D STATUS", "BREAKER E STATUS", "BREAKER F STATUS",
            "BREAKER G STATUS"
        ],  # Channel Names
        [(ph_v_conversion, "v"), (ph_v_conversion, "v"), (ph_v_conversion, "v"),
        (ph_i_conversion, "i"), (ph_v_conversion, "v"), (ph_v_conversion, "v"),
        (ph_v_conversion, "v"), (ph_i_conversion, "i"), (ph_v_conversion, "v"),
        (ph_v_conversion, "v"), (ph_v_conversion, "v"), (ph_i_conversion, "i"),
        (ph_v_conversion, "v"), (ph_v_conversion, "v")],  # Conversion factor for phasor channels
        [(1, "pow"), (1, "rms"),
        (1, "peak")],  # Conversion factor for analog channels
        [(0x0000, 0xffff)],  # Mask words for digital status words
        60,  # Nominal frequency
        1,  # Configuration change count
        240)  # Rate of phasor data transmission)

    hf = HeaderFrame(7,  # PMU_ID
                        "Hello I'm nanoPMU!")  # Header Message

    df = DataFrame(
        7,  # PMU_ID
        ("ok", True, "timestamp", False, False, False, 0, "<10",
        0),  # STAT WORD - Check DataFrame set_stat()
        [(14635, 0), (-7318, -12676), (-7318, 12675), (1092, 0), (14635, 0),
        (-7318, -12676), (-7318, 12675), (1092, 0), (14635, 0), (-7318, -12676),
        (-7318, 12675), (1092, 0), (14635, 0), (-7318, -12676)],  # PHASORS (3 - v, 1 - i)
        2500,  # Frequency deviation from nominal in mHz
        0,  # Rate of Change of Frequency
        [100, 1000, 10000],  # Analog Values
        [0x3c12],  # Digital status word
        cfg)  # Data Stream Configuration

    pmu.set_configuration(cfg)
    pmu.set_header(hf)


    data_to_send = df.convert2bytes()
    return data_to_send.hex()


def run_single_subscriber_no_blocking(subscriber_name: str, opts: Namespace):
    pth = Path(__file__).parent / 'single_subscriber.py'
    cmd = [sys.executable,
           pth.as_posix(),
           f"{subscriber_name}",
           "--gridappsd-address", opts.gridappsd_address,
           "--gridappsd-port", str(opts.gridappsd_port),
           "--username", opts.username,
           "--password", opts.password,
           "--subscription-topic", opts.publish_topic]
    print(cmd)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    # Set non-blocking process.
    os.set_blocking(proc.stdout.fileno(), False)
    return proc

main_running: bool = True
reset_stats: bool = False
show_stats: bool = False

def gather_results_thread(proc_list: list[subprocess.Popen]):
    global main_running
    global reset_stats
    global show_stats

    print(proc_list)
    count_received = 0
    received_taken: dict[str, list[float]] = {}

    while main_running:
        if show_stats:
            for k, v in received_taken.items():
                count = len(v)
                total = sum(v)
                if count == 0:
                    print(f"No messages received for subscriber: {k}")
                else:
                    print(f"{k} received: {len(v)} messages, average: {total / count}")
            show_stats = False

        if reset_stats:
            count_received = 0
            sum_total = 0
            reset_stats = False
            show_stats = False
            received_taken.clear()

        for proc in proc_list:
            line = proc.stdout.readline()
            line = line.decode('utf-8')
            try:
                subscriber, start, end, taken = line.strip().split(',')
                if subscriber not in received_taken:
                    received_taken[subscriber] = []
                received_taken[subscriber].append(float(taken))

            except ValueError: # Happens because we aren't blocking so stream just comes in.
                if line != '':
                    print("The line is: {line}")

def publish_messages(count: int = 10, sleep_time: float = 1 / 60):
    gapps = GridAPPSD(stomp_address=opts.gridappsd_address,
                      stomp_port=opts.gridappsd_port,
                      username=opts.username,
                      password=opts.password)
    print(f"Publishing {count} messages as fast as possible")
    data_to_send = get_message_to_publish()
    gapps.connect()
    assert gapps.connected

    for i in range(10):
        ts_now = datetime.utcnow().timestamp()
        message = dict(start=ts_now, payload=data_to_send)
        gapps.send(opts.publish_topic, message=message)
        time.sleep(sleep_time)
    gapps.close()

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--gridappsd-address", default="localhost", type=str)
    parser.add_argument("--gridappsd-port", default=61613, type=int)
    parser.add_argument("--publish-topic", default="pmu.data", type=str)
    parser.add_argument("--username", default="system")
    parser.add_argument("--password", default="manager")
    opts = parser.parse_args()

    proc_list = [run_single_subscriber_no_blocking(subscriber_name="first", opts=opts)]

    results_thread = Thread(target=gather_results_thread, daemon=True, args=[proc_list])
    results_thread.start()




    def menu():
        print("""Test Runner Menu

  help - Show this help
  results - See Results of test
  reset - Reset results
  run - Run a test
  exit - Close the program down
""")
    menu()
    exit_yes = False
    while not exit_yes:
        result = input(">")

        match result.strip():
            case 'help':
                menu()
            case 'results':
                show_stats = True
            case 'quit' | 'exit':
                exit_yes = True
                break
            case 'run':
                publish_messages()
            case 'reset':
                reset_stats = True


    main_running = False
    for proc in proc_list:
        proc.terminate()

