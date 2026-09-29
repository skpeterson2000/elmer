#!/usr/bin/env python3
"""A book is called by its name, and shows its cover.

    python3 tests/test_library_covers.py

The index of topics named the ATP "Subject:" in front of every chapter and
the AUXFOG "[Add Logo Here]" - both the PDFs' own Title fields, which their
publishers left as template labels - while the card catalogue, which read
the manifest, had them right. And the table listed books as lines of text,
where a shelf shows covers. What is held here:

  - a Title field that is a label or a placeholder is not a title;
  - a book that came with ELMER is called what its manifest says,
    everywhere, whatever its file claims; any other book by its own title,
    else its file's name;
  - the index of topics names each book once, over its chapters;
  - a book's cover is its first page, drawn small, served at
    /library/cover/<name>.png;
  - the User's Guide has a cover of its own: the program's icon on its dark,
    and the contents on the page after.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import library, manual  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def names():
    print("\n-- a book is called by its name --")
    check("a label or a placeholder is not a title",
          [library.clean_title(t) for t in ("Subject:", "[Add Logo Here]", "<none>", "Untitled", "Taylor.indd")],
          ["", "", "", "", ""])
    check("  and a real one is kept as it is",
          [library.clean_title(t) for t in ("FT-991A Operating Manual", "ARRL Antenna Book (25th)")],
          ["FT-991A Operating Manual", "ARRL Antenna Book (25th)"])
    was = library.SHIPPED
    library.SHIPPED = ROOT / "data" / "shelf"
    library._manifest_cache.clear()
    try:
        atp = library.SHIPPED / "ATP-6-02.53-2025.pdf"
        check("a shipped book is called what its manifest says, whatever its file claims",
              library.book_title(atp, {"title": "Subject:"}),
              "ATP 6-02.53, Techniques for Tactical Radios and Retransmission")
        own = Path(library.SHELF) / "My_Radio_Manual.pdf"
        check("another book by its own title, else its file's name",
              (library.book_title(own, {"title": "IC-7300 Full Manual"}), library.book_title(own, {"title": "Subject:"})),
              ("IC-7300 Full Manual", "My Radio Manual"))
    finally:
        library.SHIPPED = was
        library._manifest_cache.clear()
    page = (ROOT / "elmer" / "templates" / "library.html").read_text(encoding="utf-8")
    check("the index of topics names each book once, over its chapters",
          ("lib-topic-book" in page, "${escapeHTML(p.book_title)} &mdash;" in page), (True, False))


def covers():
    print("\n-- a cover beside each book on the table --")
    if not library.can_draw_pages():
        check("poppler is on this machine to draw covers", False, True)
        return
    was = library.SHIPPED
    library.SHIPPED = ROOT / "data" / "shelf"
    library._manifest_cache.clear()
    try:
        made = library.cover_image("ATP-6-02.53-2025.pdf")
        check("a book's cover is its first page, drawn", bool(made and made.is_file()), True)
        from PIL import Image
        width = Image.open(made).size[0] if made else 0
        check("  small - a thumbnail, not a page", 150 <= width <= 300, True)
        check("  and nothing for a book that is not there", library.cover_image("no-such-book.pdf"), None)
    finally:
        library.SHIPPED = was
        library._manifest_cache.clear()
    from elmer.app import app
    rules = {r.rule for r in app.url_map.iter_rules()}
    check("the cover is served at /library/cover/<name>.png", "/library/cover/<path:name>.png" in rules, True)
    page = (ROOT / "elmer" / "templates" / "library.html").read_text(encoding="utf-8")
    check("  and the table shows it, and leaves out one that cannot be drawn",
          ('class="lib-cover"' in page, "contains('lib-cover')" in page), (True, True))


def the_guide():
    print("\n-- the User's Guide has a cover --")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "guide.pdf"
        manual.build(manual.SOURCE, out, build_id="test")
        tool = library.tool("pdftotext") or "pdftotext"
        text = subprocess.run([tool, "-enc", "UTF-8", "-f", "1", "-l", "2", str(out), "-"],
                              capture_output=True).stdout.decode("utf-8", "ignore").split("\f")
    first, second = re.sub(r"\s+", " ", text[0]), re.sub(r"\s+", " ", text[1] if len(text) > 1 else "")
    check("the first page is its cover: the title and the build, no contents",
          ("User's Guide" in first, "build test" in first, "Contents" in first), (True, True, False))
    check("  and the contents start on the page after", "Contents" in second, True)
    check("the cover is the program's own icon", (ROOT / manual.COVER_ART).is_file(), True)
    check("a new layout builds the guide again on every unit, the text unchanged",
          "LAYOUT" in (ROOT / "elmer" / "manual.py").read_text(encoding="utf-8")
          and manual.source_hash() != __import__("hashlib").sha1(manual.SOURCE.read_bytes()).hexdigest()[:12], True)


if __name__ == "__main__":
    names()
    covers()
    the_guide()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
