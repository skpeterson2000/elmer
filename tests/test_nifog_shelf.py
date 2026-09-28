#!/usr/bin/env python3
"""The NIFOG comes with ELMER, in the Library, and the channels are read from it.

    python3 tests/test_nifog_shelf.py

CISA's National Interoperability Field Operations Guide is in data/shelf/,
listed in the manifest under the key "nifog". Proved here, against that real
copy (read, never written - the operator's state is a scratch directory):

  - the Library finds it by its key, and lends it freely to anybody: a work
    of the US Government, whose manifest entry gives the statute in place of
    a cover statement, and which nobody can claim;
  - a unit that has never fetched the guide reads the channels from that
    copy, with the same checks a fetch gets - the four calling channels,
    every frequency in its band - and says so, and keeps what it read;
  - a fetched copy is used instead when it is the same edition or newer, and
    set aside when the copy that came with ELMER is newer;
  - the Band Plan's answer names the book, so the page can open it in the
    Library.

Needs poppler, like the Library's other tests; it fails rather than skips
without it.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import library, nifog  # noqa: E402
from elmer.app import app  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
REAL = Path(__file__).resolve().parents[1] / "data" / "shelf"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    # The real shipped books, read only; _isolate pointed ELMER_SHELF at an
    # empty directory so other tests do not count them.
    library.SHIPPED = REAL
    library._manifest_cache.clear()

    print("\n-- in the Library --")
    name = library.shipped_name("nifog")
    check("the Library finds the NIFOG by its key", bool(name and name.startswith("NIFOG")), True)
    pdf = library.book(name) if name else None
    check("  it is a shipped book", library.is_shipped(pdf), True)
    c = app.test_client()
    c.set_cookie("elmer_user", "1")
    rows = {r["name"]: r for r in c.get("/api/library", environ_base=LOCAL).get_json()["shelf"]}
    row = rows.get(name) or {}
    check("  free to take, claimed by nobody, removed by nobody",
          (row.get("lending"), row.get("claimable"), row.get("removable")), ("free", False, False))
    check("  its card gives the statute, not a cover statement",
          ("17 U.S.C. 105" in ((row.get("shipped") or {}).get("basis") or ""),
           (row.get("shipped") or {}).get("statement")), (True, None))
    check("  and says what in it is somebody else's", "ShowMeCables" in ((row.get("shipped") or {}).get("note") or ""), True)

    if not library.tool("pdftotext"):
        check("pdftotext is here to read the channels", None, "a path")
        return

    print("\n-- its chapters, from its own printed contents --")
    # Its bookmarks are what was left of assembling the file - "NIFOG_508_
    # Master1_2_3...", table column headings - thousands of them. The list
    # beside it is the guide's printed table of contents, moved to the
    # file's pages, and it outranks the bookmarks.
    report = library.refresh(only=name)
    check("indexed", name in report["indexed"] + report["kept"], True)
    meta = library._load_index(pdf) or {}
    check("the chapters come from the list that came with it",
          (meta.get("outline_from"), len(library.outline(name))), ("the list that came with it", 136))
    pages = meta.get("text") or []

    def norm(s):
        return "".join(ch for ch in s.lower() if ch.isalnum())
    astray = [(i["page"], i["title"]) for i in library.outline(name)
              if norm(i["title"])[:28] not in norm(pages[i["page"] - 1] if i["page"] <= len(pages) else "")]
    check("  every title is on the page it names", astray, [])
    row = next((b for b in library.catalogue(1) if b["name"] == name), {})
    check("  and the Library counts them", row.get("bookmarks"), 136)
    print("\n-- the channels, from the copy that came with ELMER --")
    nifog.CACHE.unlink(missing_ok=True)
    nifog.SHELF_CACHE.unlink(missing_ok=True)
    record = nifog.load()
    check("a unit that never fetched reads them from the Library's copy",
          ((record or {}).get("source"), (record or {}).get("book")), ("shipped", name))
    channels = (record or {}).get("channels") or []
    check("  with the checks a fetch gets", nifog.problems(channels), [])
    check("  the four calling channels among them",
          all(c in [ch["name"] for ch in channels] for c in nifog.REQUIRED), True)
    check("  its edition read off the cover", (record or {}).get("version"), "2.02")
    check("  and it says where they came from", nifog.provenance(record), "read from the copy that came with ELMER")
    check("  what it read is kept", nifog.SHELF_CACHE.is_file(), True)

    print("\n-- fetched, or the copy that came with ELMER: the newer --")
    nifog.CACHE.parent.mkdir(parents=True, exist_ok=True)
    fetched = dict(record, source=None, version="2.01", fetched="2024-06-01", url="https://example.test/nifog.pdf")
    nifog.CACHE.write_text(json.dumps(fetched))
    check("an older fetch is set aside for the newer copy", nifog.load().get("source"), "shipped")
    nifog.CACHE.write_text(json.dumps(dict(fetched, version="2.02")))
    check("the same edition fetched is what is used", nifog.load().get("source"), "fetched")
    nifog.CACHE.write_text(json.dumps(dict(fetched, version="2.10")))
    got = nifog.load()
    check("  and a newer one", (got.get("source"), got.get("version")), ("fetched", "2.10"))
    check("  saying when it was fetched", nifog.provenance(got), "fetched from CISA on 2024-06-01")
    nifog.CACHE.unlink()

    print("\n-- the Band Plan --")
    d = c.get("/api/nifog", environ_base=LOCAL).get_json()
    check("the channels are there with no fetch", (d["have"], d["source"], d["count"] >= nifog.MIN_CHANNELS),
          (True, "shipped", True))
    check("  and the answer names the book, to open in the Library", d["book"], name)
    page = c.get("/bandplan", environ_base=LOCAL).get_data(as_text=True)
    check("the page has the way into the Library", 'id="nifog-read"' in page, True)


if __name__ == "__main__":
    try:
        main()
    finally:
        library._manifest_cache.clear()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
