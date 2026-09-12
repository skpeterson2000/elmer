"""The operator's own manuals, indexed so ELMER can point at the page.

A radio's manual is three hundred pages and the thing you need from it at a
campsite is one line on one of them - the menu number for the CW pitch, the
range the tuner will match. ELMER cannot ship anybody's manual and would not
want to; they are the makers' and the ARRL's. What it can do is read the
copies the operator already owns, once, and afterwards answer "where does it
say that?" with the file, the page and the two lines around it - from the
operator's own copy, on the operator's own machine, with or without a signal.

Everything here is deterministic. The text is what pdftotext read; the
chapters are the bookmarks the publisher put in the file; a search finds the
pages that contain the words. Nothing is summarised, inferred or generated,
because a program whose numbers are measured does not start guessing the
moment it opens a book. Where a manual has no bookmarks the page says so and
search still works; where a word is not in the text it is not found. That
is the whole contract, and it is one that cannot be wrong except where the
manual's own wording is.

The shelf is data/library/ - the operator's, never committed. Drop a PDF in
it and the next visit to the Library page indexes it; an index is rebuilt
when the file changes, and refreshed anyway after REINDEX_DAYS so a poppler
upgrade that reads better is picked up. Page numbers are the file's own -
the 47th page of the PDF, which is not always what the publisher printed in
the corner - and are labelled as such.
"""
import json
import logging
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

from . import paths

log = logging.getLogger("elmer")

SHELF = paths.STATE / "library"
INDEX_DIR = SHELF / ".index"
REINDEX_DAYS = 30
# What an index file looks like. An index made by an older reader is remade
# on the next visit, whatever the file did: version 2 is when the bookmarks
# of a permission-locked manual started being read at all.
INDEX_VERSION = 2
SNIPPET = 90          # characters either side of the first hit
MAX_PDF_MB = 200      # a scanned manual can be big; a disc image is not a manual

# ELMER's own topics, as the words a publisher uses for them in a heading.
# These are what the pointers match against a manual's bookmarks: an outline
# entry whose title contains any of a topic's words is that topic's chapter.
# Words, not inference - "Antenna Tuner" is an antenna chapter because it
# says antenna, and "Propagation" is not because it does not.
TOPICS = {
    "antennas": {"label": "Antennas",
                 "words": ["antenna", "dipole", "yagi", "vertical", "beam",
                           "feed line", "feedline", "transmission line",
                           "coax", "swr", "tuner", "balun", "radial"]},
    "propagation": {"label": "Propagation",
                    "words": ["propagation", "ionosphere", "ionospheric",
                              "skip", "sunspot", "solar", "muf", "nvis",
                              "grey line", "gray line"]},
    "cw": {"label": "CW and keying",
           "words": ["cw", "morse", "keyer", "paddle", "sidetone", "pitch",
                     "break-in", "qsk"]},
    "digital": {"label": "Digital modes",
                "words": ["digital", "ft8", "psk", "rtty", "packet", "aprs",
                          "winlink", "sound card", "soundcard", "cat control",
                          "usb audio"]},
    "repeaters": {"label": "Repeaters and FM",
                  "words": ["repeater", "offset", "ctcss", "dcs", "tone",
                            "squelch", "memory channel", "memories", "fm"]},
    "power": {"label": "Power and batteries",
              "words": ["power supply", "battery", "batteries", "charging",
                        "dc power", "current drain", "fuse"]},
    "safety": {"label": "Safety and RF exposure",
               "words": ["safety", "rf exposure", "exposure", "grounding",
                         "lightning", "bonding"]},
    "rules": {"label": "Rules and operating",
              "words": ["regulation", "fcc", "part 97", "band plan",
                        "operating procedure", "phonetic", "q signal",
                        "net operation", "emergency"]},
    "satellites": {"label": "Satellites",
                   "words": ["satellite", "oscar", "amsat", "doppler",
                             "iss", "eme", "moonbounce"]},
    "menus": {"label": "Menus and settings",
              "words": ["menu", "setting", "set mode", "configuration",
                        "reset", "firmware", "function list"]},
    "test": {"label": "Test equipment",
             "words": ["vna", "antenna analyzer", "analyzer", "swr meter",
                       "oscilloscope", "dummy load", "wattmeter",
                       "measurement"]},
}


# ------------------------------------------------------------------ the shelf

def tools_present():
    """The poppler tools this needs, and which are missing."""
    want = ("pdftotext", "pdftohtml", "pdfinfo")
    return {t: bool(shutil.which(t)) for t in want}


def shelf():
    """Every PDF on the shelf, by name. Hidden files and non-PDFs are not books."""
    if not SHELF.is_dir():
        return []
    out = []
    for p in sorted(SHELF.iterdir(), key=lambda q: q.name.lower()):
        if p.name.startswith(".") or not p.is_file():
            continue
        if p.suffix.lower() != ".pdf":
            continue
        out.append(p)
    return out


def book(name):
    """The PDF called `name` on the shelf, or None - never a path outside it."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    p = SHELF / name
    if p.suffix.lower() != ".pdf" or not p.is_file():
        return None
    return p


def _index_path(pdf):
    return INDEX_DIR / (pdf.name + ".json")


_cache = {}       # index path -> (index file mtime, parsed)


def _load_index(pdf):
    """The parsed index, cached against the index file's own mtime: a
    thousand-page manual is a few megabytes of JSON, and a search box is
    typed into more than once."""
    path = _index_path(pdf)
    try:
        stamp = path.stat().st_mtime
    except OSError:
        _cache.pop(str(path), None)
        return None
    had = _cache.get(str(path))
    if had and had[0] == stamp:
        return had[1]
    try:
        with open(path, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None
    _cache[str(path)] = (stamp, meta)
    return meta


def _stale(pdf, meta):
    """Why this index needs remaking, or None if it is good."""
    if meta is None:
        return "not indexed"
    if meta.get("version", 1) != INDEX_VERSION:
        return "made by an older reader"
    try:
        st = pdf.stat()
    except OSError:
        return "file gone"
    if meta.get("size") != st.st_size or int(meta.get("mtime", 0)) != int(st.st_mtime):
        return "file changed"
    if time.time() - float(meta.get("indexed_at", 0)) > REINDEX_DAYS * 86400:
        return f"older than {REINDEX_DAYS} days"
    return None


# ---------------------------------------------------------------- reading one

def _run(cmd, timeout):
    done = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if done.returncode != 0:
        err = done.stderr.decode("utf-8", "ignore").strip()[:200]
        raise RuntimeError(f"{cmd[0]} failed: {err or done.returncode}")
    return done.stdout


def _pages(pdf):
    """The text of every page, in order. pdftotext puts a form feed between."""
    raw = _run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], timeout=600)
    text = raw.decode("utf-8", "ignore")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()                      # the trailing feed after the last page
    return [re.sub(r"[ \t]+", " ", p).strip() for p in pages]


def _outline(pdf):
    """The publisher's bookmarks as ([{title, page, level}], problem).

    pdftohtml prints the outline whatever page range it was asked for, so a
    one-page range gets the chapters without the text of the whole book.

    -nodrm matters. Most radio manuals are saved with "copying not allowed"
    set - Yaesu's are - and pdftohtml honours that flag by refusing the whole
    document, bookmarks included, while pdftotext reads the same file
    without a murmur. ELMER then said the manual had no bookmarks, which was
    not true, and the operator could see the table of contents working in
    front of them. The flag is the publisher's request about copying their
    text; reading the chapter titles of a book you own, on your own
    machine, to find your own page, is not that.

    `problem` is "" when the tool ran, and says why when it did not, so the
    catalogue can tell "this file has no bookmarks" from "the bookmarks could
    not be read".
    """
    try:
        raw = _run(["pdftohtml", "-xml", "-stdout", "-i", "-nodrm",
                    "-f", "1", "-l", "1", str(pdf)], timeout=120)
    except subprocess.TimeoutExpired:
        return [], "pdftohtml took too long reading the bookmarks"
    except RuntimeError as exc:
        return [], str(exc)[:160]
    try:
        root = ET.fromstring(raw.decode("utf-8", "ignore"))
    except ET.ParseError:
        return [], "pdftohtml's answer could not be read"
    out = []

    def walk(node, level):
        for child in node:
            if child.tag == "item":
                title = " ".join((child.text or "").split())
                try:
                    page = int(child.get("page") or 0)
                except ValueError:
                    page = 0
                if title and page > 0:
                    out.append({"title": title[:120], "page": page, "level": level})
            elif child.tag == "outline":
                walk(child, level + 1)

    for top in root.iter("outline"):
        walk(top, 0)
        break                            # iter() would revisit the nested ones
    return out, ""


def _title(pdf):
    try:
        raw = _run(["pdfinfo", str(pdf)], timeout=60).decode("utf-8", "ignore")
    except (RuntimeError, subprocess.TimeoutExpired):
        return ""
    m = re.search(r"^Title:\s*(.+)$", raw, re.M)
    title = (m.group(1).strip() if m else "")
    # Word's default and the like are not titles.
    if title.lower() in ("untitled", "microsoft word", "document") or len(title) < 3:
        return ""
    return title[:120]


def index_one(pdf):
    """Read one manual and write its index. Returns the index."""
    st = pdf.stat()
    if st.st_size > MAX_PDF_MB * 1024 * 1024:
        raise RuntimeError(f"{pdf.name} is {st.st_size // (1024 * 1024)} MB - "
                           f"larger than a manual; not indexed")
    started = time.time()
    pages = _pages(pdf)
    outline, outline_problem = _outline(pdf)
    meta = {
        "version": INDEX_VERSION,
        "name": pdf.name,
        "title": _title(pdf) or pdf.stem.replace("_", " "),
        "size": st.st_size, "mtime": int(st.st_mtime),
        "indexed_at": time.time(), "pages": len(pages),
        "outline": outline,
        "outline_problem": outline_problem,
        "text": pages,
        "took_s": round(time.time() - started, 1),
    }
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _index_path(pdf).with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    tmp.replace(_index_path(pdf))
    log.info("library: indexed %s - %d pages, %d bookmarks, %.1fs",
             pdf.name, len(pages), len(meta["outline"]), meta["took_s"])
    return meta


def refresh(force=False, only=None):
    """Bring the index up to the shelf. Returns what was done, by name.

    Indexes what is new or changed, drops indexes for books that have gone,
    and leaves the rest alone. `only` restricts it to one book.
    """
    report = {"indexed": [], "kept": [], "failed": {}, "dropped": []}
    have = tools_present()
    if not have["pdftotext"]:
        report["failed"]["*"] = "pdftotext is not installed (poppler-utils)"
        return report
    books = shelf()
    if only:
        books = [b for b in books if b.name == only]
    for pdf in books:
        meta = None if force else _load_index(pdf)
        why = "asked to" if force else _stale(pdf, meta)
        if why is None:
            report["kept"].append(pdf.name)
            continue
        try:
            index_one(pdf)
            report["indexed"].append(pdf.name)
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
            report["failed"][pdf.name] = str(exc)[:200]
            log.warning("library: could not index %s: %s", pdf.name, exc)
    if not only and INDEX_DIR.is_dir():
        names = {b.name for b in shelf()}
        for idx in INDEX_DIR.glob("*.pdf.json"):
            if idx.name[:-5] not in names:
                try:
                    idx.unlink()
                    report["dropped"].append(idx.name[:-5])
                except OSError:
                    pass
    return report


# ---------------------------------------------------------------- the catalogue

def _indexes():
    out = []
    for pdf in shelf():
        meta = _load_index(pdf)
        out.append((pdf, meta))
    return out


def catalogue():
    """The shelf as the page shows it: each book, indexed or not, and why."""
    rows = []
    for pdf, meta in _indexes():
        why = _stale(pdf, meta)
        rows.append({
            "name": pdf.name,
            "title": (meta or {}).get("title") or pdf.stem.replace("_", " "),
            "size_mb": round(pdf.stat().st_size / (1024 * 1024), 1),
            "pages": (meta or {}).get("pages"),
            "bookmarks": len((meta or {}).get("outline") or []),
            "bookmarks_problem": (meta or {}).get("outline_problem") or "",
            "indexed_at": (meta or {}).get("indexed_at"),
            "indexed": meta is not None,
            "stale": why,
        })
    return rows


def outline(name):
    pdf = book(name)
    meta = _load_index(pdf) if pdf else None
    return (meta or {}).get("outline") or []


# ---------------------------------------------------------------------- search

def _terms(query):
    """Quoted phrases stay whole; everything else is a word. All lower-case."""
    q = (query or "").strip().lower()
    phrases = re.findall(r'"([^"]+)"', q)
    rest = re.sub(r'"[^"]*"', " ", q)
    words = [w for w in re.findall(r"[a-z0-9][a-z0-9.\-/:]*", rest) if len(w) > 1]
    return [p.strip() for p in phrases if p.strip()] + words


def _snippet(text, term):
    low = text.lower()
    at = low.find(term)
    if at < 0:
        return text[: 2 * SNIPPET].strip()
    a, b = max(0, at - SNIPPET), min(len(text), at + len(term) + SNIPPET)
    s = re.sub(r"\s+", " ", text[a:b]).strip()
    return ("…" if a > 0 else "") + s + ("…" if b < len(text) else "")


def search(query, limit=30):
    """The pages on the shelf that contain every term, best first.

    A page counts if every term is on it. Its score is how many times the
    terms appear, and a page where the first term appears in the first
    quarter of the text edges ahead of one where it is a footnote. Nothing
    is stemmed or synonymised: "tuner" does not find "tuning", by design -
    the operator can type the other word, and the program cannot be found
    to have invented a match.
    """
    terms = _terms(query)
    if not terms:
        return {"query": query or "", "terms": [], "hits": [], "books": 0}
    hits = []
    books = 0
    for pdf, meta in _indexes():
        if not meta:
            continue
        books += 1
        for n, text in enumerate(meta.get("text") or [], start=1):
            low = text.lower()
            counts = [low.count(t) for t in terms]
            if not all(counts):
                continue
            score = sum(counts)
            if low.find(terms[0]) < max(1, len(low) // 4):
                score += 0.5
            hits.append({"book": pdf.name, "title": meta.get("title") or pdf.stem,
                         "page": n, "score": score,
                         "snippet": _snippet(text, terms[0]),
                         "chapter": _chapter_of(meta.get("outline") or [], n)})
    hits.sort(key=lambda h: (-h["score"], h["book"], h["page"]))
    return {"query": query, "terms": terms, "hits": hits[:limit],
            "total": len(hits), "books": books}


def _chapter_of(outline, page):
    """The last bookmark at or before this page - the chapter it is in.

    The outline is in the book's own order, so the last one not past the
    page is the one the page is under, whatever its level.
    """
    best = None
    for item in outline:
        if item["page"] <= page:
            best = item
    return best["title"] if best else None


# -------------------------------------------------------------------- pointers

def pointers(topic=None, words=None):
    """Where ELMER's topics are in the operator's own books, by bookmark.

    For one topic (a key of TOPICS) or an explicit list of words: every
    bookmark on the shelf whose title contains one of the words, with the
    book and the page. A book with no bookmarks contributes nothing here and
    says so in the catalogue; search still reaches into it.
    """
    if words is None:
        words = (TOPICS.get(topic or "") or {}).get("words") or []
    words = [w.lower() for w in words if w]
    if not words:
        return []
    out = []
    for pdf, meta in _indexes():
        for item in (meta or {}).get("outline") or []:
            title = item["title"].lower()
            # A plural is the same word: "Multiband Antennas" is an antenna
            # chapter. Nothing further than that - no stems, no synonyms.
            hit = next((w for w in words
                        if re.search(r"\b" + re.escape(w) + r"(?:s|es)?\b", title)), None)
            if hit:
                out.append({"book": pdf.name, "book_title": meta.get("title") or pdf.stem,
                            "title": item["title"], "page": item["page"],
                            "level": item["level"], "matched": hit})
    out.sort(key=lambda p: (p["book"], p["page"]))
    return out


def topic_map():
    """Every topic with its pointers - the Library page's second half."""
    return [{"key": k, "label": v["label"], "pointers": pointers(k)}
            for k, v in TOPICS.items()]
