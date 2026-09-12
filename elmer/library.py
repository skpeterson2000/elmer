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
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

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
                           "coax", "swr", "tuner", "balun", "radial",
                           "whip", "hamstick"]},
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

# Where poppler ends up when it is not on the PATH this process was given.
# A program started from a desktop icon, a service, or a shortcut does not
# always inherit the PATH the operator's terminal has - and "the terminal
# finds it, ELMER does not" is a maddening thing to be told by a screen. So
# the PATH is tried first and these afterwards, and every call uses the
# full path that was found rather than asking the shell again.
FALLBACK_DIRS = ["/usr/bin", "/usr/local/bin", "/opt/homebrew/bin", "/opt/local/bin",
                 "/snap/bin", os.path.expanduser("~/.local/bin")]
if os.name == "nt":
    FALLBACK_DIRS += [str(p) for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                                          os.environ.get("LOCALAPPDATA", ""), "C:\\")
                      for p in (list(Path(base).glob("poppler*/Library/bin")) +
                                list(Path(base).glob("poppler*/bin")) +
                                list(Path(base).glob("Programs/poppler*/bin"))) if base]

_tools = {}


def tool(name):
    """The full path of a poppler tool, or None - looked up once."""
    if name in _tools:
        return _tools[name]
    found = shutil.which(name)
    if not found:
        exe = name + (".exe" if os.name == "nt" else "")
        for d in FALLBACK_DIRS:
            candidate = Path(d) / exe
            if candidate.is_file() and os.access(candidate, os.X_OK):
                found = str(candidate)
                break
    if found:
        _tools[name] = found       # a miss is not remembered: apt may run next
    else:
        log.warning("library: %s not found on PATH (%s) nor in %s", name,
                    os.environ.get("PATH") or "(empty)", ", ".join(FALLBACK_DIRS))
    return found


def tools_present():
    """The poppler tools this needs: full path where found, None where not."""
    return {t: tool(t) for t in ("pdftotext", "pdftohtml", "pdfinfo")}


def missing_tools_note():
    """What to tell the operator when the tools are not there - with what
    was looked at and on which machine, so 'but my terminal finds it' has
    somewhere to start. Two Pis on one bench is the ordinary case here, and
    a terminal on one answering for a screen on the other is the ordinary
    confusion."""
    import getpass
    import socket
    try:
        who = f"{getpass.getuser()}@{socket.gethostname()}"
    except Exception:                                    # pragma: no cover
        who = "this unit"
    return (f"pdftotext was not found by the ELMER running as {who}: not on its "
            f"PATH ({os.environ.get('PATH') or 'empty'}) and not in "
            f"{', '.join(FALLBACK_DIRS)}. On that machine, in a terminal, "
            f"'pdftotext -v' should print a version; if it does not, "
            f"'sudo apt install poppler-utils' (the Python package called "
            f"pdftotext is a library, not the tool). No restart is needed - "
            f"ELMER looks again on the next visit.")


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
    try:
        done = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except FileNotFoundError:
        raise RuntimeError(f"{cmd[0]} is not installed or not where ELMER can see it")
    if done.returncode != 0:
        err = done.stderr.decode("utf-8", "ignore").strip()[:200]
        raise RuntimeError(f"{cmd[0]} failed: {err or done.returncode}")
    return done.stdout


def _pages(pdf):
    """The text of every page, in order. pdftotext puts a form feed between."""
    raw = _run([tool("pdftotext") or "pdftotext", "-enc", "UTF-8", str(pdf), "-"], timeout=600)
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
        raw = _run([tool("pdftohtml") or "pdftohtml", "-xml", "-stdout", "-i", "-nodrm",
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
        raw = _run([tool("pdfinfo") or "pdfinfo", str(pdf)], timeout=60).decode("utf-8", "ignore")
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
        report["failed"]["*"] = missing_tools_note()
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
    from . import rigs
    rows = []
    for pdf, meta in _indexes():
        why = _stale(pdf, meta)
        rig = rigs.identify((meta or {}).get("title"), pdf.name)
        rows.append({
            # What radio the manual is for, if the table knows the model -
            # so the shelf can say what the operator owns.
            "rig": ({"make": rig["make"], "model": rig["model"], "kind": rig["kind"],
                     "word": rig["word"]} if rig else None),
            "name": pdf.name,
            "title": (meta or {}).get("title") or pdf.stem.replace("_", " "),
            "size_mb": round(pdf.stat().st_size / (1024 * 1024), 1),
            "pages": (meta or {}).get("pages"),
            # Pictures of pages, not pages: a scan has nothing for search to
            # read, and the shelf should say so rather than let "no results"
            # look like the word was not in the book.
            "scanned": bool(meta and meta.get("pages")
                            and not any((t or "").strip() for t in meta.get("text") or [])),
            "bookmarks": len((meta or {}).get("outline") or []),
            "bookmarks_problem": (meta or {}).get("outline_problem") or "",
            "indexed_at": (meta or {}).get("indexed_at"),
            "indexed": meta is not None,
            "stale": why,
        })
    return rows


MINE_KEY = "library.mine"


def mine(conn):
    """The books this user has marked as theirs. One shelf, shared - a
    manual is useful to everyone at the table - but whose radio it is for
    is a fact about a person, and it is kept per person."""
    from . import db
    return [n for n in (db.kv_get(conn, MINE_KEY, []) or []) if isinstance(n, str)]


def set_mine(conn, name, flag):
    from . import db
    have = mine(conn)
    if flag and name not in have:
        have.append(name)
    if not flag:
        have = [n for n in have if n != name]
    db.kv_set(conn, MINE_KEY, have)
    return have


def shelf_gear(conn):
    """What Make Contact should assume the operator has, from the shelf.

    The books this person marked as theirs, if any; otherwise every book on
    the shelf, which is the right reading of a one-person unit. Returns the
    radios recognised, the gear keys they tick, the basis, and the manuals
    the table could not place - said, not guessed at.

    A person who has marked only a book that is not a radio - the FT8 guide,
    the Antenna Book - has told ELMER what they read, not that they own no
    radio. Their marks are kept, but the radios come from the whole shelf
    and the answer says so (basis "shelf", `marked` naming what they own),
    rather than the poll of the shelf quietly vanishing the first time a
    book is marked.
    """
    from . import rigs
    own = set(mine(conn))
    rows = catalogue()

    def read(books):
        found, unknown = [], []
        for b in books:
            rig = rigs.identify(b.get("title"), b["name"])
            if rig:
                found.append(dict(rig, book=b["name"]))
            else:
                unknown.append(b.get("title") or b["name"])
        radios = [r for r in found if r["kind"] not in ("test", "book")]
        return found, radios, unknown

    marked = [b for b in rows if b["name"] in own]
    found, radios, unknown = read(marked) if own else ([], [], [])
    basis, picked = "mine", marked
    if not radios:
        basis, picked = "shelf", rows
        found, radios, unknown = read(rows)
    return {"basis": basis if rows else "none", "rigs": found,
            "gear": rigs.gear_from(radios), "sentence": rigs.sentence(radios),
            "unknown": unknown, "books": len(picked),
            "marked": sorted(b.get("title") or b["name"] for b in marked)}


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
    book and the page. A book with no bookmarks is read by its own title
    instead - a one-page fact sheet never has an outline, and "Hamstick
    Dipole Fact Sheet" says what it is as plainly as any chapter heading -
    so it points at page 1 when the title carries one of the words. Nothing
    is inferred beyond that; search still reaches into every page.
    """
    if words is None:
        words = (TOPICS.get(topic or "") or {}).get("words") or []
    words = [w.lower() for w in words if w]
    if not words:
        return []

    def matched(title):
        # A plural is the same word: "Multiband Antennas" is an antenna
        # chapter. Nothing further than that - no stems, no synonyms.
        title = title.lower()
        return next((w for w in words
                     if re.search(r"\b" + re.escape(w) + r"(?:s|es)?\b", title)), None)

    out = []
    for pdf, meta in _indexes():
        outline = (meta or {}).get("outline") or []
        book_title = (meta or {}).get("title") or pdf.stem.replace("_", " ")
        if not outline and meta is not None:
            # The file's own name counts as well as the title inside it: a
            # scanned instruction sheet saved as "Lakeview_Hamsticks_HF_
            # antenna_user.pdf" says "antenna" in the one place its maker's
            # metadata ("Hamstiks instructions") does not.
            hit = matched(book_title) or matched(pdf.stem.replace("_", " ").replace("-", " "))
            if hit:
                out.append({"book": pdf.name, "book_title": book_title,
                            "title": book_title, "page": 1, "level": 0,
                            "matched": hit, "by_title": True})
            continue
        for item in outline:
            hit = matched(item["title"])
            if hit:
                out.append({"book": pdf.name, "book_title": book_title,
                            "title": item["title"], "page": item["page"],
                            "level": item["level"], "matched": hit})
    out.sort(key=lambda p: (p["book"], p["page"]))
    return out


def topic_map():
    """Every topic with its pointers - the Library page's second half."""
    return [{"key": k, "label": v["label"], "pointers": pointers(k)}
            for k, v in TOPICS.items()]
