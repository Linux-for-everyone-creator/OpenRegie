"""Tut so, als wäre es OBS: schreibt seine Startargumente in eine Datei und wartet,
bis es beendet wird. Mit OPENREGIE_TEST_ABSTURZ=1 „stürzt“ es nach kurzer Zeit ab."""
import json
import os
import signal
import sys
import time

with open(os.environ["OPENREGIE_TEST_DATEI"], "w") as f:
    json.dump(sys.argv[1:], f)

def ende(*_):
    with open(os.environ["OPENREGIE_TEST_DATEI"] + ".ende", "w") as f:
        f.write("sauber")
    sys.exit(0)

signal.signal(signal.SIGTERM, ende)
if os.environ.get("OPENREGIE_TEST_ABSTURZ"):
    time.sleep(0.3)
    os._exit(3)
while True:
    time.sleep(0.05)
