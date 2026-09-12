"""The hindcast: a month that has happened, run blind, graded. Offline.

    python3 tests/test_hindcast.py

GIRO's tabulated text is parsed, the blind hour is assembled from it the way
the live feed would have shown it (latest reading at or before the hour,
within the age and confidence the live feed accepts), and a short synthetic
record is run through the model to a ledger and graded. No network: the
data here is made up to be recognisable, not fetched.
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
H.fetch = lambda start, end, codes=None, force=False: dict(syn, answered=["AL945"], silent=[])   # offline
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

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
