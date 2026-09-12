"""The library: the operator's manuals, read once and answered from.

A small manual is made here with reportlab - three chapters, bookmarks, a
menu number on page two - dropped on an isolated shelf, indexed with the
poppler tools and searched. Nothing in this file touches the operator's
own data/library/. Skips, and says so, where poppler is not installed.

    python3 tests/test_library.py
"""
import io
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import library as L  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


have = L.tools_present()
if not all(have.values()):
    print(f"poppler tools missing ({have}) - the library cannot be tested here")
    sys.exit(0)

from reportlab.lib.pagesizes import LETTER  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402


def make_manual(path, chapters, bookmarks=True):
    c = canvas.Canvas(str(path), pagesize=LETTER)
    c.setTitle("FT-991A Operating Manual")
    for i, (title, lines) in enumerate(chapters):
        if bookmarks:
            c.bookmarkPage(f"ch{i}")
            c.addOutlineEntry(title, f"ch{i}", level=0)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 720, title)
        c.setFont("Helvetica", 11)
        for j, line in enumerate(lines):
            c.drawString(72, 690 - 16 * j, line)
        if bookmarks and i == 1:
            c.bookmarkPage("sub")
            c.addOutlineEntry("2.1 Pitch and sidetone", "sub", level=1)
        c.showPage()
    c.save()


CHAPTERS = [
    ("Chapter 1 Introduction", ["The rig has a front panel.", "Press MENU to enter the menu."]),
    ("Chapter 2 CW Operation", ["Set the CW pitch with menu 062 CW PITCH.",
                                "The keyer speed is menu 058 KEYER SPEED."]),
    ("Chapter 3 Antenna Tuner", ["The automatic antenna tuner matches 16.5 to 150 ohms.",
                                 "SWR above 3:1 stops the tuner."]),
]

print("\nthe shelf is the isolated state directory's, not the operator's")
check("the shelf is under ELMER_STATE", str(L.SHELF).startswith(os.environ["ELMER_STATE"]), True)
check("  and empty to begin with", L.shelf(), [])
check("  a name with a path in it is not a book", L.book("../elmer.db"), None)

L.SHELF.mkdir(parents=True, exist_ok=True)
make_manual(L.SHELF / "FT-991A Operating Manual.pdf", CHAPTERS)
make_manual(L.SHELF / "old-notes.pdf", [("Notes", ["A coax jumper and a balun."])], bookmarks=False)
(L.SHELF / "not-a-book.txt").write_text("hello")
(L.SHELF / ".hidden.pdf").write_bytes(b"%PDF-")

print("\nindexing reads what is new and leaves what it has read")
r = L.refresh()
check("both PDFs indexed, the text file and the hidden one ignored",
      sorted(r["indexed"]), ["FT-991A Operating Manual.pdf", "old-notes.pdf"])
check("  nothing failed", r["failed"], {})
r = L.refresh()
check("a second pass keeps both", (sorted(r["kept"]), r["indexed"]),
      (["FT-991A Operating Manual.pdf", "old-notes.pdf"], []))
cat = {b["name"]: b for b in L.catalogue()}
check("the catalogue knows the title from the file", cat["FT-991A Operating Manual.pdf"]["title"],
      "FT-991A Operating Manual")
check("  the page count and the bookmarks",
      (cat["FT-991A Operating Manual.pdf"]["pages"], cat["FT-991A Operating Manual.pdf"]["bookmarks"]), (3, 4))
check("  and that the notes have none", cat["old-notes.pdf"]["bookmarks"], 0)
check("  neither is stale", [b["stale"] for b in cat.values()], [None, None])

print("\nsearch finds the page, the chapter and the lines around it")
s = L.search("cw pitch")
check("one page has both words", (s["total"], s["books"]), (1, 2))
hit = s["hits"][0]
check("  page 2 of the manual", (hit["book"], hit["page"]), ("FT-991A Operating Manual.pdf", 2))
check("  in the chapter the bookmark names", hit["chapter"], "2.1 Pitch and sidetone")
check("  with the menu number in the snippet", "menu 062" in hit["snippet"], True)
check("a quoted phrase stays whole", L.search('"menu 058"')["total"], 1)
check("  and a phrase not on any page finds nothing", L.search('"menu 999"')["total"], 0)
check("every word must be there: 'tuner' does not find 'tuning'", L.search("tuning")["total"], 0)
check("  and each book answers for its own pages",
      (L.search("balun")["hits"][0]["book"], L.search("antenna")["hits"][0]["book"]),
      ("old-notes.pdf", "FT-991A Operating Manual.pdf"))
check("case does not matter", L.search("KEYER speed")["total"], 1)
check("an empty query is an empty answer", L.search("  ")["hits"], [])

print("\npointers come from the publisher's bookmarks, by the words in them")
p = L.pointers("antennas")
check("the tuner chapter is an antenna chapter because its title says so",
      [(x["title"], x["page"], x["matched"]) for x in p], [("Chapter 3 Antenna Tuner", 3, "antenna")])
check("  CW finds the chapter and the section under it",
      [x["title"] for x in L.pointers("cw")], ["Chapter 2 CW Operation", "2.1 Pitch and sidetone"])
check("  the book without bookmarks contributes none", any(x["book"] == "old-notes.pdf" for x in L.pointers("antennas")), False)
check("  an unknown topic is nothing, not an error", L.pointers("wizardry"), [])
tm = {t["key"]: t for t in L.topic_map()}
check("the topic map covers every topic", sorted(tm), sorted(L.TOPICS))
check("  and says which have pointers", [k for k, t in tm.items() if t["pointers"]], ["antennas", "cw"])

print("\na changed file is read again; a removed one is dropped")
time.sleep(1.1)
make_manual(L.SHELF / "FT-991A Operating Manual.pdf",
            CHAPTERS + [("Chapter 4 Digital Modes", ["FT8 needs the USB audio codec."])])
check("the catalogue sees the change", {b["name"]: b["stale"] for b in L.catalogue()}["FT-991A Operating Manual.pdf"], "file changed")
r = L.refresh()
check("  and re-reads it", r["indexed"], ["FT-991A Operating Manual.pdf"])
check("  four pages now", {b["name"]: b["pages"] for b in L.catalogue()}["FT-991A Operating Manual.pdf"], 4)
check("  the new chapter is a digital-modes pointer", [x["title"] for x in L.pointers("digital")], ["Chapter 4 Digital Modes"])
(L.SHELF / "old-notes.pdf").unlink()
r = L.refresh()
check("a book taken off the shelf loses its index", r["dropped"], ["old-notes.pdf"])
check("  and the search no longer sees it", L.search("balun")["books"], 1)

print("\nand through the program's own routes")
from elmer.app import app  # noqa: E402
app.config["TESTING"] = True
client = app.test_client()
check("the page renders", client.get("/library").status_code, 200)
d = client.get("/api/library").get_json()
check("the shelf is served", [b["name"] for b in d["shelf"]], ["FT-991A Operating Manual.pdf"])
d = client.get("/api/library/search?q=cw+pitch").get_json()
check("  search answers", d["hits"][0]["page"], 2)
d = client.get("/api/library/pointers?topic=antennas").get_json()
check("  pointers answer", d["pointers"][0]["page"], 3)
check("  an unknown topic is refused", client.get("/api/library/pointers?topic=x").status_code, 400)
d = client.get("/api/library/outline?name=FT-991A%20Operating%20Manual.pdf").get_json()
check("  the outline is served", len(d["outline"]), 5)
r = client.get("/library/book/FT-991A%20Operating%20Manual.pdf")
check("  the book itself opens", (r.status_code, r.data[:5]), (200, b"%PDF-"))

print("\na book opens inside ELMER, with the way back on it")
r = client.get("/library/read/FT-991A%20Operating%20Manual.pdf?page=2&q=cw+pitch&back=%2Flab")
page = r.data.decode()
check("the reader renders", r.status_code, 200)
check("  with Back going where the caller came from", 'href="/lab" id="back"' in page, True)
check("  the chapters down the side", ("Chapter 2 CW Operation" in page, "2.1 Pitch and sidetone" in page), (True, True))
check("  and the search's hits in this book", ("in this book" in page, "menu 062" in page), (True, True))
check("  opening at the page asked for", 'value="2"' in page, True)
r = client.get("/library/read/FT-991A%20Operating%20Manual.pdf?back=//elsewhere.example")
check("  a Back to somewhere else is refused - the Library instead",
      'href="/library" id="back"' in r.data.decode(), True)
check("  a book that is not there is a 404", client.get("/library/read/nothing.pdf").status_code, 404)
check("  every link on the Library page goes through the reader, in the same tab",
      ("target=\"_blank\"" in client.get("/library").data.decode(), "/library/read/" in client.get("/library").data.decode()),
      (False, True))
check("  and a path outside the shelf does not", client.get("/library/book/..%2Felmer.db").status_code, 404)

buf = io.BytesIO()
c = canvas.Canvas(buf, pagesize=LETTER)
c.bookmarkPage("a"); c.addOutlineEntry("Propagation Basics", "a", level=0)
c.drawString(72, 720, "Propagation Basics"); c.drawString(72, 700, "The MUF rises with the sun.")
c.showPage(); c.save()
r = client.post("/api/library/add", data={"file": (io.BytesIO(buf.getvalue()), "ARRL Handbook.pdf")},
                content_type="multipart/form-data")
check("a manual handed over from a browser lands on the shelf and is read",
      (r.status_code, r.get_json()["report"]["indexed"]), (200, ["ARRL_Handbook.pdf"]))
check("  and is searchable at once", client.get("/api/library/search?q=muf").get_json()["hits"][0]["book"], "ARRL_Handbook.pdf")
r = client.post("/api/library/add", data={"file": (io.BytesIO(b"hello"), "notes.pdf")},
                content_type="multipart/form-data")
check("  something that is not a PDF is refused", r.status_code, 400)
r = client.post("/api/library/remove", json={"name": "ARRL_Handbook.pdf"})
check("  and removed on request", (r.status_code, [b["name"] for b in r.get_json()["shelf"]]),
      (200, ["FT-991A Operating Manual.pdf"]))

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
