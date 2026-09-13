#!/usr/bin/env python3
"""Quieting OP25 so a game has the Pi to itself - and only OP25.

    python3 tests/test_op25.py

KC9SP: OP25 "really consumes a Pi when it's running", a 3 especially, so
ELMER stops it when a game starts. The whole risk is precision: the obvious
`pkill -f op25` would match a shell sitting in ~/op25, an editor, a launch
script that names the app - anything with the path on its command line. So
what is proved here is that the finder catches the decoder itself and spares
everything that merely mentions it, never touches this process, and that the
whole thing is off when the operator says so.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import op25, db  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


TMP = Path(_isolate.STATE) / "multi_rx.py"
TMP.write_text("import time\ntime.sleep(120)\n")

print("\nthe finder catches the decoder and spares what only mentions it")
real = subprocess.Popen([sys.executable, str(TMP)])
decoy = subprocess.Popen(["bash", "-c", f"sleep 120 # {TMP} decoy"])
time.sleep(1.0)
try:
    pids = [p for p, _ in op25.find()]
    check("the real decoder is found", real.pid in pids, True)
    check("  a shell that only names it is spared", decoy.pid in pids, False)
    check("  this process is never in the list", os.getpid() not in pids, True)
finally:
    for p in (real, decoy):
        try:
            p.terminate(); p.wait(timeout=5)
        except Exception:
            p.kill()

print("\nstop() terminates the decoder and reports what it stopped")
real = subprocess.Popen([sys.executable, str(TMP)])
time.sleep(1.0)
stopped = op25.stop(reason="a test")
check("it reported one stopped", len(stopped), 1)
time.sleep(0.5)
check("  and it is gone", op25.find(), [])
check("  the child took the signal", real.poll() is not None, True)

print("\nthe switch and the pattern are the operator's")
conn = db.connect()
was_en = db.unit_get(conn, op25.ENABLED_SETTING)
was_m = db.unit_get(conn, op25.MATCH_SETTING)
try:
    check("on by default", op25.wanted(conn), True)
    check("  default pattern is the canonical app", op25.match_pattern(conn), "multi_rx.py")
    db.unit_set(conn, op25.ENABLED_SETTING, "off")
    check("switched off, stop_if_wanted does nothing",
          op25.stop_if_wanted(conn), [])
    db.unit_set(conn, op25.MATCH_SETTING, "boatbot")
    check("  and the pattern can be changed", op25.match_pattern(conn), "boatbot")
finally:
    db.unit_set(conn, op25.ENABLED_SETTING, was_en)
    db.unit_set(conn, op25.MATCH_SETTING, was_m)
    try:
        TMP.unlink()
    except OSError:
        pass

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
