#!/usr/bin/env python3
"""The band conditions never wait on somebody else's server.

    python3 tests/test_sky_cache.py

A cache miss used to fetch three things one after another, inside the request:
hamqsl's XML and two SWPC feeds. None of them needs the answer to any other, so
end to end it cost three DNS lookups and three TLS handshakes, which on a
domestic link is most of the wall clock and none of the work. Measured on the
operator's own connection it was 419 ms in a row against 141 ms together, and
the unit's own pace log had /api/propagation at a p95 of 1379 ms - four times
the next slowest endpoint on the box.

Worse than the good day was the bad one. Each request is allowed fifteen
seconds, so a hamqsl that had gone quiet could hold the band conditions page
for the better part of a minute while a perfectly good reading sat in memory.

So: a reading past its window is still a reading. It is handed over at once and
marked as old, and the new one is fetched behind the page. Pressing Refresh
still waits, because that is somebody asking to be told something new, and a
unit with nothing cached at all still waits, because it has nothing else to
give. Nothing upstream is contacted by this test.
"""
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import propagation as P  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# Nothing real is fetched. The stand-ins count their calls and can be told to
# take a long time or to fail, which is what the bad day looks like.
CALLS = {"ham": 0, "swpc": 0}
HANG = {"seconds": 0.0}
BREAK = {"ham": False}


def fake_ham():
    CALLS["ham"] += 1
    if HANG["seconds"]:
        time.sleep(HANG["seconds"])
    if BREAK["ham"]:
        raise OSError("hamqsl.com has gone quiet")
    return {"conditions": {}, "vhf": {}, "solarflux": "150", "aindex": "5",
            "kindex": "2", "sunspots": "80", "updated": "now"}


def fake_swpc():
    CALLS["swpc"] += 1
    if HANG["seconds"]:
        time.sleep(HANG["seconds"])
    return {"kp": 2.0, "a_running": 5.0, "solar_wind": 400}


P._hamqsl, P._swpc = fake_ham, fake_swpc
HERE = {"lat": 46.60, "lon": -94.31}


def timed(**kw):
    t0 = time.perf_counter()
    got = P.snapshot(lat=HERE["lat"], lon=HERE["lon"], **kw)
    return (time.perf_counter() - t0) * 1000, got


def clear():
    with P._cache_lock:
        P._cache["at"], P._cache["data"], P._cache["where"] = None, None, None
    P._refreshing.clear()
    CALLS["ham"] = CALLS["swpc"] = 0


def age(minutes):
    with P._cache_lock:
        P._cache["at"] = P._cache["at"] - timedelta(minutes=minutes)


print("\nwith nothing cached, there is nothing else to give")
clear()
took, got = timed()
check("the first reading is fetched", got.get("ok"), True)
check("  from both sources", (CALLS["ham"], CALLS["swpc"]), (1, 1))
check("  and it is not marked as old", got.get("stale"), None)

print("\ninside the window, the held reading is the answer")
before = dict(CALLS)
took, got = timed()
check("nothing is fetched again", (CALLS["ham"], CALLS["swpc"]),
      (before["ham"], before["swpc"]))
check("  and it says it came from the cache", got.get("cached"), True)

print("\npast the window, the page is served at once and the fetch goes behind it")
age(P.CACHE_MINUTES + 5)
HANG["seconds"] = 1.5                 # the upstream is slow today
before = dict(CALLS)
took, got = timed()
check("the page did not wait for it", took < 400, True)
check("  it got the held reading", got.get("ok"), True)
check("  told plainly that it is old", got.get("stale"), True)
check("  with its age in minutes", got.get("age_minutes") >= P.CACHE_MINUTES, True)
check("  and that a new one is coming", got.get("refreshing"), True)
# The claim is that the page did not *wait*, which the timing above says. It
# is not that no fetch had begun: the refresh runs in a thread and marks the
# call as it starts, so on a loaded machine it can tick before this line runs.
# Counting calls here was measuring the scheduler, and it failed once in a
# full suite run having passed on its own three times.
check("  and it returned long before the fetch could have finished",
      took < HANG["seconds"] * 1000, True)
# The refresh is behind it, and lands.
for _ in range(60):
    time.sleep(0.1)
    if CALLS["ham"] > before["ham"] and not P._refreshing.is_set():
        break
check("the refresh happened behind the page", CALLS["ham"], before["ham"] + 1)
took, got = timed()
check("  and the next page gets a fresh reading", (got.get("stale"), took < 50), (None, True))

print("\nten pages on a stale cache send one refresh, not ten")
age(P.CACHE_MINUTES + 5)
before = dict(CALLS)
HANG["seconds"] = 0.6
for _ in range(10):
    P.snapshot(lat=HERE["lat"], lon=HERE["lon"])
check("ten reads, one refresh in flight", CALLS["ham"] - before["ham"] <= 1, True)
for _ in range(60):
    time.sleep(0.1)
    if not P._refreshing.is_set():
        break
check("  and when it lands, still one", CALLS["ham"] - before["ham"], 1)
HANG["seconds"] = 0.0

print("\nRefresh is somebody asking to be told something new, so it waits")
before = dict(CALLS)
took, got = timed(force=True)
check("it fetches, whatever the cache says", CALLS["ham"], before["ham"] + 1)
check("  and hands back the new reading", got.get("stale"), None)

print("\nan upstream that has gone quiet does not take the reading with it")
age(P.CACHE_MINUTES + 5)
BREAK["ham"] = True
before = dict(CALLS)
took, got = timed()
check("the page still gets the held reading", got.get("ok"), True)
check("  and is told it is old", got.get("stale"), True)
for _ in range(60):
    time.sleep(0.1)
    if not P._refreshing.is_set():
        break
with P._cache_lock:
    still_good = (P._cache["data"] or {}).get("ok")
check("the failed refresh did not overwrite it", still_good, True)
# And asked outright, the failure is reported rather than hidden.
took, got = timed(force=True)
check("asked outright, the failure is said", got.get("ok"), False)
check("  naming what could not be reached", "hamqsl" in (got.get("error") or ""), True)
BREAK["ham"] = False

print("\nmoving the station asks again rather than answering about the old place")
clear()
P.snapshot(lat=46.60, lon=-94.31)
before = dict(CALLS)
P.snapshot(lat=36.57, lon=-121.95)
check("a different place is fetched, not served from the last one",
      CALLS["ham"], before["ham"] + 1)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
