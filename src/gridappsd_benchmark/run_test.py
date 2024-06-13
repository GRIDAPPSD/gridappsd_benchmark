from gridappsd import GridAPPSD
from threading import Thread
from argparse import Namespace
from datetime import datetime
import math
import logging

import os
from pathlib import Path
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pprint import pprint
from typing import IO

logging.getLogger().setLevel(logging.WARNING)

@dataclass
class Settings:
    num_subscribers: int = 1
    num_publishers: int = 1
    num_messages_to_publish: int = 10
    seconds_between_publishes: float = 1 / 60
    send_results_to_file: None | str = None

@dataclass
class AppState:
    main_running: bool = True
    reset_stats: bool = False
    show_stats: bool = False

settings = Settings()
app_state = AppState()

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
    #global main_running

    pth = Path(__file__).parent / 'single_subscriber.py'
    cmd = [sys.executable,
           pth.as_posix(),
           f"{subscriber_name}",
           "--gridappsd-address", f"{opts.gridappsd_address}",
           "--gridappsd-port", str(opts.gridappsd_port),
           "--username", f"{opts.username}",
           "--password", f"{opts.password}",
           "--subscription-topic", f"{opts.publish_topic}"]
    #print(' '.join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ.copy())
    # Set non-blocking process.
    os.set_blocking(proc.stdout.fileno(), False)
    os.set_blocking(proc.stderr.fileno(), False)
    while app_state.main_running:
        line = proc.stdout.readline()
        err = proc.stderr.readline()
        if line == b'Starting Subscription\n':
            break
        elif line:
            print(f"The line is: {line}")

        if err:
            print(f"The error is: {err}")
        #time.sleep(0.01)
    print("Subscriber Startup Complete")
    return proc

# main_running: bool = True
# reset_stats: bool = False
# show_stats: bool = False

def gather_results_thread(opts: Namespace, proc_list: list[subprocess.Popen]):
    # global main_running
    # global reset_stats
    # global show_stats
    # global settings

    count_received = 0
    received_taken: dict[str, list[float]] = {}
    # fh: IO[str] | None = None


    while app_state.main_running:
        # if settings.send_results_to_file:
        #     print(f"Writing results to file {settings.send_results_to_file}.")
        #     fh = open(settings.send_results_to_file, 'w')
        # elif fh and not settings.send_results_to_file:
        #     fh.close()
        #     fh = None
        #     print(f"Stopped writing results to file.")

        if settings.num_subscribers > len(proc_list):
            print(f"Creating Subscriber: {len(proc_list) + 1}")
            proc_list.append(run_single_subscriber_no_blocking(f"subscriber{len(proc_list) + 1}", opts))
            continue
        if settings.num_subscribers < len(proc_list):
            print(f"Terminating Subscriber: {len(proc_list)}")
            proc_list.pop().terminate()
            continue

        if app_state.show_stats:
            for k, v in received_taken.items():
                count = len(v)
                total = sum(v)
                if count == 0:
                    print(f"No messages received for subscriber: {k}")
                else:
                    print(f"{k} received: {len(v)} messages, average: {total / count}")
            if not received_taken.items():
                print("No messages received yet.")
            app_state.show_stats = False

        if app_state.reset_stats:
            count_received = 0
            sum_total = 0
            app_state.reset_stats = False
            app_state.show_stats = False
            received_taken.clear()

        for proc in proc_list:
            line = proc.stdout.readline()
            if not line:
                continue
            # if line:
            #     if fh:
            #         fh.write(line.decode('utf-8'))
            #         fh.flush()
            line = line.decode('utf-8')
            try:
                subscriber, start, end, taken = line.strip().split(',')
                if subscriber not in received_taken:
                    received_taken[subscriber] = []
                received_taken[subscriber].append(float(taken))

            except ValueError: # Happens because we aren't blocking so stream just comes in.
                if line != '':
                    print(f"The line is: {line}")

def publish_messages(opts: Namespace, count: int = 10, sleep_time: float = 1 / 60, count_publishers: int = 1):
    publishers: list[GridAPPSD] = []

    while count_publishers > len(publishers):
        gapps = GridAPPSD(stomp_address=opts.gridappsd_address,
                        stomp_port=opts.gridappsd_port,
                        username=opts.username,
                        password=opts.password)
        publishers.append(gapps)

    print(f"Publishing {count} messages, one every {sleep_time}s from {count_publishers} publishers.")
    data_to_send = get_message_to_publish()
    gapps.connect()
    assert gapps.connected

    for i in range(count):
        ts_now = datetime.utcnow().timestamp()
        message = dict(start=ts_now, payload=data_to_send)
        for gapps in publishers:
            gapps.send(opts.publish_topic, message=message)
            time.sleep(0.00001)
        time.sleep(sleep_time)

    for gapps in publishers:
        gapps.disconnect()


def menu():
    print("""Test Runner Menu

  help -            Show this help

  Settings:
    set-num-subscribers <int> -             Set number of subscribers
    set-num-publishers <int> -              Set number of publishers
    set-num-messages <int> -                Set number of messages to publish in a single test
    set-seconds-between-publishes <float> - Set number of seconds between publishes
    set-results-to-file <filename> -        Set the file to write results to

  show-settings -   Show current settings
  results -         See Results of running tests
  reset -           Reset results
  run -             Run a test
  run-range <int> - Run a range of tests

  exit/quit -       Close the program down
""")

def is_numeric_and_positive(val: str, can_be_float: bool = False) -> bool:
    if can_be_float:
        val = val.replace('.', '')
    # val = val.replace('.', '')
    return val.isnumeric() and int(val) > 0

def _main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--gridappsd-address", default="localhost", type=str)
    parser.add_argument("--gridappsd-port", default=61613, type=int)
    parser.add_argument("--publish-topic", default="/topic/pmu.data", type=str)
    parser.add_argument("--username", default="system")
    parser.add_argument("--password", default="manager")
    opts = parser.parse_args()

    menu()
    proc_list: list = []

    results_thread = Thread(target=gather_results_thread,
                            daemon=True,
                            args=[opts, proc_list])
    results_thread.start()
    exit_yes = False
    while not exit_yes:
        result = input(">")

        match result.strip():
            case 'help':
                menu()
            case 'results':
                app_state.show_stats = True
            case 'quit' | 'exit':
                exit_yes = True
                break
            case 'run':
                # print(f"Sending:\n{get_message_to_publish()}")
                publish_messages(count=settings.num_messages_to_publish,
                                 sleep_time=settings.seconds_between_publishes,
                                 count_publishers=settings.num_publishers)

            case s if s.startswith('run-range ') and is_numeric_and_positive(
                s.split()[1]):
                num_tests = int(s.split()[1])
                for i in range(num_tests):
                    print(f"Running test {i + 1} of {num_tests}")
                    publish_messages(
                        opts=opts,
                        count=settings.num_messages_to_publish,
                        sleep_time=settings.seconds_between_publishes,
                        count_publishers=settings.num_publishers)
                    app_state.show_stats = True
                app_state.show_stats = True
            case 'reset':
                app_state.reset_stats = True
            # case s if s.startswith('set-results-to-file '):
            #     settings.send_results_to_file = s.split()[1]
            #     if settings.send_results_to_file:
            #         print(
            #             f"Results will be written to: {settings.send_results_to_file}"
            #         )
            #     else:
            #         print("Results will not be written to a file.")
            #         settings.send_results_to_file = None
            case s if s.startswith('set-num-subscribers '
                                   ) and is_numeric_and_positive(s.split()[1]):
                settings.num_subscribers = int(s.split()[1])
            case s if s.startswith('set-num-publishers '
                                   ) and is_numeric_and_positive(s.split()[1]):
                settings.num_publishers = int(s.split()[1])
            case s if s.startswith(
                'set-num-messages ') and is_numeric_and_positive(s.split()[1]):
                settings.num_messages_to_publish = int(s.split()[1])
            case s if s.startswith(
                'set-seconds-between-publishes ') and is_numeric_and_positive(
                    s, can_be_float=True):
                settings.seconds_between_publishes = float(s.split()[1])
            case 'show-settings':
                pprint(asdict(settings))
            case s:
                if not s:
                    continue
                print(f"Invalid input: {s}")

        time.sleep(0.01)

    app_state.main_running = False
    for proc in proc_list:
        proc.terminate()

if __name__ == '__main__':
    _main()
