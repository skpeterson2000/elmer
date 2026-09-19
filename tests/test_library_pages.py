#!/usr/bin/env python3
"""The reader draws the page itself: one page of a book, rendered by poppler
and kept.

    python3 tests/test_library_pages.py

The browser's own PDF viewer could not be trusted to open at the page the
Library pointed to - the Edge window ignored it, a phone showed nothing - so
the unit renders the page and the reader shows the picture. A page is drawn
once and kept; a page that is not there, a book that is not there, and a
unit without poppler are each a plain None, and the route says so. Needs
reportlab to make a book and poppler to draw it, both of which the checkout
has; without poppler the drawing checks are skipped and said so.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import library  # noqa: E402
from elmer.app import app  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def make_book(path, pages=3):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=letter)
    for n in range(1, pages + 1):
        c.setFont("Helvetica", 36)
        c.drawString(72, 700, f"Page {n} of the test manual")
        c.showPage()
    c.save()


def run():
    library.SHELF.mkdir(parents=True, exist_ok=True)
    make_book(library.SHELF / "test-manual.pdf")
    client = app.test_client()
    # A page of somebody's asks who is at the controls before it opens,
    # so a test that fetches one says who it is first.
    client.post("/api/users/switch", json={"id": 1}, environ_base={"REMOTE_ADDR": "127.0.0.1"})

    print("\n-- what is not there is None --")
    check("no such book", library.page_image("nobody.pdf", 1), None)
    check("page nought", library.page_image("test-manual.pdf", 0), None)

    if not library.can_draw_pages():
        print("  (no poppler on this machine - the drawing checks are skipped)")
        r = client.get("/library/page/test-manual.pdf/1.png")
        check("the route says so", r.status_code, 404)
    else:
        print("\n-- a page, drawn once and kept --")
        made = library.page_image("test-manual.pdf", 2)
        check("a PNG of page 2", bool(made) and made.suffix == ".png" and made.is_file(), True)
        check("  under the unit's own cache", library.PAGES in made.parents, True)
        first = made.stat().st_mtime_ns
        again = library.page_image("test-manual.pdf", 2)
        check("  the same file the second time, not drawn again", (again, again.stat().st_mtime_ns), (made, first))
        check("a page past the end", library.page_image("test-manual.pdf", 9), None)

        print("\n-- the route, and the reader --")
        r = client.get("/library/page/test-manual.pdf/1.png")
        check("the page comes as an image", (r.status_code, r.mimetype), (200, "image/png"))
        check("  and starts like one", r.data[:8], b"\x89PNG\r\n\x1a\n")
        r = client.get("/library/page/test-manual.pdf/9.png")
        check("a page that is not there", r.status_code, 404)
        r = client.get("/library/read/test-manual.pdf?page=2")
        html = r.get_data(as_text=True)
        check("the reader draws pages", ('id="pageimg"' in html, 'id="mode"' in html), (True, True))
        check("  and still offers the browser's viewer", 'Browser viewer' in html, True)

    print("\n-- without poppler, the reader falls back to the browser's viewer --")
    had = library.tool
    library.tool = lambda name: None
    try:
        check("nothing drawn", library.page_image("test-manual.pdf", 1), None)
        r = client.get("/library/read/test-manual.pdf?page=1")
        check("no page image in the reader", 'id="pageimg"' in r.get_data(as_text=True), False)
    finally:
        library.tool = had

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
