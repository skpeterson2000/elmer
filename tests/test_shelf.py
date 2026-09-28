#!/usr/bin/env python3
"""The manuals that ship with ELMER are the files the manifest vouches for.

    python3 tests/test_shelf.py

data/shelf/ holds public-release manuals that come with the program, beside
the operator's own library. What makes it safe to ship a book is written
down once, in data/shelf/manifest.json - the release statement from its
cover, where it was published, and the SHA-256 of the file as committed -
and this test holds the files to it:

  - every book the manifest lists is there, byte for byte;
  - every PDF in the directory is listed, so nothing unvetted rides along;
  - each carries Distribution Statement A or is public domain, in its
    cover's words, or is a work of the US Government and cites 17 U.S.C.
    105 where the cover says nothing; and says where it was published;
  - the whole shelf stays under 40 MB, for the Windows zip and a Pi's clone.

Those checks read the real data/shelf/ by its own path, and deliberately not
through ELMER_SHELF: _isolate points that at an empty directory so that
other tests do not count the shipped books, and a check of the manifest made
through it would pass over an empty shelf and prove nothing.

And the shelf behaves as promised, shown against a throwaway shipped
directory so nothing is written under the program's content:

  - the Library shows both sources as one, the shipped books marked, every
    book starting on the table;
  - a shipped book cannot be deleted, only returned to the shelf, and where
    each book is lives in the unit's state, so it survives the file being
    replaced by an update; bringing it to the table brings it back;
  - a book on the shelf is still indexed and searched, its pages offered
    beneath the table's, and the reader searches inside it; ELMER's topics
    point only into the table;
  - any book can go on the shelf, the operator's own as well;
  - a unit that hid books under the old list finds them on the shelf;
  - a book released to the public is free to take for everybody; a book
    somebody added is theirs to take and remove, and for reading here to
    anybody else - the file refused, the reader offering none, the pages
    drawn all the same; one copied in by hand is for reading here to all
    until somebody says it is their copy - once, first come;
  - an operator cannot add a book under a shipped book's name;
  - a PDF dropped in the shipped directory without a manifest entry is not
    shown.
"""
import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data" / "shelf"
MAX_MB = 40
FIELDS = ("file", "title", "edition", "source", "sha256", "bytes")
# Distribution Statement A by name, or by its words: the Army prints the same
# release under the label "Distribution Restriction".
RELEASED = re.compile(r"distribution statement a\b|approved for public release; distribution is unlimited"
                      r"|public domain", re.I)
# A work of the US Government, whose cover need not say so: the entry gives
# the statute instead, and names the office that made it.
US_WORK = re.compile(r"work of the united states government.*17 u\.s\.c\. (§ ?)?105", re.I | re.S)


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tiny_pdf(title):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.setTitle(title)
    c.drawString(72, 720, title + " - antenna chapter")
    c.save()
    return buf.getvalue()


def the_real_shelf():
    print("\n-- the shipped shelf matches its manifest --")
    try:
        data = json.loads((REAL / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        check("the manifest reads", str(exc), "")
        return
    books = data.get("books")
    check("the manifest has a list of books", isinstance(books, list), True)
    books = books if isinstance(books, list) else []
    print(f"     {len(books)} book(s) listed")
    listed = set()
    total = 0
    for row in books:
        name = row.get("file") if isinstance(row, dict) else None
        check(f"{name}: every field filled",
              [k for k in FIELDS if not (isinstance(row, dict) and row.get(k))], [])
        if not name:
            continue
        listed.add(name)
        # The cover's own words where it has them; a US Government work's
        # basis where it has none - one or the other, never neither.
        statement, basis = str(row.get("statement") or ""), str(row.get("basis") or "")
        check(f"{name}: free to copy, in the cover's words or by statute",
              bool(RELEASED.search(statement)) if statement else bool(US_WORK.search(basis)), True)
        check(f"{name}: the address it was published at", str(row.get("source") or "").startswith("https://"), True)
        path = REAL / name
        check(f"{name}: the file is there", path.is_file(), True)
        if not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        check(f"{name}: the size the manifest says", size, row.get("bytes"))
        check(f"{name}: the SHA-256 the manifest says", sha256(path), row.get("sha256"))
    unlisted = sorted(p.name for p in REAL.glob("*") if p.suffix.lower() == ".pdf" and p.name not in listed)
    check("no PDF in data/shelf is missing from the manifest", unlisted, [])
    print(f"     total {total / 1e6:.1f} MB")
    check(f"the whole shelf is under {MAX_MB} MB", total < MAX_MB * 1e6, True)


def the_behavior():
    print("\n-- one shelf, two sources --")
    from elmer import library
    from elmer.app import app

    scratch = Path(tempfile.mkdtemp(prefix="elmer-shelf-"))
    real_shipped = library.SHIPPED
    try:
        library.SHIPPED = scratch
        library._manifest_cache.clear()
        shipped_bytes = tiny_pdf("Antenna Handbook")
        (scratch / "handbook.pdf").write_bytes(shipped_bytes)
        (scratch / "stray.pdf").write_bytes(tiny_pdf("Nobody vetted this"))
        (scratch / "manifest.json").write_text(json.dumps({"books": [{
            "file": "handbook.pdf", "title": "Antenna Handbook", "edition": "1999",
            "source": "https://example.test/handbook.pdf",
            "statement": "DISTRIBUTION STATEMENT A: Approved for public release; distribution is unlimited.",
            "sha256": sha256(scratch / "handbook.pdf"), "bytes": len(shipped_bytes)}]}), encoding="utf-8")
        library.SHELF.mkdir(parents=True, exist_ok=True)
        (library.SHELF / "my-radio.pdf").write_bytes(tiny_pdf("My Radio"))

        names = [p.name for p in library.books()]
        check("the operator's book and the shipped one are in one Library",
              ("my-radio.pdf" in names, "handbook.pdf" in names), (True, True))
        check("  and the PDF the manifest does not list is not", "stray.pdf" in names, False)

        c = app.test_client()
        c.set_cookie("elmer_user", "1")
        d = c.get("/api/library", environ_base=LOCAL).get_json()
        rows = {r["name"]: r for r in d["shelf"]}
        check("the page is told which is shipped",
              (bool(rows["handbook.pdf"]["shipped"]), rows["my-radio.pdf"]["shipped"]), (True, None))
        check("  with the manifest's title, edition and statement",
              (rows["handbook.pdf"]["title"], rows["handbook.pdf"]["shipped"]["edition"],
               "DISTRIBUTION STATEMENT A" in rows["handbook.pdf"]["shipped"]["statement"]),
              ("Antenna Handbook", "1999", True))
        check("  and every book starts on the table",
              (rows["handbook.pdf"]["place"], rows["my-radio.pdf"]["place"]), ("table", "table"))
        r = c.get("/library/book/handbook.pdf", environ_base=LOCAL)
        check("a shipped book opens", (r.status_code, r.data[:5]), (200, b"%PDF-"))
        r.close()
        check("a name that climbs out of the Library finds nothing",
              (library.book("../handbook.pdf"), library.book("..\\handbook.pdf")), (None, None))

        print("\n-- on the shelf, never deleted --")
        r = c.post("/api/library/remove", json={"name": "handbook.pdf"}, environ_base=LOCAL)
        check("removing a shipped book is refused", (r.status_code, (r.get_json() or {}).get("shipped")), (409, True))
        check("  and the file is still there", (scratch / "handbook.pdf").is_file(), True)
        r = c.post("/api/library/shelve", json={"name": "handbook.pdf", "shelved": True}, environ_base=LOCAL)
        check("returning it to the shelf is allowed", (r.status_code, r.get_json()["place"]), (200, "shelf"))
        check("  it is off the table", "handbook.pdf" in [p.name for p in library.books("table")], False)
        check("  and on the shelf, still in the Library",
              ([p.name for p in library.books("shelf")], "handbook.pdf" in [p.name for p in library.books()]),
              (["handbook.pdf"], True))
        check("  the file is untouched", sha256(scratch / "handbook.pdf"),
              hashlib.sha256(shipped_bytes).hexdigest())
        check("  and the list is kept in the unit's state, not beside the book",
              ((library.SHELF / library.SHELVED_NAME).is_file(), (scratch / library.SHELVED_NAME).exists()),
              (True, False))

        # An update replaces the file and rewrites the manifest; the
        # operator's word stands.
        newer = tiny_pdf("Antenna Handbook, reissued")
        (scratch / "handbook.pdf").write_bytes(newer)
        man = json.loads((scratch / "manifest.json").read_text(encoding="utf-8"))
        man["books"][0].update(sha256=hashlib.sha256(newer).hexdigest(), bytes=len(newer), edition="2001")
        (scratch / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
        library._manifest_cache.clear()
        check("after an update brings the file back, it is still on the shelf",
              library.place("handbook.pdf"), "shelf")

        print("\n-- the shelf is searched after the table --")
        report = library.refresh()
        if report["failed"].get("*"):
            # The library tests need poppler (CLAUDE.md); say so rather than pass.
            check("pdftotext is here for the search checks", report["failed"]["*"][:40], "")
        else:
            check("a book on the shelf is still indexed", "handbook.pdf" in report["indexed"], True)
            found = library.search("antenna")
            check("  its pages are not among the table's",
                  [h["book"] for h in found["hits"] if h["book"] == "handbook.pdf"], [])
            check("  they come beneath, as the shelf's",
                  ([h["book"] for h in found["shelf"]["hits"]], found["shelf"]["books"]), (["handbook.pdf"], 1))
            check("  and the table's pages are not repeated there",
                  "my-radio.pdf" in [h["book"] for h in found["shelf"]["hits"]], False)
            d = c.get("/api/library/search?q=antenna", environ_base=LOCAL).get_json()
            check("the search answer carries both", (len(d["hits"]), len(d["shelf"]["hits"])), (1, 1))
            check("the reader searches inside a book on the shelf",
                  [h["page"] for h in library.search("antenna", book_name="handbook.pdf")["hits"]], [1])
            check("ELMER's topics point only into the table",
                  sorted({p["book"] for p in library.pointers(words=["radio", "handbook"])}), ["my-radio.pdf"])

        r = c.post("/api/library/shelve", json={"name": "handbook.pdf", "shelved": False}, environ_base=LOCAL)
        check("bringing it to the table brings it back",
              (r.status_code, "handbook.pdf" in [p.name for p in library.books("table")]), (200, True))
        check("  and the shelf is empty again", library.books("shelf"), [])

        print("\n-- any book can go on the shelf --")
        r = c.post("/api/library/shelve", json={"name": "my-radio.pdf", "shelved": True}, environ_base=LOCAL)
        check("the operator's own book goes on the shelf too", (r.status_code, library.place("my-radio.pdf")), (200, "shelf"))
        check("  and its file stays", (library.SHELF / "my-radio.pdf").is_file(), True)
        r = c.post("/api/library/shelve", json={"name": "nothing.pdf", "shelved": True}, environ_base=LOCAL)
        check("a book that is not there is refused", r.status_code, 404)
        c.post("/api/library/shelve", json={"name": "my-radio.pdf", "shelved": False}, environ_base=LOCAL)

        print("\n-- a unit that hid books before there was a table --")
        (library.SHELF / library.SHELVED_NAME).unlink()
        (library.SHELF / library.LEGACY_HIDDEN_NAME).write_text(json.dumps(["handbook.pdf"]), encoding="utf-8")
        check("a book hidden then is on the shelf now", library.place("handbook.pdf"), "shelf")
        check("  and the old list is carried over and gone",
              ((library.SHELF / library.SHELVED_NAME).is_file(), (library.SHELF / library.LEGACY_HIDDEN_NAME).exists()),
              (True, False))
        library.set_shelved("handbook.pdf", False)

        print("\n-- the operator's books are theirs to add and remove --")
        r = c.post("/api/library/add", data={"file": (io.BytesIO(tiny_pdf("Imposter")), "handbook.pdf")},
                   content_type="multipart/form-data", environ_base=LOCAL)
        check("adding a book under a shipped book's name is refused", r.status_code, 409)
        check("  and the shipped copy is what the shelf still has",
              library.is_shipped(library.book("handbook.pdf")), True)
        r = c.post("/api/library/remove", json={"name": "my-radio.pdf"}, environ_base=LOCAL)
        check("the operator's own book still removes", (r.status_code, (library.SHELF / "my-radio.pdf").exists()),
              (200, False))

        print("\n-- free to take, and for reading here --")
        from elmer import db
        other = db.add_user(db.connect(), "Somebody Else")
        other = other if isinstance(other, int) else other["id"]
        them = app.test_client()
        them.set_cookie("elmer_user", str(other))
        r = c.post("/api/library/add", data={"file": (io.BytesIO(tiny_pdf("Bought Handbook")), "bought.pdf")},
                   content_type="multipart/form-data", environ_base=LOCAL)
        check("a book added from the page", r.status_code, 200)
        check("  is on record as the adder's", library.added_by("bought.pdf"), 1)

        def row(client, name):
            d = client.get("/api/library", environ_base=LOCAL).get_json()
            return next((b for b in d["shelf"] if b["name"] == name), {})
        check("to the adder it is theirs to take, and to remove",
              (row(c, "bought.pdf").get("lending"), row(c, "bought.pdf").get("removable")), ("yours", True))
        check("to anybody else it is for reading here, and not theirs to remove",
              (row(them, "bought.pdf").get("lending"), row(them, "bought.pdf").get("removable")), ("reference", False))
        check("a book that came with ELMER is free to take, for everybody",
              (row(c, "handbook.pdf").get("lending"), row(them, "handbook.pdf").get("lending")), ("free", "free"))

        r = c.get("/library/book/bought.pdf", environ_base=LOCAL)
        check("the adder may take the file", r.status_code, 200)
        r.close()
        r = them.get("/library/book/bought.pdf", environ_base=LOCAL)
        check("  anybody else may not", r.status_code, 403)
        r.close()
        r = them.get("/library/book/handbook.pdf", environ_base=LOCAL)
        check("  but may take a book released to the public", r.status_code, 200)
        r.close()
        r = them.get("/library/read/bought.pdf", environ_base=LOCAL)
        page = r.get_data(as_text=True)
        check("anybody may read it in the reader, which offers no file",
              (r.status_code, 'id="asfile"' in page, "for reading here" in page), (200, False, True))
        r = c.get("/library/read/bought.pdf", environ_base=LOCAL)
        check("  the adder's reader offers the file", 'id="asfile"' in r.get_data(as_text=True), True)
        if library.can_draw_pages():
            r = them.get("/library/page/bought.pdf/1.png", environ_base=LOCAL)
            check("  and its pages are drawn for anybody", r.status_code, 200)
            r.close()

        r = them.post("/api/library/remove", json={"name": "bought.pdf"}, environ_base=LOCAL)
        check("anybody else cannot remove it", (r.status_code, (library.SHELF / "bought.pdf").is_file()), (403, True))
        (library.SHELF / "by-hand.pdf").write_bytes(tiny_pdf("Copied In By Hand"))
        check("a book copied in by hand is for reading here, for everybody",
              (row(c, "by-hand.pdf").get("lending"), row(them, "by-hand.pdf").get("lending")),
              ("reference", "reference"))
        check("  and it can be claimed; one added from the page, or that came with ELMER, cannot",
              (row(c, "by-hand.pdf").get("claimable"), row(c, "bought.pdf").get("claimable"),
               row(c, "handbook.pdf").get("claimable")), (True, False, False))
        r = them.post("/api/library/claim", json={"name": "by-hand.pdf"}, environ_base=LOCAL)
        check("whoever says it is their copy first owns it",
              (r.status_code, library.added_by("by-hand.pdf"), row(them, "by-hand.pdf").get("lending")),
              (200, other, "yours"))
        check("  and to everybody else it is still for reading here, not theirs to remove",
              (row(c, "by-hand.pdf").get("lending"), row(c, "by-hand.pdf").get("removable")), ("reference", False))
        r = c.post("/api/library/claim", json={"name": "by-hand.pdf"}, environ_base=LOCAL)
        check("  a second claim is refused, and the owner stays", (r.status_code, library.added_by("by-hand.pdf")),
              (409, other))
        r = c.post("/api/library/claim", json={"name": "handbook.pdf"}, environ_base=LOCAL)
        check("a book that came with ELMER is claimed by nobody", r.status_code, 409)
        r = c.post("/api/library/remove", json={"name": "bought.pdf"}, environ_base=LOCAL)
        check("the adder can remove it, and the record goes with it",
              (r.status_code, (library.SHELF / "bought.pdf").exists(), library.added_by("bought.pdf")), (200, False, None))
    finally:
        library.SHIPPED = real_shipped
        library._manifest_cache.clear()
        shutil.rmtree(scratch, ignore_errors=True)


def main():
    the_real_shelf()
    the_behavior()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
