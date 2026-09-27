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
  - each carries Distribution Statement A or is public domain, and says
    where it was published;
  - the whole shelf stays under 40 MB, for the Windows zip and a Pi's clone.

And the shelf behaves as promised, shown against a throwaway shipped
directory so nothing is written under the program's content:

  - the Library shows both shelves as one, the shipped books marked;
  - a shipped book cannot be deleted, only hidden, and the hidden list
    lives in the unit's state, so it survives the file being replaced by an
    update; showing it again brings it back;
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
FIELDS = ("file", "title", "edition", "source", "statement", "sha256", "bytes")
# Distribution Statement A by name, or by its words: the Army prints the same
# release under the label "Distribution Restriction".
RELEASED = re.compile(r"distribution statement a\b|approved for public release; distribution is unlimited"
                      r"|public domain", re.I)


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
        check(f"{name}: released to the public, in the cover's words",
              bool(RELEASED.search(str(row.get("statement") or ""))), True)
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

        names = [p.name for p in library.shelf()]
        check("the operator's book and the shipped one are on one shelf",
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
        check("  and nothing is hidden yet", d["hidden"], [])
        r = c.get("/library/book/handbook.pdf", environ_base=LOCAL)
        check("a shipped book opens", (r.status_code, r.data[:5]), (200, b"%PDF-"))
        r.close()
        check("a name that climbs out of the shelf finds nothing",
              (library.book("../handbook.pdf"), library.book("..\\handbook.pdf")), (None, None))

        print("\n-- hidden, never deleted --")
        r = c.post("/api/library/remove", json={"name": "handbook.pdf"}, environ_base=LOCAL)
        check("removing a shipped book is refused", (r.status_code, (r.get_json() or {}).get("shipped")), (409, True))
        check("  and the file is still there", (scratch / "handbook.pdf").is_file(), True)
        r = c.post("/api/library/hide", json={"name": "handbook.pdf", "hidden": True}, environ_base=LOCAL)
        check("hiding it is allowed", r.status_code, 200)
        check("  it is off the shelf", "handbook.pdf" in [p.name for p in library.shelf()], False)
        check("  offered back by name", [h["name"] for h in library.hidden_books()], ["handbook.pdf"])
        check("  the file is untouched", sha256(scratch / "handbook.pdf"),
              hashlib.sha256(shipped_bytes).hexdigest())
        check("  and the hidden list is kept in the unit's state, not beside the book",
              ((library.SHELF / library.HIDDEN_NAME).is_file(), (scratch / library.HIDDEN_NAME).exists()),
              (True, False))

        # An update replaces the file and rewrites the manifest; the
        # operator's word stands.
        newer = tiny_pdf("Antenna Handbook, reissued")
        (scratch / "handbook.pdf").write_bytes(newer)
        man = json.loads((scratch / "manifest.json").read_text(encoding="utf-8"))
        man["books"][0].update(sha256=hashlib.sha256(newer).hexdigest(), bytes=len(newer), edition="2001")
        (scratch / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
        library._manifest_cache.clear()
        check("after an update brings the file back, it is still hidden",
              "handbook.pdf" in [p.name for p in library.shelf()], False)
        check("  and search does not reach into it",
              [h["book"] for h in library.search("antenna")["hits"] if h["book"] == "handbook.pdf"], [])

        r = c.post("/api/library/hide", json={"name": "handbook.pdf", "hidden": False}, environ_base=LOCAL)
        check("showing it again brings it back",
              (r.status_code, "handbook.pdf" in [p.name for p in library.shelf()]), (200, True))
        check("  and it is no longer offered as hidden", library.hidden_books(), [])
        r = c.post("/api/library/hide", json={"name": "my-radio.pdf", "hidden": True}, environ_base=LOCAL)
        check("the operator's own book is not hidden, it is removed", r.status_code, 404)

        print("\n-- the operator's books are theirs to add and remove --")
        r = c.post("/api/library/add", data={"file": (io.BytesIO(tiny_pdf("Imposter")), "handbook.pdf")},
                   content_type="multipart/form-data", environ_base=LOCAL)
        check("adding a book under a shipped book's name is refused", r.status_code, 409)
        check("  and the shipped copy is what the shelf still has",
              library.is_shipped(library.book("handbook.pdf")), True)
        r = c.post("/api/library/remove", json={"name": "my-radio.pdf"}, environ_base=LOCAL)
        check("the operator's own book still removes", (r.status_code, (library.SHELF / "my-radio.pdf").exists()),
              (200, False))
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
