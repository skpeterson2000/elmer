#!/usr/bin/env python3
"""Checks for the RepeaterBook route: an operator's own token fetches the
state's amateur and GMRS machines into ELMER's list, credited, refreshed
monthly, and the token itself never reaches a log or a report.

    python3 tests/test_repeaterbook.py

RepeaterBook itself is not asked: its reply is played back from a sample of
the shape its export gives, so the check runs on a bench with no network.
"""
import io
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import bugreport, repeaters as R  # noqa: E402

FAILS = []
TOKEN = "rbuapp_0123456789abcdefTEST"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


SAMPLE = {
    "amateur": {"count": 3, "results": [
        {"State ID": "27", "Rptr ID": "1", "Frequency": "146.94000", "Input Freq": "146.34000", "PL": "100.0",
         "TSQ": "", "Nearest City": "Brainerd", "Landmark": "Water tower", "County": "Crow Wing",
         "State": "Minnesota", "Country": "United States", "Lat": "46.3580", "Long": "-94.2008", "Precise": 1,
         "Callsign": "W0ABC", "Use": "OPEN", "Operational Status": "On-air", "FM Analog": "Yes", "DMR": "No",
         "D-Star": "No", "System Fusion": "Yes", "NXDN": "No", "APCO P-25": "No", "M17": "No",
         "Notes": "", "Last Update": "2026-08-01"},
        {"State ID": "27", "Rptr ID": "2", "Frequency": "444.10000", "Input Freq": "449.10000", "PL": "",
         "Nearest City": "Nisswa", "Landmark": "", "County": "Crow Wing", "State": "Minnesota",
         "Lat": "46.52", "Long": "-94.29", "Precise": 0, "Callsign": "N0DEF", "Operational Status": "Unknown",
         "FM Analog": "No", "DMR": "Yes", "DMR Color Code": "1", "D-Star": "No"},
        {"State ID": "27", "Rptr ID": "3", "Frequency": "147.00000", "Input Freq": "147.60000", "PL": "94.8",
         "Nearest City": "Baxter", "County": "Crow Wing", "State": "Minnesota", "Lat": "46.34", "Long": "-94.28",
         "Precise": 1, "Callsign": "K0OFF", "Operational Status": "Off-air", "FM Analog": "Yes"},
    ]},
    "gmrs": {"count": 1, "results": [
        {"State ID": "27", "Frequency": "462.67500", "Input Freq": "467.67500", "PL": "141.3",
         "Nearest City": "Brainerd", "County": "Crow Wing", "State": "Minnesota", "Lat": "46.36", "Long": "-94.20",
         "Precise": 1, "Callsign": "WRXX123", "Operational Status": "On-air", "FM Analog": "Yes"},
    ]},
}
SEEN = []


class _Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(request, timeout=None):
    SEEN.append(request)
    url = request.full_url
    which = "gmrs" if "stype=gmrs" in url else "amateur"
    if request.get_header("X-rb-app-token") != TOKEN:
        return _Reply(json.dumps({"ok": False, "error_code": "auth_invalid"}).encode())
    return _Reply(json.dumps(SAMPLE[which]).encode())


def main():
    with tempfile.TemporaryDirectory() as tmp:
        R.STORE = Path(tmp) / "repeaters.json"
        R._cache["key"] = None
        real = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            return run()
        finally:
            urllib.request.urlopen = real


def run():
    print("\n-- the token's shape --")
    check("a RepeaterBook user token is recognized", R.token_looks_right(TOKEN), True)
    check("  a stray word is not", R.token_looks_right("my password"), False)
    check("  nor nothing", R.token_looks_right(""), False)

    print("\n-- the ask --")
    rows, error = R.from_repeaterbook("MN", TOKEN)
    check("no error", error, None)
    req = SEEN[-1]
    check("the state goes as its FIPS number", "state_id=27" in req.full_url, True)
    check("the token goes in RepeaterBook's header", req.get_header("X-rb-app-token"), TOKEN)
    ua = req.get_header("User-agent")
    check("the User-Agent names the program, its home and a contact", "ELMER/" in ua and "github.com" in ua and "@" in ua, True)
    check("  and not the operator", "skptrsn" in ua, False)
    check("two on-air machines came back; the off-air one did not", sorted(r["call"] for r in rows), ["N0DEF", "W0ABC"])
    w0 = next(r for r in rows if r["call"] == "W0ABC")
    check("frequency, input, offset, tone", (w0["output"], w0["input"], w0["offset"], w0["tone"]), (146.94, 146.34, -0.6, "100.0"))
    check("  the site named town - landmark", w0["location"], "Brainerd - Water tower")
    check("  the modes read off the flags", w0["modes"], "FM, YSF")
    check("  placed precisely", w0["approx"], False)
    n0 = next(r for r in rows if r["call"] == "N0DEF")
    check("  a machine RepeaterBook could not place precisely is marked approximate", n0["approx"], True)
    check("  a digital-only machine says so", n0["modes"], "DMR")
    _, error = R.from_repeaterbook("MN", "rbuapp_wrongwrongwrong")
    check("a refused token is said plainly", "did not accept the token" in error, True)
    check("a build RepeaterBook does not know by name is the author's errand, and says so",
          "author" in R._rb_refusal({"ok": False, "error_code": "ua_mismatch"}), True)
    check("  and a revoked token its owner's", "revoked" in R._rb_refusal({"ok": False, "error_code": "auth_revoked"}), True)
    _, error = R.from_repeaterbook("ON", TOKEN)
    check("a place RepeaterBook does not number is said plainly", "not one it knows" in error, True)

    print("\n-- into ELMER's list --")
    R.save([R._row("W0OLD", 146.94, location="Brainerd", lat=46.3, lon=-94.2, approx=True),
            R._row("W0ABC", 146.94, location="Brainerd", county="Crow Wing", lat=46.0, lon=-94.0, approx=True)],
           "TowerWitch (/x)")
    ok, message, count = R.fetch_repeaterbook("MN", TOKEN)
    check("fetched", (ok, count), (True, 3))
    check("  and said what came", message, "2 amateur and 1 GMRS repeaters for MN from RepeaterBook")
    rows, source = R.load()
    check("the older export's row for the same machine gave way to RepeaterBook's", next(r["approx"] for r in rows if r["call"] == "W0ABC"), False)
    check("  a machine only the export knew is still there", any(r["call"] == "W0OLD" for r in rows), True)
    check("  the GMRS machine is in, as GMRS", next(r["service"] for r in rows if r["call"] == "WRXX123"), "gmrs")
    check("  the sources named once each", source, "TowerWitch (/x) and RepeaterBook.com")
    check("  the credit written with the list", json.loads(R.STORE.read_text())["credit"], R.RB_CREDIT)
    check("the state is now fresh", R.rb_fresh("MN"), True)
    asked = len(SEEN)
    ok, message, count = R.fetch_repeaterbook("MN", TOKEN)
    check("  so a second ask within the month asks RepeaterBook nothing", (ok, count, len(SEEN) - asked), (True, 0, 0))
    ok, message, count = R.fetch_repeaterbook("MN", TOKEN, force=True)
    check("  unless pressed for", (ok, len(SEEN) - asked), (True, 2))
    near, _ = R.nearby(46.60, -94.31, None, limit=8, service="gmrs")
    check("and the GMRS machine is offered from the list", [r["call"] for r in near], ["WRXX123"])

    print("\n-- the token stays home --")
    check("a report redacts a token that somehow reached the log",
          bugreport.redact(f"settings saved token={TOKEN} ok"), "settings saved token=[token] ok")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
