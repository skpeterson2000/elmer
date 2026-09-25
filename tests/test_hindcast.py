"""The hindcast: a month that has happened, run blind, graded. Offline.

    python3 tests/test_hindcast.py

GIRO's tabulated text is parsed, the blind hour is assembled from it the way
the live feed would have shown it (latest reading at or before the hour,
within the age and confidence the live feed accepts), and a short synthetic
record is run through the model to a ledger and graded. No network: the
data here is made up to be recognizable, not fetched.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401
from elmer import hindcast as H  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


GIRO_TEXT = """# Global Ionospheric Radio Observatory (GIRO)
# Location: GEO ( 45.1 N   276.4 E ), URSI-Code AL945, ALPENA
# Time                    CS   foF2 QD   hmF2 QD MUF(D) QD   M(D) QD
2026-09-10T00:00:00.000Z  80  6.075 //  249.6 // 19.888 //   3.27 //
2026-09-10T00:15:00.000Z  70  5.875 //  251.0 //    --- __    --- __
2026-09-10T00:30:00.000Z  10  9.900 //  240.0 // 30.000 //   3.03 //
2026-09-10T00:45:00.000Z  80    --- //  252.0 //    --- __    --- __
"""

print("\nGIRO's table is read")
rows = H.parse_giro(GIRO_TEXT)
check("three usable rows - a line with no foF2 is no reading", len(rows), 3)
check("  the first carries frequency, height, MUF and the M factor",
      (rows[0]["fof2"], rows[0]["hmf2"], rows[0]["mufd"], rows[0]["md"], rows[0]["cs"]),
      (6.075, 249.6, 19.888, 3.27, 80.0))
check("  a value the scaler could not produce is None, not zero", rows[1]["mufd"], None)

print("\nthe blind hour sees what the live feed would have shown")
data = {"stations": {"AL945": rows}, "kp": [["2026-09-09T21:00:00Z", 1.0], ["2026-09-10T00:00:00Z", 3.0]],
        "f107": [["2026-09-09T20:00:00", 105.0], ["2026-09-10T20:00:00", 112.0]]}
at = datetime(2026, 9, 10, 0, 40, tzinfo=timezone.utc)
seen = H.sondes_at(data, at)
check("the latest reading at or before the hour", (len(seen), seen[0]["fof2"]), (1, 5.875))
check("  not the later one at 00:30 that the scaler graded 10 - it is refused, so 00:15 stands",
      seen[0]["time"][11:16], "00:15")
check("  with the station's own place and name", (seen[0]["name"], seen[0]["lat"]), ("Alpena, MI, USA", 45.07))
check("  and its age in minutes", seen[0]["age_minutes"], 25)
check("nothing is seen before the first reading", H.sondes_at(data, datetime(2026, 9, 9, 23, 0, tzinfo=timezone.utc)), [])
check("a reading four hours old has gone stale",
      H.sondes_at(data, datetime(2026, 9, 10, 5, 0, tzinfo=timezone.utc)), [])
check("the flux is the most recent at or before the hour", H.sfi_at(data, at), 105.0)
check("  and Kp the block containing it", H.kp_at(data, at), 3.0)
check("  before any Kp, the first known", H.kp_at(data, datetime(2026, 9, 9, 1, 0, tzinfo=timezone.utc)), 1.0)

print("\na short record runs blind to a ledger and is graded")
# Two days of a station that reads 6 MHz all night and 9 by day, every 15 min.
start = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
made = []
t = start - timedelta(hours=6)
while t < start + timedelta(days=2, hours=6):
    lit = 14 <= t.hour <= 23
    made.append({"time": t.isoformat().replace("+00:00", ".000Z"), "cs": 90,
                 "fof2": 9.0 if lit else 6.0, "hmf2": 250.0 if lit else 320.0,
                 "mufd": (9.0 if lit else 6.0) * 3.0, "md": 3.0})
    t += timedelta(minutes=15)
syn = {"stations": {"AL945": made},
       "kp": [[(start + timedelta(hours=3 * i)).isoformat().replace("+00:00", "Z"), 1.3] for i in range(-2, 20)],
       "f107": [[(start + timedelta(days=d)).isoformat()[:19], 110.0] for d in range(-1, 4)]}
end = start + timedelta(days=2)
res = H.run(start, end, 45.5, -84.0, syn, build="test", ledger=H.CACHE / "ledger-test")
check("every hour was forecast", res["hours"], 49)
check("  every hour had the station in reach", res["hours_with_reading"], 49)
check("  and the ledger was written where asked", Path(res["ledger"]).is_dir() and any(Path(res["ledger"]).glob("*.json")), True)
# A long run must keep every day it forecast: the live unit's sixty-day
# pruning once graded a year as its last two months.
far = start - timedelta(days=400)
old_run = H.run(far, far + timedelta(days=1), 45.5, -84.0,
                {"stations": {"AL945": [dict(r, time=(datetime.fromisoformat(r["time"].replace("Z", "+00:00")) - timedelta(days=400)).isoformat().replace("+00:00", ".000Z")) for r in made]},
                 "kp": [[(far + timedelta(hours=3 * i)).isoformat().replace("+00:00", "Z"), 1.3] for i in range(-2, 20)],
                 "f107": [[(far + timedelta(days=d)).isoformat()[:19], 110.0] for d in range(-1, 4)]},
                build="test-old", ledger=H.CACHE / "ledger-old")
check("  a run four hundred days back keeps its days", len(list((H.CACHE / "ledger-old").glob("*.json"))) >= 2, True)
check("  and the live keep window is back afterwards", (F_KEEP := __import__("elmer.forecastlog", fromlist=["KEEP_DAYS"]).KEEP_DAYS) == 60, True)
sk = res["skill"]
check("  forecast-hours were scored", sk["n"] > 200, True)
check("  by sky and by lead", ("lit" in sk["by_regime"] or "dark" in sk["by_regime"], "24" in sk["by_lead"]), (True, True))
check("  persistence has a number too - the yardstick", sk["persistence_24h"]["n"] > 0, True)
check("  the adjustment says how many measured hours it stands on",
      all(v["n"] > 0 for v in res["adjustment"].values()), True)
text = H.report(res)
check("the report acknowledges the data providers by station", "AL945" in text and "CC-BY-NC-SA" in text, True)
check("  and names the yardstick", "persistence" in text, True)

print("\nthe calibration job runs the two passes and hands the forecast the table")
import time as _time
from elmer import calibrate as C, forecastlog as F


def fake_fetch(flux_days=None, stations=True, trouble=None):
    """An offline fetch: the synthetic two-day record, moved onto whatever
    span the job asks for. `flux_days` limits the flux to that many days
    before the end; `stations` False is a GIRO that answered nobody."""
    def fetch(start, end, codes=None, force=False, notice=None):
        shift = (start - datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc))
        span = int((end - start).total_seconds() // 86400) + 3
        rows = [dict(r, time=(datetime.fromisoformat(r["time"].replace("Z", "+00:00")) + shift)
                     .isoformat().replace("+00:00", ".000Z")) for r in made]
        out = {"stations": {"AL945": rows} if stations else {},
               "kp": [[(start + timedelta(hours=3 * i)).isoformat().replace("+00:00", "Z"), 1.3]
                      for i in range(-8, span * 8)],
               "f107": [[(start + timedelta(days=d)).isoformat()[:19], 110.0]
                        for d in range(-1, span)
                        if flux_days is None or (end - (start + timedelta(days=d))).days < flux_days],
               "answered": ["AL945"] if stations else [], "silent": [] if stations else ["AL945"],
               "sources": {"kp": "test", "f107": "test"}, "trouble": trouble or []}
        return out
    return fetch


H.fetch = fake_fetch()   # offline
st = C.start(45.5, -84.0, days=2, build="t", place="Test")
check("it starts", st["state"] in ("queued", "fetching", "running"), True)
for _ in range(600):
    st = C.status()
    if st["state"] in ("done", "failed", "stopped"):
        break
    _time.sleep(0.1)
check("  and finishes", (st["state"], st["error"]), ("done", None))
check("  with the year's fraction at one", st["fraction"], 1.0)
check("  something found to say", len(st["findings"]) >= 2, True)
check("  a result with before and after", sorted(st["result"]), ["after", "before", "table"])
check("  and the table saved for the live forecast", F.calibration() is not None and "months" in F.calibration(), True)
check("a second start while idle is a new job", C.start(45.5, -84.0, days=2, build="t", place="Test")["state"] in ("queued", "fetching", "running"), True)
check("  stop stops it", C.stop(), True)

print("\nthe record is fetched with patience, and read for what it covers")
CANADA = """fluxdate    fluxtime    fluxjulian    fluxcarrington  fluxobsflux  fluxadjflux  fluxursi
----------  ----------  ------------  --------------  -----------  -----------  ----------
20250925    170000      2460944.197   2302.604        0175.3       0176.3       0158.7
20250925    200000      2460944.322   2302.60         0170.4       0171.4       0154.2
20250925    230000      2460944.447   2302.61         0168.2       0169.2       0152.2
20250926    170000      2460945.197   2302.640        0166.0       0167.0       0150.3
"""
rows = H.parse_canada_flux(CANADA)
check("Penticton's table gives one flux a day, the noon reading", rows, [["2025-09-25T20:00:00", 170.4], ["2025-09-26T20:00:00", 166.0]])
cov = H.coverage(syn, start, end)
check("the synthetic record covers its span", (cov["f107"], cov["kp"] > 0.9), (1.0, True))
thin = dict(syn, f107=[[(end - timedelta(days=1)).isoformat()[:19], 110.0]])
cov = H.coverage(thin, start, end)
check("  a record with one day of flux says so", (cov["f107"] < 0.5, cov["f107_from"]), (True, (end - timedelta(days=1)).strftime("%Y-%m-%d")))
check("a flux reading from months away is no reading",
      H.sfi_at(syn, start + timedelta(days=200)), None)
check("  nor is Kp - quiet is assumed", H.kp_at(syn, start + timedelta(days=200)), 2.0)
check("  but a day or two of gap is bridged", H.sfi_at(syn, start + timedelta(days=4, hours=12)), 110.0)
res_far = H.run(start, start + timedelta(days=300), 45.5, -84.0, syn, build="test-far", ledger=H.CACHE / "ledger-far")
check("a run that outlives its flux stops and says why",
      (res_far["hours"] < 24 * 10, "no flux reading" in (res_far["stopped"] or "")), (True, True))

# A server that is busy twice and then answers: the request is tried
# again, the wait is said, and the body comes back.
import io as _io
import urllib.error as _ue
calls, said, slept = [], [], []
H.time.sleep = lambda s: slept.append(s)


def busy_then_ok(request, timeout=None, context=None):
    calls.append(request.full_url)
    if len(calls) < 3:
        raise _ue.HTTPError(request.full_url, 429, "Too Many Requests", {"Retry-After": "7"}, _io.BytesIO(b""))

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"fine"
    return R()


real_urlopen = H.urllib.request.urlopen
H.urllib.request.urlopen = busy_then_ok
check("a busy server is asked again and answers the third time", H._get("https://example.test/x", notice=said.append, what="GIRO (AL945)"), "fine")
check("  it waited what the server asked", slept, [7.0, 14.0])
check("  and said so, in words", said[0], "GIRO (AL945) it is busy and asked us to wait; trying again in 7 s.")
calls.clear()
slept.clear()


def never(request, timeout=None, context=None):
    calls.append(1)
    raise _ue.URLError("getaddrinfo failed")


H.urllib.request.urlopen = never
try:
    H._get("https://example.test/x", what="GFZ")
    check("a server that never answers is given up on", "raised", "Unavailable")
except H.Unavailable as exc:
    check("a server that never answers is given up on, in words", str(exc), "GFZ: there is no route to it - is the network up?")
check("  after the tries allowed", len(calls), H.TRIES)
H.urllib.request.urlopen = real_urlopen
H.time.sleep = _time.sleep if "_time" in dir() else __import__("time").sleep

print("\nthe calibration job runs on what the record covers, and says so when it cannot")
from elmer import calibrate as C2
H.fetch = fake_fetch(flux_days=1)
st = C2.start(45.5, -84.0, days=2, build="t2", place="Test")
# The job is a real hindcast on a thread, and this waits for it to reach a
# terminal state. Thirty seconds was enough on any machine anybody runs this
# on by hand and not enough on a loaded CI runner, where it failed once with
# the job still fetching - a red build that said nothing about the code. Two
# minutes is past anything the work takes and still bounded, and the state it
# was stuck in is reported rather than compared against.
_t = __import__("time")
_deadline = _t.time() + 120
while _t.time() < _deadline:
    st = C2.status()
    if st["state"] in ("done", "failed", "stopped"):
        break
    _t.sleep(0.1)
else:
    print(f"  note  the job never finished; it was {st['state']!r} after 120 s")
check("with one day of flux in a two-day span, the job stops in words", st["state"], "failed")
check("  that name the trouble, not a traceback",
      ("solar flux record could not be fetched" in (st["error"] or ""), "Traceback" in (st["error"] or "")), (True, False))
H.fetch = fake_fetch(stations=False, trouble=["GFZ's archive of Kp and flux did not answer (it is busy and asked us to wait)."])
C2._job = None
C2.Job.run.__globals__["hindcast"].fetch = H.fetch
job = C2.Job(45.5, -84.0, 2, "t3", "Test")
job.stop.wait = lambda s: True          # the 45 s rest is skipped: the stop is pressed
job.run()
check("no sonde at all, and the job is stopped rather than run", job.state, "stopped")

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
