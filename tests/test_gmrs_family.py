#!/usr/bin/env python3
"""Checks for what a GMRS license earns on the unit: the family it covers
(47 CFR 95.1705(c)), the first-contact step it puts on the track, the
renewal link when the date is near, and what a distance to a machine
means for a handheld.

    python3 tests/test_gmrs_family.py
"""
import io
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import repeaters as R, uls  # noqa: E402

FAILS = []
QTH = {"location": {"lat": 46.60, "lon": -94.31, "short": "Pequot Lakes", "grid": "EN36"}}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    uls._checked["gmrs"] = time.time()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("HD.dat", "HD|1|||WRMP909|A|ZA|05/14/2021|05/14/2031||||||||||N||||||||||N||||||||||||||||||||||||||\r\n")
        z.writestr("EN.dat", "EN|1|||WRMP909|I|L1|Someone, A|A||Someone|||||1 Street Rd|PEQUOT LAKES|MN|56472||||0030807051||\r\n")
    uls.DIR.mkdir(parents=True, exist_ok=True)
    (uls.DIR / "g.zip").write_bytes(buf.getvalue())
    uls.build("gmrs", uls.DIR / "g.zip")
    R.save([R._row("WRXX123", 462.675, tone="141.3", location="Brainerd", lat=46.36, lon=-94.20),
            R._row("WRYY456", 462.550, tone="100.0", location="Nisswa", lat=46.52, lon=-94.29)], "the test")

    print("\n-- what a distance means for a handheld --")
    check("six miles", R.reach_words(10), "inside a handheld's radio horizon")
    check("twenty-five miles wants the antenna up", "twenty feet" in R.reach_words(40), True)
    check("fifty miles is beyond the horizon whatever the power", "50 W does not move the horizon" in R.reach_words(80), True)

    from elmer.app import app
    c = app.test_client()
    print("\n-- the licensee --")
    r = c.post("/api/settings", json={"gmrs_call": "WRMP909", "name": "Scott", **QTH})
    check("holds WRMP909", r.get_json()["settings"]["gmrs"]["found"], True)
    r = c.post("/api/users/rename", json={"id": 1, "name": "Scott"})
    r = c.post("/api/users/add", json={"name": "Grandkid", "shared": False})
    check("a grandchild joins the unit", r.status_code, 200)
    c.post("/api/settings", json=QTH)
    d = c.get("/api/ways-out?gear=gmrs").get_json()
    g = next(w for w in d["ways"] if w["key"] == "gmrs-repeater")
    check("  and, uncovered, is told the license is a fee and a form", "a fee and a form" in g["needs"], True)
    check("  their track has no GMRS step", [s["key"] for s in d["track"]], ["listen", "personal", "exam"])

    print("\n-- marked as family, on the licensee's own account --")
    c.post("/api/users/switch", json={"id": 1})
    r = c.post("/api/settings", json={"gmrs_covers": [2]})
    check("the licensee marks the grandchild", r.get_json()["settings"].get("gmrs_covers"), [2])
    html = c.get("/").get_data(as_text=True)
    check("  the Station panel offers the accounts on the unit to mark", "setup-gmrs-family" in html and "Grandkid" in html, True)

    c.post("/api/users/switch", json={"id": 2})
    d = c.get("/api/ways-out?gear=gmrs").get_json()
    g = next(w for w in d["ways"] if w["key"] == "gmrs-repeater")
    check("the grandchild's repeater card says whose license and which rule",
          "you operate under WRMP909, Scott's license, as family (95.1705(c))" in g["needs"], True)
    check("  and to say the call", "Say WRMP909." in g["do"], True)
    check("  with the reach of each machine in words", [r["reach"] for r in g["rows"]], ["inside a handheld's radio horizon"] * 2)
    check("  the track gains the GMRS step, before the exam", [s["key"] for s in d["track"]], ["listen", "personal", "gmrs", "exam"])
    step = next(s for s in d["track"] if s["key"] == "gmrs")
    check("  which names the machine and the call", step["title"], "Key the GMRS repeater at Nisswa - say WRMP909")
    check("  the band plan strip says so", "operate under it as family" in c.get("/bandplan").get_data(as_text=True), True)
    check("  and the Station panel", "as immediate family" in c.get("/").get_data(as_text=True), True)
    p = c.get("/api/personal").get_json()
    check("  the GMRS fold too", (p["gmrs_license"].get("covered_by"), p["gmrs_repeaters"][0]["reach"]), ("Scott", "inside a handheld's radio horizon"))
    r = c.post("/api/settings", json={"gmrs_covers": [1]})
    check("nobody without a license can claim to cover anyone", r.get_json()["settings"].get("gmrs_covers"), None)

    print("\n-- unmarked again --")
    c.post("/api/users/switch", json={"id": 1})
    c.post("/api/settings", json={"gmrs_covers": []})
    c.post("/api/users/switch", json={"id": 2})
    d = c.get("/api/ways-out?gear=gmrs").get_json()
    check("the grandchild is back to the fee and the form", "a fee and a form" in next(w for w in d["ways"] if w["key"] == "gmrs-repeater")["needs"], True)

    print("\n-- renewal, when the date is near --")
    with uls._connect() as conn:
        conn.execute("UPDATE license SET expires = ? WHERE call = 'WRMP909'", (time.strftime("%m/%d/%Y", time.localtime(time.time() + 40 * 86400)),))
    c.post("/api/users/switch", json={"id": 1})
    r = c.post("/api/settings", json={"gmrs_call": "WRMP909"})
    check("forty days out", r.get_json()["settings"]["gmrs"]["status"]["days"] in (39, 40), True)
    html = c.get("/").get_data(as_text=True)
    check("  the Station panel links the ULS renewal and says there is no grace period",
          "renew at ULS" in html and "no grace period after" in html, True)
    check("  and the band plan strip", "renew at ULS" in c.get("/bandplan").get_data(as_text=True), True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
