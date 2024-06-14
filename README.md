# GridAPPS-D Benchmark Testing

This package is a benchmark throughput test designed to test the internal message bus for GridAPPS-D.

## Third Party Code Inclusion

We include the `syncorphasor` [https://github.com/iicsys/pypmu](https://github.com/iicsys/pypmu) source code in our benchmark tool for setting up the payload for this benchmark.  We were unable to install it from pypi via a wheel so the easiest was to include it here.  Both that library and this are licensed under BSD-3-Clause.

## Execution Requirements

The benchmark requires a GridAPPS-D server running with accessible ip and port from the
benchmark running machine.  This is defaulted to localhost, 61613 (ip, port) for the main
benchmark.

To build the benchmark, poetry is required.

### Quick Setup of Poetry

1. Execute `curl -sSL https://install.python-poetry.org | python3 -`
2. Add `export PATH="/home/os2204/.local/bin:$PATH"` to your ~/.bashrc file.
3. Execute source ~/.bashrc to reload the shell.

### Quick Setup of Benchmark

1. Clone this repository `https://github.com/GRIDAPPSD/gridappsd_benchmark`
2. cd into gridappsd_benchmark
3. Execute `poetry install`

### Quick Setup of GridAPPS-D

1. Clone `https://github.com/GRIDAPPSD/gridappsd-docker`
2. cd into gridappsd-docker
3. Execute ./run.sh -t develop
4. Execute ./run-gridappsd.sh

## Test Creation

### Help for executing the benchmark

```bash

cd gridappsd_benchmark

# Activates the poetry environment
poetry shell

gridappsd-scale --help

usage: gridappsd-scale [-h] [--gridappsd-address GRIDAPPSD_ADDRESS] [--gridappsd-port GRIDAPPSD_PORT] [--publish-topic PUBLISH_TOPIC] [--username USERNAME] [--password PASSWORD]

options:
  -h, --help            show this help message and exit
  --gridappsd-address GRIDAPPSD_ADDRESS
                        The ip address of the gridappsd instance to connect to for all connections.
  --gridappsd-port GRIDAPPSD_PORT
                        The port of the gridappsd instance to connect to for all connections.
  --publish-topic PUBLISH_TOPIC
                        The topic to publish messages to and subscribe to for all connections. Note: This should start with /topic/ or a queue will be created instead.
  --username USERNAME   The username to use for all connections.
  --password PASSWORD   The password to use for all connections.
```

The gridappsd-scale command can be used to start the configurations of tests.

Executing `gridappsd-scale` will create a command line environment for setting various options and
running tests against the default local GridAPPS-D environment.

```bash
gridappsd-scale
Test Runner Menu

  help -            Show this help

  Settings:
    set-num-subscribers <int> -             Set number of subscribers
    set-num-publishers <int> -              Set number of publishers
    set-num-messages <int> -                Set number of messages to publish in a single test
    set-seconds-between-publishes <float> - Set number of seconds between publishes

  show-settings -   Show current settings
  results -         See Results of running tests
  reset -           Reset results
  run -             Run a test
  run-range <int> - Run a range of tests

  exit/quit -       Close the program down

Creating Subscriber: 1
>Subscriber Startup Complete
```

At this point you can specify the number of subscribers, publishers seconds between messages using the
menu output.  You can show your default settings by typing show-settings and hitting enter.  Note
the  seconts_between_publish defaults to 1/60th of a second.

```bash
...
show-settings
{'num_messages_to_publish': 10,
 'num_publishers': 1,
 'num_subscribers': 1,
 'seconds_between_publishes': 0.016666666666666666,
 'send_results_to_file': None}
>
```

Running a test next will start the publisher and send 10 messages across the message bus.  The
single subscriber will receive the messages and the time from the publish to the reciever will be
calculated.

```bash
...
>run
Subscriber Startup Complete
Publishing 10 messages, one every 0.016666666666666666s from 1 publishers.
>
...
```

Subsiquent runs will each publish 10 messages.  Once all runs have been completed one
can see the results.

```bash
...
>results
subscriber1 received: 20 messages, average: 0.010016918182373047
```

Note the above showed 20 messages because I ran the `run` method twice.  To reset the
data you can use the reset command.

## Developer Notes

The benchmark uses subprocess to start processes in their own containers and uses sys.stdout
from the processes to capture the data.  Each subscriber is one instance of single_subscriber.py.  Currently
all of the publishers are created within a single thread.

