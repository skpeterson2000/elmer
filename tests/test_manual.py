#!/usr/bin/env python3
"""The User's Guide: built from docs/USER-GUIDE.md onto the Library shelf,
put back when it goes missing, and kept off when the operator says so.

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

    print("\n-- the source, and the book --")
    check("docs/USER-GUIDE.md is in the checkout", manual.SOURCE.is_file(), True)
    text = manual.SOURCE.read_text(encoding="utf-8")
    heads = [ln for ln in text.splitlines() if ln.startswith("## ")]
    check("  with chapters to make a table of contents from", len(heads) >= 8, True)
    check("  and the pre-release notice in its front matter", "pre-release" in text.lower(), True)
    pages = manual.build(manual.SOURCE, manual.path(), build_id="test")
    check("built onto the shelf, more than a few pages", (manual.path().is_file(), pages > 5), (True, True))
    head = manual.path().read_bytes()[:5]
    check("  a PDF", head, b"%PDF-")
    st = manual.status(conn)
    check("  present, current, not declined", (st["present"], st["stale"], st["declined"], st["build"]), (True, False, False, "test"))

    print("\n-- the Library reads it --")
    if library.tools_present().get("pdftotext"):
        report = library.refresh(only=manual.NAME)
        check("indexed like any book", manual.NAME in report["indexed"], True)
        row = next(r for r in library.catalogue() if r["name"] == manual.NAME)
        check("  its chapters come from the bookmarks the builder wrote", (row["bookmarks"] >= len(heads), row["bookmarks_from"]), (True, "bookmarks"))
        check("  and its title is the guide's", "User" in row["title"], True)
        found = library.search("decline", 30)
        check("  search finds the word about declining it, in this book", manual.NAME in str(found), True)
    else:
        print("  (no poppler here - the Library's reading of the book is not checked)")

    print("\n-- put back, and kept off --")
    check("in place, place() keeps it", manual.place(conn)["did"], "kept")
    manual.path().unlink()
    check("gone by accident, the doctor sees it", manual.status(conn)["present"], False)
    check("  and place() puts it back", (manual.place(conn)["did"], manual.path().is_file()), ("built", True))
    manual.path().write_bytes(b"%PDF-stale")
    (manual.shelf() / manual._MARK).write_text('{"source": "old"}', encoding="utf-8")
    check("the text changed since it was built: stale, and rebuilt", (manual.status(conn)["stale"], manual.place(conn)["did"], manual.status(conn)["stale"]), (True, "built", False))
    out = manual.decline(conn, True)
    check("declined: off the shelf now", (out["declined"], manual.path().is_file(), manual.declined(conn)), (True, False, True))
    check("  and not put back", (manual.place(conn)["did"], manual.path().is_file()), ("declined", False))
    out = manual.decline(conn, False)
    check("taken back: placed again", (out["declined"], out["did"], manual.path().is_file()), (False, "built", True))

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
    d = client.get("/api/library").get_json()
    check("the Library page is told where the guide stands", (d["manual"]["present"], d["manual"]["declined"]), (True, False))
    r = client.post("/api/library/manual", json={"declined": True})
    check("declining from the page takes it off", (r.status_code, r.get_json()["declined"], manual.path().is_file()), (200, True, False))
    r = client.post("/api/library/remove", json={"name": manual.NAME})
    check("  removing a book that is not there is a plain 404", r.status_code, 404)
    r = client.post("/api/library/manual", json={"declined": False})
    check("taking that back puts it on the shelf", (r.status_code, manual.path().is_file()), (200, True))
    r = client.post("/api/library/remove", json={"name": manual.NAME})
    check("removing the guide by hand says it will be back", (r.status_code, "comes back" in (r.get_json().get("note") or "")), (200, True))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
