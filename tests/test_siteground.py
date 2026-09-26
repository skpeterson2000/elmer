#!/usr/bin/env python3
"""Rating the ground under an antenna, from the public surveys - offline.

    python3 tests/test_siteground.py

elmer/siteground.py reads the soil survey, the water survey and the lie of
the land for a spot and turns them into an ITU ground type with its reasons
and the practical side. Nothing here goes to the network: the three lookups
are stood in for with what the real services said for real places (rural
Indiana, downtown Indianapolis, the Outer Banks), so what is held is the
reading of them - and the keeping, which is the point of rating a spot while
there is a signal: the same answer must be there in a field without one.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import siteground as S, terrain, trip  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def soil(**kw):
    base = {"name": "Some loam", "drainage": "Well drained", "bedrock_cm": None, "water_table_cm": None,
            "flooding": "None", "ponding_pct": 0, "texture": "Loam", "clay_pct": 20.0, "sand_pct": 40.0,
            "salinity_ds_m": 0.0, "organic_pct": 2.0, "topsoil_cm": 25.0}
    base.update(kw)
    return base


# What the soil survey actually said, 2026-09-26.
CYCLONE = soil(name="Cyclone silty clay loam, 0 to 2 percent slopes", drainage="Poorly drained",
               water_table_cm=5.0, ponding_pct=83.0, texture="Silty clay loam", clay_pct=27.0, sand_pct=14.0)
URBAN = soil(name="Urban land-Fox loam complex, 0 to 2 percent slopes", drainage="", texture="")
DUNE = soil(name="Newhan fine sand", drainage="Moderately well drained", texture="Fine sand",
            clay_pct=2.0, sand_pct=98.0, flooding="Rare")

print("\n-- the rating, from the soil --")
r = S.rate(CYCLONE, {}, None, lat=40.5)
check("poorly drained silty clay loam with water a few inches down is wet ground", (r["ground"], r["pattern"]),
      ("wet", "good"))
check("  and says why, with the water table in inches", "about 2 in down" in r["why"][0], True)
check("  standing water is a practical note", any("Water stands" in p for p in r["practical"]), True)
check("  and north of the freeze line, winter is", any(p.startswith("Winter:") for p in r["practical"]), True)
check("  but not in the south", any(p.startswith("Winter:") for p in S.rate(CYCLONE, {}, None, lat=30.0)["practical"]),
      False)
check("urban land is city ground", (S.rate(URBAN, {}, None)["ground"], S.rate(URBAN, {}, None)["pattern"]), ("city", "poor"))
d = S.rate(DUNE, {}, None, lat=35.25)
check("98% sand is sand, whatever it says about drainage", d["ground"], "sand")
check("  and a rod in it holds poorly", any("holds poorly" in p for p in d["practical"]), True)
check("  radials matter most there", any("matter most" in p for p in d["practical"]), True)
rock = S.rate(soil(bedrock_cm=40.0), {}, None)
check("bedrock sixteen inches down is poor ground", rock["ground"], "poor")
check("  and no full rod goes in", any("will not go in" in p for p in rock["practical"]), True)
check("salty soil lifts ordinary ground to wet", S.rate(soil(salinity_ds_m=8.0), {}, None)["ground"], "wet")
check("open water mapped as a soil unit is fresh water", S.rate(soil(name="Water"), {}, None)["ground"], "fresh")
check("  and the sea when salt water is beside it",
      S.rate(soil(name="Water"), {"salt": {"what": "the sea", "name": "", "near": True}}, None)["ground"], "sea")
check("ordinary loam is average ground", S.rate(soil(), {}, None)["ground"], "average")
none = S.rate(None, {}, None)
check("no soil survey is unrated, not guessed", (none["ground"], "United States" in none["headline"]), (None, True))

print("\n-- the water nearby is said --")
sea = S.rate(DUNE, {"salt": {"what": "the sea", "name": "Atlantic Ocean", "near": False}}, None)
check("the sea within a mile, named", any("Atlantic Ocean" in w and "within a mile" in w for w in sea["why"]), True)
lake = S.rate(soil(), {"lake": {"what": "a lake or pond", "name": "", "near": True}}, None)
check("a lake is fresh water, and not the sea", any("not the sea" in w for w in lake["why"]), True)

print("\n-- kept for the field --")
calls = {"n": 0}


def answer(lat, lon):
    calls["n"] += 1
    return CYCLONE


S.soil_at = answer
S.water_near = lambda lat, lon: {"lake": {"what": "a lake or pond", "name": "", "near": False}}
S.lie_of_land = lambda lat, lon: {"elevation_m": 226.0, "drops_m": {}, "falls": [], "rises": [], "says": "flat all round"}
first = S.survey(40.5, -86.5, name="the back forty")
check("rated with a signal", (first["ok"], first["ground"], first["kept"]), (True, "wet", False))


def dark(*_a, **_k):
    raise OSError("no network")


S.soil_at = S.water_near = dark
S.lie_of_land = lambda lat, lon: None
again = S.survey(40.5, -86.5)
check("the same spot with no signal is answered from the unit", (again["ground"], again["kept"]), ("wet", True))
check("  with its name kept", again["name"], "the back forty")
refreshed = S.survey(40.5, -86.5, refresh=True)
check("a refresh with no signal keeps what there was, and says it failed",
      (refreshed["ground"], bool(refreshed.get("refresh_failed"))), ("wet", True))
never = S.survey(10.0, 10.0)
check("a spot never rated, with no signal, says so", (never["ok"], "no network" in never["error"]), (False, True))
check("the kept list has the spot", [s["name"] for s in S.kept_spots()], ["the back forty"])

print("\n-- the elevation service failing is a warning, not a crash --")
import urllib.request  # noqa: E402
real = urllib.request.urlopen
urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(OSError("unreachable"))
try:
    check("no elevations, no traceback", terrain.points([(40.0, -86.0), (40.1, -86.0)]), None)
finally:
    urllib.request.urlopen = real

print("\n-- the routes --")
from elmer import db  # noqa: E402
from elmer.app import app  # noqa: E402
c = app.test_client()
got = c.get("/api/ground?lat=40.5&lon=-86.5", environ_base=LOCAL).get_json()
check("a spot by coordinates", (got["ground"], got["kept"]), ("wet", True))
check("no QTH set is said, not guessed", c.get("/api/ground", environ_base=LOCAL).status_code, 404)
conn = db.connect()
settings = db.get_profile(conn)["settings"]
settings["location"] = {"lat": 40.5, "lon": -86.5, "grid": "EN60"}
db.save_settings(conn, settings)
conn.commit()
check("  and with one set, the QTH is the default", c.get("/api/ground", environ_base=LOCAL).get_json()["ground"], "wet")
check("nonsense coordinates are refused", c.get("/api/ground?lat=100&lon=0", environ_base=LOCAL).status_code, 400)
check("the kept spots are listed", len(c.get("/api/ground/kept", environ_base=LOCAL).get_json()["spots"]), 1)
lab = c.get("/lab", environ_base=LOCAL).get_data(as_text=True)
check("the Lab has a Ground tab", ('data-tab="ground"' in lab, 'id="pane-ground"' in lab), (True, True))

print("\n-- a trip packs the ground --")
trip.resolve = lambda where: {"name": "Moab, Utah", "short": "Moab", "lat": 38.57, "lon": -109.55, "grid": "DM58"}
from elmer import places, references  # noqa: E402
places.fetch = lambda *a, **k: [{"name": "Moab"}]
references.fetch = lambda *a, **k: {"parks": [], "summits": []}
S.survey = lambda lat, lon, name="", refresh=False: {"ok": True, "ground": "sand", "label": "Dry sand, desert"}
ok, message, record = trip.prepare("Moab, Utah")
check("the destination's ground is kept on the record", record["ground"], "sand")
check("  and listed with what was packed", "the ground: dry sand, desert" in record["have"], True)
S.survey = lambda lat, lon, name="", refresh=False: {"ok": False, "error": "nothing could be fetched - no network?"}
ok, message, record = trip.prepare("Moab, Utah")
check("  a ground that could not be rated is said to be missing",
      any(m.startswith("the ground could not be rated") for m in record["missing"]), True)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
