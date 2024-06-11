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

from argparse import Namespace
from multiprocessing import Process
from datetime import datetime
from gridappsd import GridAPPSD
import time

PUBLISH_FREQUENCY = 1/60
def run_publisher(pub_id: int, opts: Namespace):
    print(f"Starting publisher {pub_id}")

    gapps = GridAPPSD(stomp_port=opts.gridappsd_port,
                      stomp_address=opts.gridappsd_address,
                      username=opts.username,
                      password=opts.password)

    message_number = 0
    published_message_times: list[float] = []
    while True:

        ts_now = datetime.utcnow().timestamp()

        message = dict(start=ts_now, payload=data_to_send.hex())
        gapps.send(opts.publish_topic, message)
        published_message_times.append(ts_now)
        message_number += 1
        if message_number > opts.num_messages:
            break
        time.sleep(PUBLISH_FREQUENCY)

    gapps.disconnect()

    for p in published_message_times:
        print(p)



if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "num_publishers",
        type=int,
        help="How many publishers started.  Must be >= 1")
    parser.add_argument("--gridappsd-address", default="localhost", type=str)
    parser.add_argument("--gridappsd-port", default=61613, type=int)
    parser.add_argument("--publish-topic", default="pmu.data", type=str)
    parser.add_argument("--username", default="system")
    parser.add_argument("--password", default="manager")
    parser.add_argument("--num-messages", default=20, type=int)
    opts = parser.parse_args()

    procs: list[Process] = []
    for p in range(opts.num_publishers):
        proc = Process(target=run_publisher, args=[p, opts])
        proc.daemon = True
        proc.start()
        procs.append(proc)

    while num_procs := len(procs):
        if not procs[num_procs - 1].is_alive():
            procs.pop(num_procs - 1).join()

        time.sleep(0.00000001)

