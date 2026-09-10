#!/usr/bin/env python3
"""A printed chart may only carry a callsign for the licence that station holds.

    python3 tests/test_print_claims.py

The band plan draws any class for anybody, which is worth having: it is how
somebody decides whether an upgrade is worth sitting for. The moment that
leaves the screen on paper it becomes a different object. A sheet headed
"US Amateur Bands - Extra - KC9SP" is read as a claim to hold Extra, by
anybody who reads it, whatever the page that made it meant.

Other operators would know, and the one waving it would be caught. That is not
the point: leaving the door open reflects on the community whose licence this
program exists to teach people to respect, so it is closed here.

The rule is that the callsign goes on only when the class being drawn is the
class actually held - from the FCC record where there is one - and that
anything else says on its face what it is. What is checked is the decision the
route makes, because the rule is not hard to get right and is easy to forget
to apply.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import app as elmer_app, bandpdf, prints  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    seen = {}

    def fake_card(license_class, station=None, own=True):
        seen.clear()
        seen.update(kind="card", license_class=license_class,
                    station=station, own=own)
        return b"%PDF-1.4 stub"

    def fake_full(bands, license_class, regional=None, station=None,
                  interop=False, own=True):
        seen.clear()
        seen.update(kind="full", license_class=license_class,
                    station=station, own=own)
        return b"%PDF-1.4 stub"

    def fake_keep(pdf, name, kind, title, meta=None):
        # Nothing goes on the operator's shelf for a test.
        return {"id": "test", "name": name, "kind": kind, "title": title,
                "bytes": len(pdf), "made_at": 0, "meta": meta or {}}

    bandpdf.build_card, bandpdf.build = fake_card, fake_full
    prints.keep = fake_keep
    client = elmer_app.app.test_client()

    # The licence is stated here rather than read off whoever's unit this is
    # running on. A test that asks the machine what class it holds passes on
    # the Pi it was written on and fails on a fresh install, where nobody has
    # entered a callsign yet - which is every clean checkout and every build.
    def holding(cls):
        elmer_app._own_class = lambda: cls

    def ask(cls, layout="card"):
        client.post("/api/bandplan/pdf",
                    json={"class": cls, "layout": layout, "raw": True})
        return dict(seen)

    held = "Extra"
    holding(held)
    print(f"\n-- a station holding {held} --")
    mine = ask(held)
    check("drawn for the class held", mine["license_class"], held)
    check("  and it is marked as the operator's own", mine["own"], True)
    # That the callsign is offered, not that there is one to offer. A unit
    # nobody has claimed has no callsign at all, and the decision under test
    # is the route's, not the operator's.
    check("  so the callsign is offered",
          "callsign" in (mine["station"] or {}), True)

    print("\n-- and no other class may carry it --")
    for other in ("Technician", "General", "Novice", "Advanced"):
        got = ask(other)
        check(f"{other}: not the operator's own", got["own"], False)
        check(f"  {other}: no callsign on it", got["station"], None)

    print("\n-- the full chart is told the same thing --")
    check("a class not held is marked on the full chart too",
          ask("Novice", "full")["own"], False)
    check("  and the operator's own is not", ask(held, "full")["own"], True)

    print("\n-- and a unit nobody has claimed yet claims nothing --")
    # A fresh install has no callsign and no class on file. It must not put a
    # callsign on anything, and every sheet it prints is a study sheet -
    # which is also the state every clean checkout builds in.
    holding("")
    for cls in ("Technician", "General", "Extra"):
        blank = ask(cls)
        check(f"{cls}: nothing is claimed", blank["own"], False)
        check(f"  {cls}: and no callsign", blank["station"], None)

    print("\n-- and a sheet that is not yours says so on its face --")
    check("there is wording for it", bool(bandpdf.NOT_HELD.strip()), True)
    said = bandpdf.NOT_HELD % "GENERAL"
    check("  which names the class it was drawn for",
          "GENERAL" in said, True)
    check("  and denies being a licence", "not a licence" in said, True)
    check("  and denies being about any station",
          "any station" in said, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
