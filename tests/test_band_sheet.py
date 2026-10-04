#!/usr/bin/env python3
"""One band, in one place: the sheet for the glovebox.

    python3 tests/test_band_sheet.py

The Band Plan prints a single band for a single place - the QTH in use when
it is printed, or a town or grid typed for a trip. What is proved here:

* The place is the QTH unless another is typed, and a typed place moves the
  coordinator and the repeaters with it: a sheet for Colorado printed in
  Minnesota is not Minnesota's.
* The repeaters are that band's, within the radius, nearest first - in the
  operator's units, opening at fifty miles.
* An empty repeater list says which empty it is. "None held anywhere",
  "the list covers somewhere else" and "none on this band near here" send
  somebody to do three different things.
* A coordinator is credited only on a band their plan covers. The MRC plans
  VHF and up; a 20 m sheet that named it would be claiming otherwise.
* HF below 10 m has no repeater section at all, rather than an empty one.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import json  # noqa: E402
import time  # noqa: E402
from elmer import bandsheet, prints, regional, repeaters  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
HOME = (46.60, -94.32)              # Pequot Lakes, Minnesota


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def north(km):
    """A point `km` due north of home."""
    return HOME[0] + km / 111.2, HOME[1]


def seed():
    rows = []
    for call, out, inp, km in (("W0AAA", 146.94, 146.34, 5), ("W0BBB", 147.15, 147.75, 30),
                               ("W0CCC", 145.45, 144.85, 70), ("W0DDD", 146.70, 146.10, 110),
                               ("W0EEE", 444.10, 449.10, 10)):
        lat, lon = north(km)
        rows.append(repeaters._row(call, out, input=inp, tone="123.0", location="Somewhere",
                                   modes="FM", lat=lat, lon=lon))
    repeaters.save(rows, "a test list")
    # The coordinator's plan, as the cache holds it: 2 m only.
    regional.CACHE.mkdir(parents=True, exist_ok=True)
    (regional.CACHE / "MRC.json").write_text(json.dumps({
        "short": "MRC", "name": "Minnesota Repeater Council", "states": ["MN"],
        "fetched": time.strftime("%Y-%m-%d"),
        "bands": {"2 m": [{"low": 146.52, "high": 146.52, "kind": "calling",
                            "label": "National simplex calling"},
                           {"low": 147.42, "high": 147.57, "kind": "simplex",
                            "label": "FM simplex"}]}}))


def main():
    seed()
    from elmer.app import app
    client = app.test_client()
    client.post("/api/users/switch", json={"id": 1}, environ_base=LOCAL)
    client.post("/api/settings", json={"location": {
        "lat": HOME[0], "lon": HOME[1], "short": "Pequot Lakes",
        "name": "Pequot Lakes, Crow Wing County, Minnesota, 56472, United States"}},
        environ_base=LOCAL)

    seen = {}
    real = bandsheet.build

    def spy(name, license_class, place, **kw):
        seen.clear()
        seen.update(kw, name=name, place=place)
        return real(name, license_class, place, **kw)
    bandsheet.build = spy

    def sheet(**body):
        body.setdefault("class", "General")
        r = client.post("/api/bandplan/band-pdf", json=body, environ_base=LOCAL)
        return r.status_code, (r.get_json() or {})

    print("\n-- 2 m at home --")
    code, d = sheet(band="2 m")
    check("the sheet is built", code, 200)
    calls = [r["call"] for r in seen.get("repeaters") or []]
    check("the 2 m machines within fifty miles, nearest first", calls, ["W0AAA", "W0BBB", "W0CCC"])
    check("  not the 70 cm one beside them", "W0EEE" in calls, False)
    check("the place is the QTH", (seen["place"]["label"], seen["place"]["away"]), ("Pequot Lakes", False))
    check("the coordinator is home's", (seen.get("regional") or {}).get("short"), "MRC")
    meta = prints.one(d["id"])["meta"]
    check("the shelf says what it was", (meta["band"], meta["state"], meta["repeaters"]), ("2 m", "MN", 3))

    code, d = sheet(band="2 m", radius=10)          # sixteen kilometers
    check("a smaller radius, a shorter list", [r["call"] for r in seen["repeaters"]], ["W0AAA"])

    print("\n-- a trip --")
    code, d = sheet(band="2 m", **{"from": "DM79"})
    check("a typed place is where the sheet is for", (code, seen["place"]["grid"][:4], seen["place"]["away"]),
          (200, "DM79", True))
    check("  and the coordinator is not home's", seen.get("regional"), None)
    check("  and the repeaters are not home's", seen["repeaters"], [])
    check("  and the sheet says the list covers somewhere else",
          "covers somewhere else" in seen["repeater_note"], True)
    # A name is looked up over the network; a test does not, so the lookup
    # is stood in for by one that finds nothing.
    from elmer import geocode
    real_resolve = geocode.resolve
    geocode.resolve = lambda text, allow_lookup=True: real_resolve(text, allow_lookup=False)
    code, d = sheet(band="2 m", **{"from": "nowhere-at-all-xq"})
    geocode.resolve = real_resolve
    check("a place that cannot be found is refused, and says so",
          (code, "could not find" in (d.get("error") or "")), (400, True))

    print("\n-- the other bands --")
    sheet(band="1.25 m")
    check("a band with nothing near says so, as that", seen["repeater_note"],
          "The list holds no 1.25 m repeater within that distance.")
    code, d = sheet(band="20 m")
    check("20 m has no repeater section, rather than an empty one", (code, seen["repeaters"]), (200, None))
    check("a band that is not one is refused", sheet(band="7 m")[0], 400)

    print("\n-- whose plan the sheet credits --")
    mrc = {"short": "MRC", "name": "Minnesota Repeater Council", "fetched": "2026-10-01",
           "bands": {"2 m": [{"low": 146.52, "high": 146.52, "kind": "calling", "label": "x"}]}}
    place = {"label": "Pequot Lakes", "grid": "EN26", "state": "MN"}
    check("credited on a band it covers",
          "Coordinated segments from the Minnesota Repeater Council" in bandsheet.header_note("2 m", place, mrc), True)
    check("and not on one it does not",
          "does not cover 20 m" in bandsheet.header_note("20 m", place, mrc), True)
    narcc = [{"short": "NARCC", "name": "Northern Amateur Relay Council of California",
              "url": "https://narcc.org/"}]
    note = bandsheet.header_note("70 cm", {"label": "Redding", "state": "CA"}, None, narcc)
    check("a coordinator ELMER cannot read is still named, with where to look",
          ("Northern Amateur Relay Council" in note, "https://narcc.org/" in note), (True, True))
    check("simplex lists the coordinator's beside the national",
          {w for *_, w in bandsheet.simplex("2 m", mrc)} >= {"national", "MRC"}, True)

    print("\n-- the page --")
    page = client.get("/bandplan", environ_base=LOCAL).data.decode("utf-8")
    check("the Band Plan has the button", 'id="bp-sheet"' in page, True)
    check("  opening at fifty miles", 'value="50"' in page and ">mi<" in page, True)

    bandsheet.build = real
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILED: {FAILS}")
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
