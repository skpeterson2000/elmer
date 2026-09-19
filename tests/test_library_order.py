#!/usr/bin/env python3
"""The Library leads with what you made, then how to find things, then things.

    python3 tests/test_library_order.py

The page used to open with the operator's own licence papers and their
certificate wall, and put the search, the index and the books underneath
them. A library whose own function is below the fold is the wrong way round.

The order now runs: what this unit has printed for you, when there is any;
the search and the index beside each other, which are the two ways of
finding something; the books; awards, ELMER's own and anybody else's
together because they hang on the same wall; and the licence papers at the
foot, which are private and are not library.

And the thing that was missing rather than misplaced: an award arrives as a
PDF at least as often as a picture - that is what a contest organiser emails
- and the wall took PNG and JPEG only. It now renders a PDF's first page and
hangs that.
"""
import io as _io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import awards, library, manual  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def order_of(page):
    """The page's panels, in the order somebody scrolling meets them."""
    wanted = [
        ("printed", "What you have printed"),
        ("find", "Find the page"),
        ("index", "ELMER&rsquo;s topics" if "ELMER&rsquo;s topics" in page else "ELMER's topics"),
        ("shelf", "On the shelf"),
        ("awards", "Awards and certificates"),
        ("elsewhere", "From elsewhere"),
        ("licences", "Your licences"),
    ]
    seen = [(page.index(text), key) for key, text in wanted if text in page]
    return [key for _, key in sorted(seen)]


def main():
    from elmer.app import app
    client = app.test_client()

    print("\n-- with nothing printed yet --")
    page = client.get("/library", environ_base=LOCAL).data.decode("utf-8")
    check("the page opens on the search, not on somebody's papers",
          order_of(page),
          ["find", "index", "shelf", "awards", "elsewhere", "licences"])
    # An empty shelf at the top of a library is furniture.
    check("  and an empty print shelf is not shown at all",
          "What you have printed" in page, False)

    print("\n-- once this unit has made something --")
    r = client.post("/api/bandplan/pdf", json={"class": "Technician", "layout": "card"},
                    environ_base=LOCAL)
    check("a band card is built and kept", r.status_code, 200)
    page = client.get("/library", environ_base=LOCAL).data.decode("utf-8")
    check("what you made leads the page",
          order_of(page),
          ["printed", "find", "index", "shelf", "awards", "elsewhere", "licences"])
    check("  and it is reachable from there",
          bool(re.search(r'href="/prints/[0-9a-f]+"', page)), True)

    print("\n-- an award that arrived as a PDF --")
    # The certificate a contest organiser emails. Built here with the guide's
    # own renderer so the test carries no binary of its own.
    md = Path(_isolate.__file__).with_name("_award.md")
    md.write_text("# Worked All Continents\n\nAwarded for contacts on six continents.\n",
                  encoding="utf-8")
    pdf_path = md.with_suffix(".pdf")
    manual.build(md, pdf_path)
    data = pdf_path.read_bytes()
    ok, message = awards.add(1, _io.BytesIO(data), "eWAC.pdf", {"title": "eWAC"})
    check("it hangs", (ok, message.endswith(".jpg")), (True, True))
    check("  as a picture of its first page, on this operator's wall",
          [w.get("name") for w in awards.wall(1)], [message])
    md.unlink(missing_ok=True)
    pdf_path.unlink(missing_ok=True)

    print("\n-- and the page says so --")
    page = client.get("/library", environ_base=LOCAL).data.decode("utf-8")
    check("the upload offers all three kinds",
          all(k in page for k in ("application/pdf", "image/png", "image/jpeg")), True)
    # The renderer is poppler, which the shelf already needs in order to read
    # a book: a unit that can index a manual can hang a certificate.
    check("  and the renderer is the one the shelf already uses",
          library.tool("pdftoppm") is not None, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
