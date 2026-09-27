#!/usr/bin/env python3
"""Checks that the license indicator says where its answer came from.

Status - in force, renew, expired, cancelled, no FCC record - is one thing,
drawn in color, from one record. Evidence is another: the FCC record, the
operator's own paper, both, or nothing. This walks all five states through
the real pages - the account menu's list, the dashboard line and the band
plan - because each of them used to know only the FCC half:

  none     a callsign and nothing to go on: "not confirmed", with why
  paper    the paper alone, with the network cut - how a unit in a camp
           with no signal confirms a license on its first day
  fcc      the record alone
  both     the record and the paper agree
  differ   they disagree; the record wins and the paper is flagged

and that the paper is never called "verified", nobody is ever called
"unlicensed", and another account on the unit sees the marks but not what
somebody's paper says.

    python3 tests/test_license_evidence.py

Needs reportlab (to make a license-shaped PDF) and poppler (to read it), as
the Library does.
"""
import io
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import callsign, library, papers  # noqa: E402

FAILS = []
TODAY = date.today()


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def license_pdf(call, klass, granted, expires):
    """A page shaped like the FCC's official copy: the call, the dates, and
    the class under Operator Privileges."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 740, "FEDERAL COMMUNICATIONS COMMISSION")
    c.drawString(72, 720, f"Call Sign: {call}   Grant Date: {granted:%m-%d-%Y}   Expiration Date: {expires:%m-%d-%Y}")
    c.drawString(72, 700, "Operator Privileges")
    c.drawString(72, 686, klass)
    c.save()
    return buf.getvalue()


def record(klass="Extra", expires=None, found=True):
    expires = expires or TODAY + timedelta(days=5 * 365)
    if not found:
        return {"callsign": "KC9SP", "found": False, "reason": "no current FCC record for this callsign"}
    return {"callsign": "KC9SP", "found": True, "license_class": klass,
            "expires": f"{expires:%m/%d/%Y}", "granted": f"{expires - timedelta(days=3652):%m/%d/%Y}",
            "status": callsign.status_for(expires), "source": "test"}


# The network, cut at the socket: every fetch anywhere in the program fails
# the way it does in a camp with no signal, and is counted.
REACHED = []


def no_network(req, *a, **k):
    REACHED.append(getattr(req, "full_url", req))
    raise OSError("no network in this test")


def main():
    if not library.tool("pdftotext"):
        print("poppler is not here; nothing to check")
        return 0
    urllib.request.urlopen = no_network
    real_lookup = callsign.lookup
    from elmer.app import app
    cl = app.test_client()
    cl.post("/api/users/switch", json={"id": 1}, environ_base={"REMOTE_ADDR": "127.0.0.1"})

    def me():
        users = cl.get("/api/users").get_json()["users"]
        return next(u for u in users if u["id"] == 1)

    def pages():
        return (cl.get("/").get_data(as_text=True), cl.get("/bandplan").get_data(as_text=True))

    def add_paper(klass, expires, call="KC9SP"):
        pdf = license_pdf(call, klass, expires - timedelta(days=3652), expires)
        r = cl.post("/api/papers/add", data={"kind": "amateur", "file": (io.BytesIO(pdf), "l.pdf")},
                    content_type="multipart/form-data")
        assert r.status_code == 200, r.get_data(as_text=True)

    print("\n-- none: a callsign, no signal, no paper --")
    cl.post("/api/settings", json={"callsign": "KC9SP"})
    u = me()
    ev = u["evidence"]
    check("the lookup went for the network and was refused", len(REACHED) >= 1, True)
    check("status unchecked, state none, no marks", (u["standing"], ev["state"], ev["marks"]), ("unchecked", "none", []))
    check("  the word is 'not confirmed', with the reason", (ev["label"], ev["reason"]),
          ("not confirmed", f"the FCC could not be reached on {TODAY.isoformat()} - offline"))
    home, plan = pages()
    check("  the dashboard says so", "not confirmed" in home and "could not be reached" in home, True)
    check("  and nobody is called unlicensed", "unlicensed" in (home + plan).lower(), False)
    ev = papers.evidence("unchecked", "KC9SP", None, None)
    check("  never asked at all reads 'not looked up yet'", (ev["state"], ev["reason"]), ("none", "not looked up yet"))

    print("\n-- paper only, with the network still cut --")
    add_paper("Amateur Extra", TODAY + timedelta(days=400))
    before = len(REACHED)
    u = me()
    ev = u["evidence"]
    check("state paper, the paper mark alone", (ev["state"], ev["marks"]), ("paper", ["paper"]))
    check("  in force, worked out from the paper's expiry and today", (u["standing"], ev["status"]["days"]), ("current", 400))
    check("  the class read off the paper, in the record's own name", ev["paper"]["class"], "Extra")
    check("  'from your paper, dated X', never 'verified'",
          ev["source"].startswith(f"from your paper, dated {(TODAY + timedelta(days=400) - timedelta(days=3652)).isoformat()}")
          and "verified with" in ev["source"] and "not verified" in ev["source"], True)
    home, plan = pages()
    check("  the dashboard carries the paper mark and the words", ('class="ev ev-paper"' in home, "from your paper, dated" in home),
          (True, True))
    check("  the band plan shows the paper's strip", ("from your paper, dated" in plan, "Extra" in plan), (True, True))
    check("  and none of it touched the network", len(REACHED), before)
    # A paper past its date, inside the two years to renew.
    add_paper("Amateur Extra", TODAY - timedelta(days=30))
    u = me()
    check("  a paper thirty days past its date reads grace, on the paper's word",
          (u["standing"], u["evidence"]["state"], u["evidence"]["status"]["renew_within"]), ("grace", "paper", 700))
    check("  still without the network", len(REACHED), before)
    add_paper("Amateur Extra", TODAY + timedelta(days=400))

    print("\n-- fcc only --")
    cl.post("/api/papers/remove", json={"kind": "amateur"})
    callsign.lookup = lambda call, refresh=False: record()
    cl.post("/api/settings", json={"callsign": "KC9SP"})
    u = me()
    ev = u["evidence"]
    check("state fcc, the FCC mark alone", (u["standing"], ev["state"], ev["marks"]), ("current", "fcc", ["fcc"]))
    from elmer import db
    kept = db.get_user(db.connect(), 1)["settings"]
    check("  the offline note is gone with a real answer", "license_unreached" in kept, False)
    home, plan = pages()
    check("  the dashboard says it is the FCC's", ('class="ev ev-fcc"' in home, "from the FCC record for KC9SP" in home),
          (True, True))

    print("\n-- both, agreeing --")
    add_paper("Amateur Extra", TODAY + timedelta(days=5 * 365))
    u = me()
    ev = u["evidence"]
    check("state both, both marks", (ev["state"], ev["marks"], ev["differs"]), ("both", ["fcc", "paper"], []))
    home, plan = pages()
    check("  the dashboard and the band plan say they agree",
          ("your paper agrees" in home, "your paper agrees" in plan), (True, True))

    print("\n-- both, differing --")
    callsign.lookup = lambda call, refresh=False: record(klass="General", expires=TODAY + timedelta(days=6 * 365))
    cl.post("/api/settings", json={"callsign": "KC9SP"})
    u = me()
    ev = u["evidence"]
    check("state differ, on the class and the expiry", (ev["state"], ev["differs"]), ("differ", ["class", "expiry"]))
    check("  the status is the FCC's", u["standing"], "current")
    check("  the FCC's answer is the one shown", ev["fcc_says"].startswith("KC9SP · General · expires"), True)
    home, plan = pages()
    check("  the dashboard says they differ, in words, with the FCC's answer",
          ("Your paper and the FCC differ" in home, "General" in home, "may be out of date" in home), (True, True, True))
    check("  and the band plan", "Your paper and the FCC differ" in plan, True)
    check("  the look is its own shape, not a status color", 'class="small license-differ"' in home, True)
    callsign.lookup = lambda call, refresh=False: record(found=False)
    cl.post("/api/settings", json={"callsign": "KC9SP"})
    u = me()
    check("the FCC with no record, and a paper that shows one, differ too",
          (u["standing"], u["evidence"]["state"], u["evidence"]["differs"]), ("unfound", "differ", ["record"]))
    home, plan = pages()
    check("  and the band plan still shows it, with no FCC license to hang it on",
          "Your paper and the FCC differ" in plan, True)

    print("\n-- another account on the unit --")
    callsign.lookup = lambda call, refresh=False: record()
    cl.post("/api/settings", json={"callsign": "KC9SP"})
    cl.post("/api/users/add", json={"name": "Second", "shared": False})
    theirs = next(u for u in cl.get("/api/users").get_json()["users"] if u["id"] == 1)["evidence"]
    check("sees the marks and the word", (theirs["marks"], theirs["label"]), (["fcc", "paper"], "licensed"))
    check("  and not what the paper says", ("paper" in theirs, "dated" in (theirs["source"] or "")), (False, False))

    callsign.lookup = real_lookup
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILED: {', '.join(FAILS)}")
        return 1
    print("all ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
