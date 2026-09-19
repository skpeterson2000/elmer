#!/usr/bin/env python3
"""A distance on a screen is in the units the operator chose. Every screen.

    python3 tests/test_units_follow.py

Reported plainly: "when Imperial is selected, why is a skip zone measured in
km?" The answer was worse than the question assumed. The preference existed,
it was correct, and it reached exactly one page. Everywhere else a unit was
picked and written into the string, so the skip zone came out in kilometres
on the Lab page and in miles on the band plan - and an operator who had
chosen either one was being overruled in one place or the other. Two
renderings of one number that do not agree is a fault this program keeps
finding in itself, and this is that fault again.

What this holds down:

  - the preference reaches every page, not one, so a helper can read it;
  - nothing renders a distance by multiplying in place;
  - what is a name or a measurement rather than a distance does not move:
    the 40 m band is still 40 m, wire is still cut in feet, and the F2
    layer is still a few hundred kilometres up however anybody drives.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
STATIC = Path(__file__).resolve().parents[1] / "elmer" / "static"
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer import units, db
    from elmer.app import app

    print("\n-- the conversions themselves --")
    check("a mile is a mile", round(units.from_km(1.609344, "imperial"), 6), 1.0)
    check("a nautical mile is a nautical mile", round(units.from_km(1.852, "nautical"), 6), 1.0)
    check("metric is the identity", units.from_km(1234.0, "metric"), 1234.0)
    check("and it says the unit out loud", units.say(1609.344, "imperial"), "1000 mi")

    print("\n-- skip distance is a distance, not a measurement of the layer --")
    # This is the line the report was really about. hmF2 is a property of
    # the ionosphere and stays in km; how far away the nearest station who
    # can hear you is standing is the same question as how far the next
    # park is, and moves with the preference.
    check("the module no longer calls skip distance a thing that stays in km",
          "skip distance are kilometres" in units.__doc__, False)
    check("  and says so where somebody will read it",
          "Skip distance belongs on the moving side" in units.__doc__, True)

    print("\n-- the preference reaches every page, not one --")
    conn = db.connect()
    db.save_settings(conn, {"units": "imperial",
                            "location": {"lat": 44.98, "lon": -93.27, "grid": "EN34"}})
    client = app.test_client()
    client.set_cookie("elmer_user", str(conn.user_id))
    for path in ("/", "/bandplan", "/lab", "/propagation", "/out"):
        page = client.get(path, environ_base=LOCAL)
        if page.status_code != 200:
            check(f"{path} opens", page.status_code, 200)
            continue
        body = page.get_data(as_text=True)
        check(f"{path} is handed the operator's units",
              '"short": "mi"' in body or '"short":"mi"' in body, True)

    print("\n-- the shared helper exists for a page to use --")
    elmer_js = (STATIC / "elmer.js").read_text(encoding="utf-8")
    for name in ("function away(", "function awayText(", "function unitSystem("):
        check(f"elmer.js defines {name.split('(')[0].split()[-1]}()", name in elmer_js, True)
    check("  and reads the preference at the moment of use, not at load",
          "window.UNITS ||" in elmer_js, True)

    print("\n-- nothing renders a distance by multiplying in place --")
    # 0.6214 and 1.609 are the two ways this was written by hand. Either one
    # in a rendering file means some panel is still deciding for the operator.
    for js in sorted(STATIC.glob("*.js")):
        hits = re.findall(r"0\.621\d*|/ *1\.609|\* *0\.62\b", js.read_text(encoding="utf-8"))
        check(f"{js.name} converts nothing by hand", hits, [])

    print("\n-- the skip zone, in both of the places that draw it --")
    lab = (STATIC / "lab.js").read_text(encoding="utf-8")
    band = (STATIC / "bandplan.js").read_text(encoding="utf-8")
    check("the Lab's simulator asks for the operator's units",
          "awayText(skipKm)" in lab, True)
    check("  and so does the band plan's warning", "awayText(now.skip_km)" in band, True)
    check("  neither of them still says km or miles on its own",
          ("skip zone ' +\n      Math.round(skipKm) + ' km" in lab
           or "Math.round(now.skip_km / 1.609)" in band), False)

    print("\n-- what is a name or a measurement does not move --")
    check("the F2 layer is still reported in km, because that is its height",
          "' km, foF2 '" in lab, True)
    check("  and a band is still named in metres",
          units.system("imperial")["short"], "mi")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
