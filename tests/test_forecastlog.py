"""The forecast's own record: skill, the learned adjustment, and drift.

    python3 tests/test_forecastlog.py

A synthetic fortnight is written into an isolated ledger: the model
forecasts a MUF that runs 1.8 MHz under what the sondes then measure at
night and 0.2 over by day. The record has to say so with an n behind it,
turn the night bias into a capped correction once enough readings agree,
refuse a bias past the cap, and tell a shape change with the sky still
from one with the sky moving or the build changing.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401
from elmer import forecastlog as F  # noqa: E402
from elmer import propagation as P  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


NOW = datetime(2026, 9, 12, 6, 0, tzinfo=timezone.utc)


def regime_at(t):
    # Sunlit 13Z-00Z at this longitude, grey either side, dark otherwise -
    # a stand-in for the sun, since this is about the ledger, not the sky.
    h = t.hour
    if 14 <= h <= 23:
        return "lit"
    if h in (13, 0):
        return "grey"
    return "dark"


def model_muf(t):
    return 12.0 if regime_at(t) != "lit" else 18.0


def bands_for(start, build="aaaaaaa", shape=0):
    hours = [start + timedelta(hours=i) for i in range(25)]
    rows = [{"at": t.isoformat(), "muf": model_muf(t), "regime": regime_at(t),
             "score": (60 if regime_at(t) == "lit" else 85) + shape, "day": regime_at(t) == "lit"}
            for t in hours]
    return [{"band": "40m", "hours": rows}, {"band": "20m", "hours": [dict(r, score=100 - r["score"]) for r in rows]}]


INPUTS = {"sfi": 110, "k_index": 1.3, "muf_now": 12.0, "muf_source": "measured",
          "fof2": 4.4, "hmf2": 245, "hmf2_measured": True, "m3000": 2.8, "lat": 46.36, "lon": -94.2}

print("\nthe ledger is the isolated state's")
check("under ELMER_STATE", str(F.LEDGER).startswith(__import__("os").environ["ELMER_STATE"]), True)

print("\na fortnight of forecasts and readings")
first = NOW - timedelta(days=14)
t = first
while t < NOW:
    F.record(bands_for(t), INPUTS, "aaaaaaa", now=t)
    # What the sondes then said: the model runs 1.8 low at night, 0.2 high by day.
    truth = model_muf(t) + (1.8 if regime_at(t) != "lit" else -0.2)
    F.measured({"muf_source": "measured", "muf": truth, "fof2": 4.0, "regime": regime_at(t),
                "calibration": {"stations": 3, "nearest_km": 900}}, now=t)
    t += timedelta(hours=1)
check("one file a day", len(list(F.LEDGER.glob("????-??-??.json"))) >= 14, True)
check("  one entry per hour, a reload replacing rather than repeating",
      len(F._load(F._day(first))["forecasts"]), 24 - first.hour if first.hour else 24)
again = F.record(bands_for(first), INPUTS, "aaaaaaa", now=first + timedelta(minutes=20))
check("  the same hour written twice is one entry", len(F._load(F._day(first))["forecasts"]), 24 - first.hour if first.hour else 24)

print("\nskill: what was said against what was measured")
# The reading for this hour arrives with the page, as it does in the route.
F.measured({"muf_source": "measured", "muf": 13.8, "fof2": 4.0, "regime": "dark",
            "calibration": {}}, now=NOW)
sk = F.skill(days=7, now=NOW)
check("errors were collected", sk["n"] > 100, True)
check("  the night bias is the one planted, forecast minus measured",
      sk["by_regime"]["dark"]["bias"], -1.8)
check("  the day bias too", sk["by_regime"]["lit"]["bias"], 0.2)
check("  by lead as well", "24" in sk["by_lead"] and sk["by_lead"]["24"]["n"] > 0, True)
check("  and the one-line version: yesterday's word for this hour against the sondes",
      (sk["latest"] or {}).get("lead_h") is not None and sk["latest"]["forecast"] == 12.0
      and round(sk["latest"]["measured"], 1) == 13.8, True)

print("\nthe adjustment: learned, capped, labelled")
adj = F.adjustment(now=NOW)
check("night: enough readings, bias measured, correction applied",
      (adj["dark"]["enough"], adj["dark"]["measured_bias"], adj["dark"]["applied"]), (True, 1.8, 1.8))
check("  day: the small bias is applied as measured", adj["lit"]["applied"], -0.2)
check("  the offsets handed to the model are only the applied ones",
      F.applied_bias(adj), {k: v["applied"] for k, v in adj.items() if v["applied"]})

print("\nwith too few readings nothing is applied")
few = F.adjustment(days=1, now=first + timedelta(hours=30))
check("a day's worth is not enough to act on", all(not v["applied"] for v in few.values()), True)
check("  but is still measured and said", all(v["n"] > 0 for v in few.values()), True)

print("\na bias past the cap is reported, not applied")
wild = NOW + timedelta(days=30)
t = wild - timedelta(days=3)
while t < wild:
    F.record(bands_for(t), INPUTS, "aaaaaaa", now=t)
    F.measured({"muf_source": "measured", "muf": model_muf(t) + 6.0, "fof2": 4.0,
                "regime": regime_at(t), "calibration": {}}, now=t)
    t += timedelta(hours=1)
capped = F.adjustment(days=3, now=wild)
check("six megahertz is a broken station or a different sky",
      (capped["dark"]["capped"], capped["dark"]["applied"], capped["dark"]["measured_bias"]), (True, 0.0, 6.0))

print("\nthe model takes the learned bias where the reading has let go")
plain = P.outlook(14.0, 46.36, -94.2, sfi=110, start=NOW, muf_now=12.0)
lifted = P.outlook(14.0, 46.36, -94.2, sfi=110, start=NOW, muf_now=12.0, bias={"dark": 1.8, "lit": -0.2})
check("the anchored hour is untouched - the reading is the level there",
      lifted[0]["muf"], plain[0]["muf"])
far_dark = [i for i, r in enumerate(plain) if i >= 12 and r["regime"] == "dark"]
check("  a dark hour past the anchor is lifted by the bias",
      far_dark and abs((lifted[far_dark[0]]["muf"] - plain[far_dark[0]]["muf"]) - 1.8) < 0.15, True)
check("  and its critical frequency moved with it",
      far_dark and lifted[far_dark[0]]["fof2"] > plain[far_dark[0]]["fof2"], True)

print("\ndrift: the shape moving without the sky moving")
a = F.record(bands_for(NOW), INPUTS, "aaaaaaa", now=NOW)
same = F.drift(F.latest(before=F._hour((NOW + timedelta(hours=1)).isoformat())),
               {"hour": "x", "hours": [h["at"] for h in bands_for(NOW + timedelta(hours=1))[0]["hours"]],
                "inputs": INPUTS, "build": "aaaaaaa",
                "bands": {b["band"]: [h["score"] for h in b["hours"]] for b in bands_for(NOW + timedelta(hours=1))}})
check("the same model an hour on has not moved", same["moved"], False)
shifted = bands_for(NOW + timedelta(hours=1), shape=20)
entry = {"hour": "x", "hours": [F._hour(h["at"]) for h in shifted[0]["hours"]], "inputs": INPUTS,
         "build": "aaaaaaa", "bands": {b["band"]: [h["score"] for h in b["hours"]] for b in shifted}}
v = F.drift(F.latest(before=F._hour((NOW + timedelta(hours=1)).isoformat())), entry)
check("twenty points at every hour with the sky still is drift", (v["moved"], v["inputs_moved"], v["build_changed"]), (True, False, False))
check("  and the note says the model moved", "the model did" in v["note"], True)
entry["build"] = "bbbbbbb"
v2 = F.drift(F.latest(before=F._hour((NOW + timedelta(hours=1)).isoformat())), entry)
check("  the same movement with a new build is explained by the build", (v2["moved"], v2["build_changed"]), (True, True))
entry["inputs"] = dict(INPUTS, sfi=140)
v3 = F.drift(F.latest(before=F._hour((NOW + timedelta(hours=1)).isoformat())), entry)
check("  and with the flux up thirty it moved with the sky", v3["inputs_moved"], True)

print("\nthe ledger is pruned")
check("nothing older than the keep window survives",
      all((NOW - datetime.strptime(p.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)).days <= F.KEEP_DAYS + 1
          for p in F.LEDGER.glob("????-??-??.json") if p.stem < F._day(NOW)), True)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
