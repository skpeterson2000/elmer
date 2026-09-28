#!/usr/bin/env python3
"""The User's Guide: built from USER-GUIDE.md into the Library, put back
when it goes missing, and never removed - it can go on the shelf, and a
unit that once declined it finds it there.

    python3 tests/test_manual.py

Needs reportlab to build the book, which the checkout has; the Library's
own reading of its bookmarks needs poppler, and is checked when poppler is
here and said to be skipped when it is not.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, library, manual  # noqa: E402
from elmer.app import app  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def run():
    conn = db.connect()
    print("\n-- the markdown, read --")
    items = manual.parse("# The Title\n\nA line under it.\n\n## One\n\nWords **bold** and *slant* and `code`.\n\n- a bullet\n  that runs on\n- another\n\n> a note\n\n### One point one\n\nMore.\n")
    check("title, lead, chapter, paragraph, bullets, note, section", [k for k, _ in items],
          ["title", "p", "h1", "p", "li", "li", "note", "h2", "p"])
    check("  a bullet that runs on is one bullet", items[4][1], "a bullet that runs on")
    check("  inline marks become the PDF's own", manual._inline("a **b** *c* `d` & <e>"),
          'a <b>b</b> <i>c</i> <font face="Courier">d</font> &amp; &lt;e&gt;')
    # A cited source is linked and printed: the link is for the screen and
    # the address is for the printed page, where nothing can be clicked.
    linked = manual._inline("see [the record](https://example.org/r?a=1&b=2) for it")
    check("  a source is a real link", 'href="https://example.org/r?a=1&amp;b=2"' in linked, True)
    check("  with its address printed beside it",
          linked.count("https://example.org/r?a=1&amp;b=2"), 2)
    check("  and the address survives the rules that come after it",
          "https://e.org/a_b-c/d.html?q=1" in manual._inline("[x](https://e.org/a_b-c/d.html?q=1)"), True)

    print("\n-- the source, and the book --")
    check("USER-GUIDE.md is in the checkout, at the top where a person looks", (manual.SOURCE.is_file(), manual.SOURCE.parent == manual.paths.ROOT), (True, True))
    text = manual.SOURCE.read_text(encoding="utf-8")
    heads = [ln for ln in text.splitlines() if ln.startswith("## ")]
    check("  with chapters to make a table of contents from", len(heads) >= 8, True)
    check("  and the pre-release notice in its front matter", "pre-release" in text.lower(), True)
    # A figure that is not in the checkout does not break the book - it prints
    # "[picture missing: ...]" where the picture should be, which is worse,
    # because it ships. Every one the guide names has to be here.
    figures = [rel for kind, (rel, _cap) in
               ((k, v) for k, v in manual.parse(text) if k == "img")]
    check("  every figure it names is in the checkout",
          [rel for rel in figures if not (manual.paths.ROOT / rel).is_file()], [])
    check("  and there are figures to name", len(figures) >= 10, True)
    pages = manual.build(manual.SOURCE, manual.path(), build_id="test")
    check("built onto the shelf, more than a few pages", (manual.path().is_file(), pages > 5), (True, True))
    head = manual.path().read_bytes()[:5]
    check("  a PDF", head, b"%PDF-")
    # A heading is never the last thing on a page: it goes to the top of
    # the next, with its section, and the page before is left short.
    check("  no heading is left at the foot of a page", manual.last_stranded, [])
    check("  and the check can see one when there is one",
          manual.stranded([(3, "p", ""), (3, "h2", "Golf"), (4, "p", "")]), [(3, "Golf")])
    st = manual.status(conn)
    check("  present and current", (st["present"], st["stale"], st["build"]), (True, False, "test"))

    print("\n-- the Library reads it --")
    if library.tools_present().get("pdftotext"):
        report = library.refresh(only=manual.NAME)
        check("indexed like any book", manual.NAME in report["indexed"], True)
        row = next(r for r in library.catalogue() if r["name"] == manual.NAME)
        check("  its chapters come from the bookmarks the builder wrote", (row["bookmarks"] >= len(heads), row["bookmarks_from"]), (True, "bookmarks"))
        check("  and its title is the guide's", "User" in row["title"], True)
        found = library.search('"card catalogue"', 30)
        check("  search finds the card catalogue, in this book", manual.NAME in str(found), True)
    else:
        print("  (no poppler here - the Library's reading of the book is not checked)")

    print("\n-- put back, never kept off --")
    check("in place, place() keeps it", manual.place(conn)["did"], "kept")
    manual.path().unlink()
    check("gone by accident, the doctor sees it", manual.status(conn)["present"], False)
    check("  and place() puts it back", (manual.place(conn)["did"], manual.path().is_file()), ("built", True))
    manual.path().write_bytes(b"%PDF-stale")
    (manual.shelf() / manual._MARK).write_text('{"source": "old"}', encoding="utf-8")
    check("the text changed since it was built: stale, and rebuilt", (manual.status(conn)["stale"], manual.place(conn)["did"], manual.status(conn)["stale"]), (True, "built", False))
    check("there is no declining it any more", (hasattr(manual, "decline"), hasattr(manual, "remove")), (False, False))
    # A unit that declined it when that could be done: the guide is placed
    # again, on the shelf rather than the table, and the old word is cleared.
    db.unit_set(conn, manual.LEGACY_DECLINED_KEY, True)
    manual.path().unlink()
    check("once declined: back in the Library", (manual.place(conn)["did"], manual.path().is_file()), ("built", True))
    check("  on the shelf, not the table", library.place(manual.NAME), "shelf")
    check("  and the old word is cleared", bool(db.unit_get(conn, manual.LEGACY_DECLINED_KEY, False)), False)
    library.set_shelved(manual.NAME, False)

    print("\n-- the doctor, and the Library page --")
    from elmer import diagnostics
    app.config["TESTING"] = True
    client = app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}
    lines = client.get("/api/doctor", environ_base=local).get_json()
    rows = lines.get("lines") or lines.get("checks") or lines
    row = next((r for r in rows if isinstance(r, dict) and r.get("label") == "user's guide"), None)
    check("the self-check has a line for the guide", bool(row), True)
    check("  saying it is on the shelf", (row or {}).get("state"), "ok")
    manual.path().unlink()
    lines = client.get("/api/doctor", environ_base=local).get_json()
    rows = lines.get("lines") or lines.get("checks") or lines
    row = next((r for r in rows if isinstance(r, dict) and r.get("label") == "user's guide"), None)
    check("  gone, the line warns and offers the fix", ((row or {}).get("state"), (row or {}).get("fix")), ("warn", "manual"))
    r = client.post("/api/doctor/fix", json={"fix": "manual"}, environ_base=local)
    check("  and the fix puts it back", (r.status_code, r.get_json()["ok"], manual.path().is_file()), (200, True, True))
    client.set_cookie("elmer_user", "1")
    d = client.get("/api/library", environ_base=local).get_json()
    row = next((b for b in d["shelf"] if b["name"] == manual.NAME), {})
    check("the Library lists the guide, free to take and not removable",
          (row.get("guide"), row.get("lending"), row.get("removable")), (True, "free", False))
    r = client.post("/api/library/remove", json={"name": manual.NAME}, environ_base=local)
    check("removing the guide is refused, and the file stays",
          (r.status_code, (r.get_json() or {}).get("guide"), manual.path().is_file()), (409, True, True))
    r = client.post("/api/library/manual", json={"declined": True}, environ_base=local)
    check("  and there is no route to decline it", r.status_code in (404, 405), True)
    r = client.post("/api/library/shelve", json={"name": manual.NAME, "shelved": True}, environ_base=local)
    check("it can go on the shelf like any book", (r.status_code, library.place(manual.NAME)), (200, "shelf"))
    client.post("/api/library/shelve", json={"name": manual.NAME, "shelved": False}, environ_base=local)

    print("\n-- placed means readable, on the first visit --")
    # Building the guide only put a file on the shelf. Until it is indexed the
    # search cannot see into it and ELMER's topics have nothing of it to file,
    # so a fresh unit opened its Library on an empty index directly under a
    # paragraph promising the guide was there. The page heals itself on a
    # later visit, which is one visit too late for the only visit that
    # forms an impression.
    library.SHELF.mkdir(parents=True, exist_ok=True)
    for stale in library.SHELF.glob(manual.NAME + "*"):
        stale.unlink()
    import shutil as _sh
    _sh.rmtree(library.INDEX_DIR, ignore_errors=True)
    done = manual.place(db.connect(), force=True)
    check("the guide is built", done["did"], "built")
    check("  and indexed by the same act, not by the next page view",
          len(library.outline(manual.NAME)) > 20, True)
    filed = {t["label"]: len(t["pointers"]) for t in library.topic_map() if t["pointers"]}
    check("  so a fresh unit's topic index is not empty", len(filed) >= 6, True)
    # The guide covers these at length; if it files nothing under them the
    # index is the thing at fault, not the shelf.
    for label in ("Antennas", "Propagation", "CW and keying", "Games and the table"):
        check(f"  {label.lower()} has something in it", filed.get(label, 0) > 0, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
