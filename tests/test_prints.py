#!/usr/bin/env python3
"""Checks for the shelf of PDFs this unit has printed.

    python3 tests/test_prints.py

The point of the shelf is that a chart built on a Pi running full screen can be
read and printed without leaving the application to go looking for a downloads
folder. Two things have to hold for that: what is built is still there
afterwards, and the id in the URL cannot be talked into reading something else
off the disk.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import prints  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    # A shelf of its own, so a test never eats somebody's charts.
    real, prints.SHELF = prints.SHELF, prints.SHELF.parent / "prints-test"
    prints.INDEX = prints.SHELF / "index.json"
    shutil.rmtree(prints.SHELF, ignore_errors=True)
    try:
        print("\n-- what is built stays built --")
        row = prints.keep(b"%PDF-1.4 one", "band-plan-extra.pdf", "band-chart",
                          "Full band chart - Extra", {"class": "Extra"})
        check("it comes back with an id", bool(row["id"]), True)
        check("  and its bytes", prints.read(row["id"]), b"%PDF-1.4 one")
        check("  and is on the shelf", [r["id"] for r in prints.shelf()],
              [row["id"]])
        check("  knowing what it is", prints.one(row["id"])["title"],
              "Full band chart - Extra")

        print("\n-- newest first, because that is the one being reprinted --")
        second = prints.keep(b"%PDF-1.4 two", "rf.pdf", "rf-exposure", "RF record")
        check("the new one leads", prints.shelf()[0]["id"], second["id"])

        print("\n-- the id cannot be talked into reading the disk --")
        for bad in ("../../etc/passwd", "..%2f..%2fetc", "index", "",
                    "../elmer.db", "a" * 64):
            check(f"  {bad!r} reads nothing", prints.read(bad), None)
        check("and deleting one of those deletes nothing",
              prints.forget("../../etc/passwd"), False)
        check("  while the shelf is untouched", len(prints.shelf()), 2)

        print("\n-- a shelf, not an archive --")
        prints.KEEP, keep_was = 3, prints.KEEP
        for n in range(4):
            prints.keep(b"%PDF-1.4 filler", f"f{n}.pdf", "band-chart", f"Chart {n}")
        check("the oldest drop off by themselves", len(prints.shelf()), 3)
        check("  and their files go with them",
              len(list(prints.SHELF.glob("*.pdf"))), 3)
        prints.KEEP = keep_was

        print("\n-- and one thrown away is gone --")
        top = prints.shelf()[0]
        check("deleting says so", prints.forget(top["id"]), True)
        check("  it is off the shelf", top["id"] in
              [r["id"] for r in prints.shelf()], False)
        check("  and its bytes are unreadable", prints.read(top["id"]), None)
    finally:
        shutil.rmtree(prints.SHELF, ignore_errors=True)
        prints.SHELF, prints.INDEX = real, real / "index.json"

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
