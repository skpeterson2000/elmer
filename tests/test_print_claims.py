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

    with elmer_app.app.test_request_context():
        held = elmer_app._own_class()
    print(f"\n-- this station holds {held!r} --")
    check("there is a class on file to compare against", bool(held), True)

    def ask(cls, layout="card"):
        client.post("/api/bandplan/pdf",
                    json={"class": cls, "layout": layout, "raw": True})
        return dict(seen)

    print("\n-- its own class may carry the callsign --")
    mine = ask(held)
    check("drawn for the class held", mine["license_class"], held)
    check("  and it is marked as the operator's own", mine["own"], True)
    check("  so the callsign goes on",
          bool((mine["station"] or {}).get("callsign")), True)

    print("\n-- and no other class may --")
    for other in ("Technician", "General", "Novice", "Advanced", "Extra"):
        if other.lower() == held.lower():
            continue
        got = ask(other)
        check(f"{other}: not the operator's own", got["own"], False)
        check(f"  {other}: no callsign on it", got["station"], None)

    print("\n-- the full chart is told the same thing --")
    full = ask("Novice" if held.lower() != "novice" else "Extra", "full")
    check("a class not held is marked on the full chart too",
          full["own"], False)
    check("  and the operator's own is not", ask(held, "full")["own"], True)

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
