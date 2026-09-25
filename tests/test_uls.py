#!/usr/bin/env python3
"""Checks for the FCC's own license files: read into the unit's index and
answering callsigns of every kind - amateur, GMRS, commercial - with the
class, the dates, the status, the FRN's other tickets, and nothing of the
name or the street.

    python3 tests/test_uls.py

The FCC is not asked: three small zips in the shape of its files are built
here, so the check runs on a bench with no network.
"""
import io
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import callsign, uls  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def hd(call, status, code, granted, expires, cancelled=""):
    return f"HD|1|||{call}|{status}|{code}|{granted}|{expires}|{cancelled}|||||||||N||||||||||N|||||||||||||||||||||||||||\r\n"


def en(call, frn, city, state, zip_code):
    f = [""] * 30
    f[0], f[4], f[7], f[8], f[10], f[15], f[16], f[17], f[18], f[22] = "EN", call, "Someone, A", "A", "Someone", "1 Street Rd", city, state, zip_code, frn
    return "|".join(f) + "\r\n"


def make_zip(tables):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in tables.items():
            z.writestr(name, text)
    path = uls.DIR / "test.zip"
    uls.DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())
    return path


def main():
    # Nothing asks the FCC during the check: the files are "just checked".
    for s in uls.SERVICES:
        uls._checked[s] = time.time()
    print("\n-- the service from the call's shape --")
    check("GMRS", (uls.service_of("WRMP909"), uls.service_of("WQAB123"), uls.service_of("KAB1234")), ("gmrs", "gmrs", "gmrs"))
    check("amateur", (uls.service_of("KC9SP"), uls.service_of("W1AW"), uls.service_of("AA0AAA")), ("amateur", "amateur", "amateur"))
    check("commercial", (uls.service_of("PG1136564"), uls.service_of("DBGB001241"), uls.service_of("MP0012345")), ("commercial", "commercial", "commercial"))
    check("neither", uls.service_of("EN36"), None)

    print("\n-- the GMRS file --")
    n = uls.build("gmrs", make_zip({
        "HD.dat": hd("WRMP909", "A", "ZA", "05/14/2021", "05/14/2031") + hd("WROL001", "E", "ZA", "01/01/2010", "01/01/2020")
        + hd("WRGO002", "C", "ZA", "01/01/2019", "01/01/2029", "06/01/2022"),
        "EN.dat": en("WRMP909", "0030807051", "PEQUOT LAKES", "MN", "56472") + en("WROL001", "0000000001", "Nowhere", "TX", "77777"),
        "HS.dat": "HS|1||WRMP909|05/14/2021|LIISS\r\n"}))
    check("three rows read", n, 3)
    r = uls.lookup("WRMP909")
    check("the license: found, active, the dates", (r["found"], r["fcc_status"], r["granted"], r["expires"]), (True, "active", "05/14/2021", "05/14/2031"))
    check("  current, with no grace period on GMRS", (r["status"]["state"], r["status"]["grace_ends"]), ("current", "2031-05-14"))
    check("  the FRN kept", r["frn"], "0030807051")
    check("  the town kept, for placing a far station", (r["place"], r["zip"]), ("Pequot Lakes, MN", "56472"))
    check("  and the name and street not", any(k for k in r if "name" in k or "street" in k), False)
    check("  the source names the FCC and the file's date", r["source"].startswith("FCC ULS, the GMRS file of "), True)
    check("an expired one is found and said to be expired, past any grace", (uls.lookup("WROL001")["found"], uls.lookup("WROL001")["status"]["state"]), (True, "expired"))
    g = uls.lookup("WRGO002")
    check("a cancelled one is not a license, and says why", (g["found"], g["reason"]), (False, "the FCC record is cancelled as of 06/01/2022"))
    check("one not in the file", uls.lookup("WRZZ000")["reason"], "no FCC GMRS record for this callsign")

    print("\n-- the amateur file, with the class --")
    uls.build("amateur", make_zip({
        "HD.dat": hd("KC9SP", "A", "HA", "05/14/2021", "05/14/2031") + hd("N0XYZ", "E", "HA", "01/01/2013", "01/01/2023"),
        "AM.dat": "AM|1|||KC9SP|G|||||||||||||\r\nAM|2|||N0XYZ|T|||||||||||||\r\n",
        "EN.dat": en("KC9SP", "0030807051", "PEQUOT LAKES", "MN", "56472")}))
    r = uls.lookup("KC9SP")
    check("class read from AM.dat", r["license_class"], "General")
    check("  the FRN's other ticket - the GMRS one - listed", [(o["callsign"], o["service"]) for o in r["others"]], [("WRMP909", "gmrs")])
    check("  and the whole FRN answers as one", sorted(x["callsign"] for x in uls.by_frn("0030807051")), ["KC9SP", "WRMP909"])
    check("an amateur more than two years past the date is expired for good", uls.lookup("N0XYZ")["status"]["state"], "expired")
    uls.build("amateur", make_zip({
        "HD.dat": hd("KC9SP", "A", "HA", "05/14/2021", "05/14/2031") + hd("N0XYZ", "E", "HA", "01/01/2015", "01/01/2025"),
        "AM.dat": "AM|1|||KC9SP|G|||||||||||||\r\nAM|2|||N0XYZ|T|||||||||||||\r\n",
        "EN.dat": en("KC9SP", "0030807051", "PEQUOT LAKES", "MN", "56472")}))
    check("  and one inside the two years is in grace", uls.lookup("N0XYZ")["status"]["state"], "grace")

    print("\n-- the commercial file, with the class and the radar endorsement --")
    uls.build("commercial", make_zip({
        "HD.dat": hd("PG1136564", "A", "CM", "12/16/1987", "") + hd("MP0000001", "A", "CM", "01/01/2020", "01/01/2025"),
        "FA.dat": "FA|1|||PG1136564|PG|Y|N||Y|||||\r\nFA|2|||MP0000001|MP|N|N||Y|||||\r\n",
        "EN.dat": en("PG1136564", "0030807051", "PEQUOT LAKES", "MN", "56472")}))
    r = uls.lookup("PG1136564")
    check("a GROL with the radar endorsement, for life", (r["license_class"], r["radar"], r["status"]["state"], r["status"].get("lifetime")),
          ("General Radiotelephone Operator License with Ship Radar endorsement", True, "current", True))
    check("an MROP past its date", (uls.lookup("MP0000001")["license_class"], uls.lookup("MP0000001")["status"]["state"]), ("Marine Radio Operator Permit", "expired"))
    check("the FRN now holds three", len(uls.by_frn("0030807051")), 3)

    print("\n-- through the one door --")
    check("callsign.lookup answers GMRS and commercial from the file", (callsign.lookup("WRMP909")["source"][:8], callsign.lookup("PG1136564")["found"]), ("FCC ULS,", True))
    check("  and amateur too, once the amateur file is here", callsign.lookup("KC9SP")["source"][:8], "FCC ULS,")
    check("what is on the unit", sorted(k for k, v in uls.state().items() if v["have"]), ["amateur", "commercial", "gmrs"])

    print("\n-- the three boxes on the Station panel --")
    from elmer.app import app
    c = app.test_client()
    # A page of somebody's asks who is at the controls before it opens,
    # so a test that fetches one says who it is first.
    c.post("/api/users/switch", json={"id": 1}, environ_base={"REMOTE_ADDR": "127.0.0.1"})
    r = c.post("/api/settings", json={"callsign": "KC9SP", "gmrs_call": "WRMP909", "commercial_call": "PG1136564"})
    d = r.get_json()
    check("an operator with all three, each filed under its own", (d["callsign"], d["settings"]["gmrs_call"], d["settings"]["commercial_call"]),
          ("KC9SP", "WRMP909", "PG1136564"))
    check("  the commercial record read, with the class", d["settings"]["commercial_license"]["license_class"][:37], "General Radiotelephone Operator Licen")
    check("  and the commercial pools switched on with it", d["settings"].get("commercial"), True)
    r = c.post("/api/settings", json={"callsign": "MP0000001"})
    check("a commercial call typed into the amateur box is filed as commercial, the amateur call untouched",
          (r.get_json()["callsign"], r.get_json()["settings"]["commercial_call"]), ("KC9SP", "MP0000001"))
    html = c.get("/bandplan").get_data(as_text=True)
    check("the band plan shows a strip for each", html.count('class="panel tight mt license-strip'), 3)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
