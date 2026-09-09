#!/usr/bin/env python3
"""Parks on the Air: what is kept, what is not, and what is never sent.

    python3 tests/test_pota.py

Nothing here touches the network - the fetch is replaced throughout, which is
also the point of one of the checks: a typed sentence must never turn into a
request at all.

The awards an operator has earned are public, and POTA publishes them keyed by
callsign with no key, no subscription and no password. That is why this module
exists and why there is no DXCC in it: the ARRL awards live behind the
operator's own Logbook of the World login, and a program that asked for that
password would be doing something quite different from a lookup.

What is guarded most carefully is what is thrown away. The endpoint returns the
operator's name, their town and a gravatar hash, and none of it is any of
ELMER's business - `elmer.callsign` set that precedent by discarding the name
and street address on the FCC record it reads, for the same reason.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import pota                                          # noqa: E402

FAILS = []

SAMPLE = {
    "id": 25549, "callsign": "KC9SP", "name": "A Real Person",
    "qth": "A Real Town, A Real County, MN", "gravatar": "deadbeefcafe",
    "grid": None, "sk": 0, "other_callsigns": [],
    "recent_activity": [{"park": "US-0001"}],
    "stats": {"activator": {"activations": 2, "parks": 2, "qsos": 40},
              "hunter": {"parks": 30, "qsos": 31},
              "awards": 3, "endorsements": 7},
    "awards": [
        {"name": "Bronze Hunter", "granted": "2022-07-30T17:48:39",
         "endorsements": ["20M", "DATA", "FT8"]},
        {"name": "Gold Hunter", "granted": "2026-01-20T15:15:09",
         "endorsements": []},
        {"name": "Silver Hunter", "granted": "2022-08-31T12:50:49",
         "endorsements": ["20M"]},
    ],
}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    calls = []

    def fake(call):
        calls.append(call)
        return SAMPLE

    pota.CACHE = Path(__file__).resolve().parent / "_pota_cache"
    for old in pota.CACHE.glob("*.json"):
        old.unlink()
    real_fetch, pota._fetch = pota._fetch, fake

    try:
        print("-- a callsign is a callsign before anything leaves the unit --")
        for junk in ("hello world", "ABCDEF", "12345", "", "  "):
            before = len(calls)
            out = pota.lookup(junk)
            check(f"{junk!r} is turned away", out["ok"], False)
            check("  and no request was made", len(calls), before)
        for good in ("KC9SP", "W1AW", "VE3ABC/M", "DL/KC9SP"):
            check(f"{good} is accepted as a callsign",
                  bool(pota.RE_CALL.match(pota.normalise(good))), True)
        check("and case does not matter", pota.normalise("kc9sp"), "KC9SP")

        print("\n-- what comes back, and what is dropped --")
        got = pota.lookup("KC9SP")
        check("the awards are kept", len(got["awards"]), 3)
        check("  the counts are kept", got["hunter"]["parks"], 30)
        check("  and the activator side too", got["activator"]["activations"], 2)
        # The three that are none of this program's business.
        blob = json.dumps(got)
        for gone, what in (("A Real Person", "the operator's name"),
                           ("A Real Town", "their town"),
                           ("deadbeefcafe", "their gravatar hash")):
            check(f"{what} is not stored", gone in blob, False)
        check("  nor is their recent activity", "recent_activity" in got, False)

        print("\n-- newest first, because that is the one they want to see --")
        check("the most recent award leads", got["awards"][0]["name"],
              "Gold Hunter")
        check("  and the dates are days, not timestamps",
              got["awards"][0]["granted"], "2026-01-20")
        check("  endorsements ride along",
              got["awards"][2]["endorsements"], ["20M", "DATA", "FT8"])

        print("\n-- asking twice costs one request --")
        before = len(calls)
        pota.lookup("KC9SP")
        check("the second answer came off the disk", len(calls), before)
        check("  and says so", pota.lookup("KC9SP").get("cached"), True)

        print("\n-- no record is not an error --")
        import urllib.error

        def missing(call):
            raise urllib.error.HTTPError("u", 404, "Not Found", None, None)

        pota._fetch = missing
        none = pota.lookup("W1ZZZ")
        check("a callsign with no POTA record", none["found"], False)
        check("  is reported plainly", "no POTA record" in none["error"], True)

        print("\n-- and no network falls back to what it knew --")
        def down(call):
            raise OSError("network is down")

        pota._fetch = down
        # Force the cached KC9SP entry to look old so a fetch is attempted.
        path = pota.CACHE / "KC9SP.json"
        stale = json.loads(path.read_text())
        stale["fetched_at"] = time.time() - (pota.MAX_AGE_SECONDS + 60)
        path.write_text(json.dumps(stale))
        offline = pota.lookup("KC9SP")
        check("the last known record is still shown", offline["found"], True)
        check("  with its awards", len(offline["awards"]), 3)
        check("  and marked stale", offline.get("stale"), True)
        check("a callsign never seen, with no network, says so",
              pota.lookup("K9ABC")["found"], False)

        print("\n-- one line for a panel with room for one --")
        check("it counts what there is",
              pota.summary(offline), "3 awards, 30 parks hunted, 2 activations")
        check("  and says nothing when there is nothing",
              pota.summary({"found": False}), "")
    finally:
        pota._fetch = real_fetch
        for old in pota.CACHE.glob("*.json"):
            old.unlink()
        if pota.CACHE.exists():
            pota.CACHE.rmdir()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
