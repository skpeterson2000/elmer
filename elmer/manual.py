"""The User's Guide: ELMER's own manual, on the operator's shelf.

The Library reads the operator's manuals and answers "where does it say
that?" with the page. This program's own guide belongs on that shelf too,
read by the same index, found by the same search, opened in the same reader
- rather than as a file somewhere a kiosk cannot reach. So the guide is
built from `USER-GUIDE.md` into a PDF with real bookmarks, one a
chapter, and placed at `data/library/` when ELMER starts if it is not
there or the text has changed. The Library indexes it on the next visit as
it would any book.

The guide cannot be removed from the Library, by the page or by a
setting. Nobody is better off without the manual to the program in front
of them, and a guide deleted on a kiosk is a guide nobody can find again.
It can go on the shelf like any book, out of the way and still in the
catalogue. A file deleted by hand from the folder comes back when ELMER
next starts, and the doctor's Fix puts it back sooner. (There used to be a
way to decline it for good. A unit that did finds the guide on the shelf
rather than the table - see place().)

The markdown is a small subset, chosen so the file reads plainly on GitHub
and renders here without a markdown library: `#` the title, `##` a
chapter, `###` a section, paragraphs, `-` bullets, `>` a note, `**bold**`,
`*italic*`, `` `code` ``, `[text](https://...)` for a source worth
following, and `![caption](docs/screenshots/x.png)` for a picture, scaled
to the page. A link is printed as well as linked, because most of what
this file becomes is paper. The PDF carries a table of contents with page
numbers, bookmarks for the Library's chapter list, and the build in the
footer so a problem report and a page can be matched.
"""
import hashlib
import json
import logging
import re
import time
from pathlib import Path

from . import db, paths

log = logging.getLogger("elmer")

# At the top of the checkout, beside the README, because that is where a
# person who has just unzipped ELMER looks for the manual - and the shelf is
# easy to lose a book on once it fills up. The screenshots stay in docs/.
SOURCE = paths.ROOT / "USER-GUIDE.md"
NAME = "ELMER-Users-Guide.pdf"
COVER_ART = "elmer/static/icon.png"     # the program's icon, the guide's cover
COVER_DARK = "#0b1017"                  # the program's own background
# Where a unit said it declined the guide, when that could be said. Read
# once, to put the guide on the shelf rather than the table, then cleared.
LEGACY_DECLINED_KEY = "manual_declined"
_MARK = ".manual.json"                  # beside the shelf's index: what was built, from what


def shelf():
    from . import library
    return library.SHELF


def path():
    return shelf() / NAME


def _mark_path():
    return shelf() / _MARK


# Bumped when the book's layout changes, so a unit whose guide was built
# from the same text by the old layout builds it again - the text alone
# decided that, and a new cover would have waited for the next edit.
LAYOUT = "2026-09-29 cover"


def source_hash(source=None):
    source = Path(source or SOURCE)
    try:
        return hashlib.sha1(source.read_bytes() + LAYOUT.encode()).hexdigest()[:12]
    except OSError:
        return None


def _carry_over_decline(conn):
    """A unit that declined the guide when that was possible gets it back on
    the shelf, not the table: in the Library, and out of the way of anybody
    who had said so."""
    if not db.unit_get(conn, LEGACY_DECLINED_KEY, False):
        return
    from . import library
    try:
        library.set_shelved(NAME, True)
    except OSError as exc:
        # Tried again at the next start; the guide is on the table meanwhile.
        log.warning("user's guide: was declined, and could not be put on the shelf: %s", exc)
        return
    db.unit_set(conn, LEGACY_DECLINED_KEY, False)
    log.info("user's guide: was declined on this unit - back in the Library, on the shelf")


def status(conn=None):
    """Where the guide stands: in the Library or not, current or not - for
    the doctor."""
    p = path()
    present = p.is_file()
    mark = {}
    try:
        mark = json.loads(_mark_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        mark = {}
    want = source_hash()
    return {"name": NAME, "path": str(p), "present": present,
            "source": SOURCE.is_file(),
            "stale": bool(present and want and mark.get("source") != want),
            "built": mark.get("built"), "build": mark.get("build")}


def place(conn=None, force=False):
    """Put the guide in the Library if it is not there or not current.
    Returns what was done: kept, built, or the reason it could not be."""
    conn = conn or db.connect()
    _carry_over_decline(conn)
    if not SOURCE.is_file():
        return {"did": "no source", "why": f"{SOURCE} is not in this checkout"}
    st = status(conn)
    if st["present"] and not st["stale"] and not force:
        return {"did": "kept"}
    try:
        build(SOURCE, path())
    except Exception as exc:                       # reportlab missing, disk full
        log.warning("user's guide: not built: %s: %s", type(exc).__name__, exc)
        return {"did": "failed", "why": f"{type(exc).__name__}: {exc}"}
    # Read it while we are here. Building it only put a file on the shelf;
    # until it is indexed the search cannot see into it and ELMER's topics
    # have nothing of it to file, so a fresh unit opened its Library on an
    # empty index and a shelf that said "nothing here yet" directly above a
    # paragraph promising the guide was on it. The Library page does heal
    # itself on a later visit, which is exactly one visit too late.
    try:
        from . import library          # imported here, as shelf() does
        library.refresh(only=NAME)
    except Exception as exc:                       # no poppler on this unit
        log.info("user's guide: on the shelf but not indexed yet: %s", exc)
    log.info("user's guide: %s in the Library", "rebuilt" if st["present"] else "placed")
    return {"did": "built"}


# ------------------------------------------------------------------ the book

_INLINE = [
    # A cited source, first so none of the rules below can get inside the
    # address. It is made a real link and the address is printed beside it:
    # most of what this file becomes is paper, and a reader holding a printed
    # page cannot click anything.
    (re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)"),
     r'<link href="\2"><u>\1</u></link> (<font face="Courier" size="8">\2</font>)'),
    (re.compile(r"\*\*(.+?)\*\*"), r"<b>\1</b>"),
    (re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])"), r"<i>\1</i>"),
    (re.compile(r"`([^`]+)`"), r'<font face="Courier">\1</font>'),
]


def _inline(text):
    text = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    for pat, rep in _INLINE:
        text = pat.sub(rep, text)
    return text


def parse(md):
    """The subset, as a list of (kind, text): title, h1, h2, p, li, note."""
    out = []
    para = []

    def flush():
        if para:
            out.append(("p", " ".join(para)))
            para.clear()

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        if line.startswith("### "):
            flush(); out.append(("h2", line[4:].strip()))
        elif line.startswith("## "):
            flush(); out.append(("h1", line[3:].strip()))
        elif line.startswith("# "):
            flush(); out.append(("title", line[2:].strip()))
        elif re.match(r"^\s*[-*]\s+", line):
            flush(); out.append(("li", re.sub(r"^\s*[-*]\s+", "", line)))
        elif line.startswith("> "):
            flush(); out.append(("note", line[2:].strip()))
        elif re.match(r"^!\[.*\]\(.+\)\s*$", line):
            flush()
            m = re.match(r"^!\[(.*)\]\((.+)\)\s*$", line)
            out.append(("img", (m.group(2).strip(), m.group(1).strip())))
        elif not para and out and out[-1][0] == "li" and raw.startswith("  "):
            out[-1] = ("li", out[-1][1] + " " + line.strip())      # a bullet that runs on
        else:
            para.append(line.strip())
    flush()
    return out


# What the last build left stranded: see stranded(). A test reads it.
last_stranded = []


def stranded(placed):
    """Headings that are the last thing on their page, as (page, text).

    `placed` is every flowable in the order it was laid out, as (page,
    kind, text). A heading belongs at the top of what it names; one at the
    foot of a page, with its section over the leaf, is a heading nobody
    can read with its text.
    """
    out = []
    for (page, kind, text), nxt in zip(placed, placed[1:] + [None]):
        if kind in ("h1", "h2") and nxt is not None and nxt[0] != page:
            out.append((page, text))
    return out


def build(source, target, build_id=None):
    """Render the markdown at `source` into the PDF at `target`, with a table
    of contents, bookmarks and page numbers. Returns the page count."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate,
                                    PageBreak, PageTemplate, Paragraph, Spacer)
    from reportlab.platypus.tableofcontents import TableOfContents

    source, target = Path(source), Path(target)
    md = source.read_text(encoding="utf-8")
    items = parse(md)
    title = next((t for k, t in items if k == "title"), "ELMER User's Guide")
    if build_id is None:
        try:
            from . import bugreport
            build_id = bugreport.build_stamp().get("build") or ""
        except Exception:
            build_id = ""

    base = getSampleStyleSheet()
    st = {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=26, leading=32, spaceAfter=18, alignment=TA_LEFT),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=11, leading=15, textColor=colors.HexColor("#555555")),
        # A heading is kept with what follows it: never the last thing on
        # a page, which is a heading read without its text. When what comes
        # next will not fit under it, the page is left short and the heading
        # starts the next one, at the top of the section it names.
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=17, leading=21, spaceBefore=18, spaceAfter=8,
                             textColor=colors.HexColor("#1a1a1a"), keepWithNext=1),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12.5, leading=16, spaceBefore=12, spaceAfter=4,
                             textColor=colors.HexColor("#1a1a1a"), keepWithNext=1),
        "p": ParagraphStyle("p", parent=base["Normal"], fontSize=10.2, leading=14, spaceAfter=6),
        "li": ParagraphStyle("li", parent=base["Normal"], fontSize=10.2, leading=14, leftIndent=16, bulletIndent=5,
                             spaceAfter=3, bulletFontName="Helvetica"),
        "note": ParagraphStyle("n", parent=base["Normal"], fontSize=9.6, leading=13, leftIndent=14, rightIndent=14,
                               textColor=colors.HexColor("#444444"), spaceAfter=8, borderPadding=4,
                               backColor=colors.HexColor("#f2f2f2")),
        "toc": ParagraphStyle("toch", parent=base["Heading1"], fontSize=15, leading=19, spaceAfter=8),
        "cap": ParagraphStyle("cap", parent=base["Normal"], fontSize=8.8, leading=12,
                              textColor=colors.HexColor("#555555"), spaceAfter=10),
    }

    def picture(rel, caption):
        """A screenshot, scaled to the frame and never taller than half a
        page, with its caption kept on the same page. A picture that is not
        in the checkout is said so in its place rather than breaking the
        book."""
        src = paths.ROOT / rel
        if not src.is_file():
            return [Paragraph(f"[picture missing: {_inline(rel)}]", st["cap"])]
        try:
            from reportlab.lib.utils import ImageReader
            iw, ih = ImageReader(str(src)).getSize()
        except Exception:
            return [Paragraph(f"[picture unreadable: {_inline(rel)}]", st["cap"])]
        max_w, max_h = LETTER[0] - 1.6 * inch, 3.9 * inch
        scale = min(max_w / iw, max_h / ih, 1.0)
        img = Image(str(src), width=iw * scale, height=ih * scale)
        img.hAlign = "LEFT"
        return [KeepTogether([img, Spacer(1, 3), Paragraph(_inline(caption), st["cap"])])]

    class Guide(BaseDocTemplate):
        """Headings become bookmarks and table-of-contents entries as they
        are laid out - the same key for both, so a chapter in the Library's
        list opens on the page the contents say."""

        def afterFlowable(self, flowable):
            # where everything landed, on the last pass: kept so a heading
            # left alone at the foot of a page can be found - see stranded
            if getattr(flowable, "_kind", None):
                self.placed.append((self.page, flowable._kind, getattr(flowable, "_plain", "")))
            level = getattr(flowable, "_level", None)
            if level is None:
                return
            text = flowable._plain
            # the key must be the same on every pass of the build, or the
            # contents never settle: the flowable's own identity is
            key = f"h{id(flowable)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=False)
            self.notify("TOCEntry", (level, text, self.page, key))

    def footer(canv, doc):
        canv.saveState()
        canv.setFont("Helvetica", 8)
        canv.setFillColor(colors.HexColor("#666666"))
        canv.drawString(0.8 * inch, 0.55 * inch, f"{title}" + (f"  ·  build {build_id}" if build_id else ""))
        canv.drawRightString(LETTER[0] - 0.8 * inch, 0.55 * inch, f"page {doc.page}")
        canv.restoreState()

    # The cover: the Library shows the first page of every book on the table
    # as its cover, and the guide's first page was its contents. So it has
    # one - the program's own icon on the program's own dark, the title under
    # it, and the build at the foot - drawn on the canvas, with the contents
    # starting on the page after.
    first_words = next((t for k, t in items if k == "p"), "")

    def cover(canv, doc):
        width, height = LETTER
        canv.saveState()
        canv.setFillColor(colors.HexColor(COVER_DARK))
        canv.rect(0, 0, width, height, stroke=0, fill=1)
        art = paths.ROOT / COVER_ART
        size = 4.6 * inch
        top = height - 1.1 * inch
        if art.is_file():
            try:
                canv.drawImage(str(art), (width - size) / 2, top - size, size, size, mask="auto")
            except (OSError, ValueError) as exc:
                log.warning("guide: the cover's picture %s could not be drawn: %s", art, exc)
        else:
            log.warning("guide: no cover picture at %s - the cover is the title alone", art)
        canv.setFillColor(colors.HexColor("#e6edf3"))
        canv.setFont("Helvetica-Bold", 30)
        canv.drawCentredString(width / 2, top - size - 0.75 * inch, "User's Guide")
        canv.setFillColor(colors.HexColor("#ffb454"))
        canv.rect(width / 2 - 0.9 * inch, top - size - 0.98 * inch, 1.8 * inch, 2.2, stroke=0, fill=1)
        if first_words:
            words = Paragraph(_inline(first_words), ParagraphStyle(
                "cv", parent=base["Normal"], fontSize=11.5, leading=16, alignment=1,
                textColor=colors.HexColor("#8b98a5")))
            w, h = words.wrap(width - 2.4 * inch, 2.5 * inch)
            words.drawOn(canv, 1.2 * inch, top - size - 1.3 * inch - h)
        canv.setFont("Helvetica", 8.5)
        canv.setFillColor(colors.HexColor("#626e7b"))
        canv.drawCentredString(width / 2, 0.7 * inch,
                               (f"build {build_id}  ·  " if build_id else "") + time.strftime("%d %B %Y"))
        canv.restoreState()

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".pdf.tmp")
    doc = Guide(str(tmp), pagesize=LETTER, leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                topMargin=0.8 * inch, bottomMargin=0.9 * inch, title=title, author="ELMER",
                subject="How to use ELMER", creator="ELMER")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([PageTemplate(id="cover", frames=[frame], onPage=cover),
                          PageTemplate(id="page", frames=[frame], onPage=footer)])

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("toc0", parent=base["Normal"], fontSize=10.5, leading=15, leftIndent=0),
        ParagraphStyle("toc1", parent=base["Normal"], fontSize=9.5, leading=13, leftIndent=16),
    ]
    # The cover page holds nothing but what cover() draws on it.
    flow = [NextPageTemplate("page"), Spacer(1, 1), PageBreak()]
    sub_lines = []
    body_started = False
    for kind, text in items:
        if kind == "title":
            flow.append(Paragraph(_inline(text), st["title"]))
            continue
        if not body_started and kind == "p":
            flow.append(Paragraph(_inline(text), st["sub"]))
            sub_lines.append(text)
            continue
        if not body_started:
            body_started = True
            if build_id:
                flow.append(Spacer(1, 8))
                flow.append(Paragraph(f"Built from build {build_id}, {time.strftime('%d %B %Y')}.", st["sub"]))
            flow.append(Spacer(1, 18))
            flow.append(Paragraph("Contents", st["toc"]))
            flow.append(toc)
            flow.append(PageBreak())
        if kind in ("h1", "h2"):
            para = Paragraph(_inline(text), st[kind])
            para._level = 0 if kind == "h1" else 1
            para._plain = text
            para._kind = kind
            flow.append(para)
        elif kind == "li":
            flow.append(Paragraph(_inline(text), st["li"], bulletText="•"))
        elif kind == "note":
            flow.append(Paragraph(_inline(text), st["note"]))
        elif kind == "img":
            flow.extend(picture(*text))
        else:
            flow.append(Paragraph(_inline(text), st["p"]))
        if kind not in ("h1", "h2") and flow and not getattr(flow[-1], "_kind", None):
            flow[-1]._kind = kind

    # multiBuild lays the book out more than once, until the contents'
    # page numbers settle; only the last pass is the book as printed.
    real_build = doc.build

    def one_pass(*a, **kw):
        doc.placed = []
        return real_build(*a, **kw)
    doc.build = one_pass
    doc.multiBuild(flow)
    global last_stranded
    last_stranded = stranded(doc.placed)
    for page, text in last_stranded:
        log.warning("guide: the heading %r is the last thing on page %d", text, page)
    tmp.replace(target)
    mark = {"source": source_hash(source), "built": time.time(), "build": build_id,
            "name": target.name}
    try:
        (target.parent / _MARK).write_text(json.dumps(mark), encoding="utf-8")
    except OSError as exc:
        # The guide is built and on the shelf; without its mark it is only
        # built again at the next start, which costs time and nothing else.
        log.warning("user's guide: built, but its mark could not be written: %s", exc)
    return doc.page
