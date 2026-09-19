"""The operator's own manuals, indexed so ELMER can point at the page.

A radio's manual is three hundred pages and the thing you need from it at a
campsite is one line on one of them - the menu number for the CW pitch, the
range the tuner will match. ELMER cannot ship anybody's manual and would not
want to; they are the makers' and the ARRL's. What it can do is read the
copies the operator already owns, once, and afterwards answer "where does it
say that?" with the file, the page and the two lines around it - from the
operator's own copy, on the operator's own machine, with or without a signal.

Everything here is deterministic. The text is what pdftotext read; the
chapters are the bookmarks the publisher put in the file - or, where there
are none, the numbered headings the publisher printed, read in their own
order (see :func:`_headings`), or a list the operator wrote beside the
book (see :func:`_own_list`); a search finds the pages that contain the
words. Nothing is summarised, inferred or generated, because a program
whose numbers are measured does not start guessing the moment it opens a
book. Where a manual has none of the three the page says so and search
still works; where a word is not in the text it is not found. That is the
whole contract, and it is one that cannot be wrong except where the
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
INDEX_VERSION = 3     # 3: chapters from printed headings and the operator's own list
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
                           "whip", "hamstick", "smith chart", "impedance",
                           "reflection"]},
    "propagation": {"label": "Propagation",
                    # "skip" alone matched "Skip Memory Channels" and "skips
                    # Tx 1"; the propagation sense always comes with its noun.
                    "words": ["propagation", "ionosphere", "ionospheric",
                              "skip zone", "skip distance", "sunspot", "solar",
                              "muf", "nvis", "grey line", "gray line",
                              "sporadic", "band conditions", "forecast",
                              "line of sight", "critical frequency"]},
    "cw": {"label": "CW and keying",
           "words": ["cw", "morse", "keyer", "paddle", "sidetone", "pitch",
                     "break-in", "qsk"]},
    # The games and the room they are played in: the guide's own chapters,
    # which no radio manual has - so this is the topic that lists them.
    "games": {"label": "Games and the table",
              "words": ["game", "gaming", "tournament", "shootout", "cutthroat",
                        "golf", "baseball", "table screen", "net control",
                        "big board", "club night", "lounge"]},
    "digital": {"label": "Digital modes",
                "words": ["digital", "ft8", "ft4", "wsjt", "js8", "jt65",
                          "msk144", "psk", "rtty", "packet", "aprs",
                          "winlink", "sound card", "soundcard", "cat control",
                          "usb audio", "decoder", "decoding", "digimode",
                          "data mode"]},
    "signals": {"label": "Signals and theory",
                "words": ["modulation", "waveform", "error correction",
                          "source encoding", "bandwidth", "spectrum",
                          "sideband", "harmonic", "intermodulation",
                          "signal-to-noise", "snr", "decibel", "reactance",
                          "resonance", "ohm's law"]},
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
             "words": ["vna", "antenna analyzer", "analyzer", "analyser",
                       "swr meter", "oscilloscope", "dummy load", "wattmeter",
                       "measurement", "multimeter", "meter", "sextant"]},
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
    # Where winget puts a portable package - which is what install.ps1
    # fetches poppler as - and the folder of aliases it puts on the PATH of
    # windows opened afterwards, not of the one ELMER was started from.
    _local = os.environ.get("LOCALAPPDATA", "")
    if _local:
        _winget = Path(_local) / "Microsoft" / "WinGet"
        FALLBACK_DIRS += [str(p) for p in _winget.glob("Packages/*Poppler*/poppler*/Library/bin")]
        FALLBACK_DIRS += [str(_winget / "Links")]

_tools = {}


def _is_poppler(path):
    """Whether the tool at `path` is poppler's, by its own banner.

    Git for Windows ships xpdf's pdftotext (version 4.00) in its bin folder,
    and a shell opened from Git has that first on the PATH. It answers to
    the same name and reads a two-column page by joining the columns, so a
    heading comes out glued to the paragraph beside it and an index made
    with it is quietly worse than one made with poppler. The banner tells
    them apart: poppler's says so.
    """
    try:
        out = subprocess.run([path, "-v"], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return b"poppler" in (out.stderr + out.stdout).lower()


def tool(name):
    """The full path of a poppler tool, or None - looked up once.

    Every copy on the PATH and in the usual places is a candidate; the
    first that is poppler's wins, and failing that the first found at all
    - a tool that reads is better than none."""
    if name in _tools:
        return _tools[name]
    exe = name + (".exe" if os.name == "nt" else "")
    candidates = []
    on_path = shutil.which(name)
    if on_path:
        candidates.append(on_path)
    for d in FALLBACK_DIRS:
        candidate = Path(d) / exe
        if candidate.is_file() and os.access(candidate, os.X_OK) and str(candidate) not in candidates:
            candidates.append(str(candidate))
    found = next((c for c in candidates if _is_poppler(c)), candidates[0] if candidates else None)
    if found and len(candidates) > 1 and found != candidates[0]:
        log.info("library: %s at %s preferred over %s - it is poppler's", name, found, candidates[0])
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


def _own_list_mtime(pdf):
    try:
        return int(_own_list_path(pdf).stat().st_mtime)
    except OSError:
        return 0


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
    if int(meta.get("own_list_mtime", 0)) != _own_list_mtime(pdf):
        return "your chapter list changed"
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
    # Word's default and the like are not titles, and neither is the name of
    # the layout file the magazine's artist saved ("Taylor.indd").
    if title.lower() in ("untitled", "microsoft word", "document") or len(title) < 3:
        return ""
    if re.search(r"\.(indd|qxd|pmd|docx?|odt|tex|fm|pdf)$", title, re.I):
        return ""
    return title[:120]


# The publisher's own numbering, one heading to a line as pdftotext prints
# it: "3. Error Detection and Error Correction", "Chapter 4 Antenna Tuner",
# "Appendix A. Source Encoding Details". A heading is short, starts with a
# capital and does not end like a sentence.
RE_HEADING = re.compile(r"^(?:(?P<chapter>Chapter|Section|Part)\s+)?(?P<num>\d{1,2})(?P<sep>[.:])?\s+(?P<title>[A-Z][^\n]{2,80}?)\s*$")
RE_APPENDIX = re.compile(r"^(?P<title>Appendix\s+[A-Z][.:]?\s+[A-Z][^\n]{2,80}?)\s*$")
HEADINGS_MIN = 3       # fewer numbered headings than this is not a table of contents
HEADINGS_PER_PAGE = 3  # more than this on one page is a list, or the contents page


def _title_case(title):
    """Chapter headings are set in title case or capitals; the steps of a
    numbered list are sentences. Every word of four letters or more starts
    with a capital - "Structured Messages and Source Encoding" does, "Press
    and hold the key for" does not."""
    words = [w for w in re.findall(r"[A-Za-z]{4,}", title)]
    if not words or not all(w[0].isupper() for w in words):
        return False
    # A line that stops on "the" or "of" is a sentence wrapped, not a title.
    return title.split()[-1].lower() not in STOPS


STOPS = {"the", "a", "an", "of", "to", "and", "or", "for", "in", "on", "with", "by",
         "at", "from", "into", "is", "are", "be", "that", "which", "your"}


def _headings(pages):
    """Chapters read from the headings printed in the text, for a file the
    publisher left no bookmarks in - a magazine article, a guide typed up
    in a word processor.

    What makes a line a chapter heading rather than a step in a numbered
    list, a footnote or a running head is the sequence and the setting:
    the headings are numbered 1, 2, 3 ... in the order the pages have them,
    at least HEADINGS_MIN of them, over more than one page, in title case,
    never more than HEADINGS_PER_PAGE to a page. A list of setup steps is
    numbered too, but its lines are sentences and it lives on one page; a
    contents page lists every chapter on one page; page numbers in a
    running head ("8 QEX July/August 2020") count up by twos and never
    start at 1. The run stops at the first number that is missing, and the
    appendices printed after it come along. Sub-numbered headings (2.1) are
    left alone: what they look like varies too much between publishers to
    read without guessing, and search reaches into every page regardless.
    """
    seen = {}                        # (style, number) -> [(page, line)], in page order
    on_page = {}                     # (style, page) -> {numbers on it}
    for page_no, text in enumerate(pages, 1):
        for line in text.split("\n"):
            line = line.strip()
            m = RE_HEADING.match(line)
            if not m:
                continue
            title = m.group("title").strip()
            if title[-1] in ".,;:" or len(title.split()) > 12 or not _title_case(title):
                continue             # a sentence, or the first line of one
            style = "chapter" if m.group("chapter") else ("dot" if m.group("sep") else "bare")
            n = int(m.group("num"))
            seen.setdefault((style, n), []).append((page_no, line))
            on_page.setdefault((style, page_no), set()).add(n)
    best = []
    for style in ("chapter", "dot", "bare"):
        run, n = [], 1
        while True:
            # The first printing of the number on a quiet page, not before
            # the chapter above it. A contents page is crowded, and so is
            # a page with a numbered table on it; a heading printed only on
            # a crowded page is taken when the run vouches for it - it is
            # chapter 1, which the contents lists too and which often
            # starts on the page the contents ends on, or the chapter after
            # it stands on a quiet page beyond.
            floor = run[-1]["page"] if run else 1
            printings = [(pg, ln) for pg, ln in seen.get((style, n), []) if pg >= floor]
            quiet = [(pg, ln) for pg, ln in printings if len(on_page[(style, pg)]) <= HEADINGS_PER_PAGE]
            hit = quiet[0] if quiet else None
            if hit is None and printings:
                last = printings[-1]
                vouched = n == 1 or any(pg >= last[0] and len(on_page[(style, pg)]) <= HEADINGS_PER_PAGE
                                        for pg, _ln in seen.get((style, n + 1), []))
                hit = last if vouched else None
            if hit is None:
                break
            run.append({"title": hit[1][:120], "page": hit[0], "level": 0})
            n += 1
        if len(run) > len(best):
            best = run
    if len(best) < HEADINGS_MIN or best[0]["page"] == best[-1]["page"]:
        return []
    last = best[-1]["page"]
    for page_no, text in enumerate(pages[last - 1:], last):
        for line in text.split("\n"):
            m = RE_APPENDIX.match(line.strip())
            if m and m.group("title")[-1] not in ".,;:":
                best.append({"title": m.group("title")[:120], "page": page_no, "level": 0})
    return best


def _own_list_path(pdf):
    return pdf.with_name(pdf.name + ".toc.txt")


def _own_list(pdf, page_count):
    """Chapters the operator wrote beside the book, as (title, [chapters]).

    A text file named after the book plus ".toc.txt" - "SignaLink_USB_
    Product_Guide.pdf.toc.txt" - one chapter to a line as the page number,
    a space, and the title; a line indented with spaces is a section under
    the chapter above it; a first line "title: ..." names the book. It is
    the operator's own table of contents for a book that has none, and it
    outranks anything read from the file.
    """
    path = _own_list_path(pdf)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return "", []
    title, out = "", []
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not out and raw.lower().startswith("title:"):
            title = raw.partition(":")[2].strip()[:120]
            continue
        m = re.match(r"^(?P<indent>\s*)(?P<page>\d{1,4})\s+(?P<title>\S.*?)\s*$", raw)
        if not m:
            continue
        page = int(m.group("page"))
        if not 1 <= page <= max(page_count, 1):
            continue
        out.append({"title": m.group("title")[:120], "page": page,
                    "level": 1 if m.group("indent") else 0})
    return title, out


def index_one(pdf):
    """Read one manual and write its index. Returns the index."""
    st = pdf.stat()
    if st.st_size > MAX_PDF_MB * 1024 * 1024:
        raise RuntimeError(f"{pdf.name} is {st.st_size // (1024 * 1024)} MB - "
                           f"larger than a manual; not indexed")
    started = time.time()
    pages = _pages(pdf)
    outline, outline_problem = _outline(pdf)
    outline_from = "bookmarks" if outline else ""
    own_title, own = _own_list(pdf, len(pages))
    if own:
        outline, outline_from = own, "your list"
    elif not outline:
        outline = _headings(pages)
        outline_from = "printed headings" if outline else ""
    meta = {
        "version": INDEX_VERSION,
        "name": pdf.name,
        "title": own_title or _title(pdf) or pdf.stem.replace("_", " "),
        "size": st.st_size, "mtime": int(st.st_mtime),
        "own_list_mtime": _own_list_mtime(pdf),
        "indexed_at": time.time(), "pages": len(pages),
        "outline": outline,
        "outline_from": outline_from,
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
            "bookmarks_from": (meta or {}).get("outline_from") or "",
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


# ------------------------------------------------------------- the pages
# The reader used to hand the browser's own PDF viewer the file with #page=N
# on the end and trust it to open there. Chromium on the Pi did; the Edge
# window on Windows loads the file and ignores the page, and a phone hands
# the file to some other app and shows nothing. So the reader draws the page
# itself: poppler renders one page to a PNG, kept here so a page is rendered
# once, and the browser's viewer is still offered for anyone who wants to
# select text or search inside the file.
PAGES = paths.STATE / "library-pages"
PAGE_DPI = 110


def page_image(name, n, dpi=PAGE_DPI):
    """The PNG of page `n` of a book on the shelf, rendered once and kept;
    None if the book is not there, the page is not, or poppler is not."""
    pdf = book(name)
    if pdf is None or n < 1:
        return None
    render = tool("pdftoppm")
    if not render:
        return None
    out_dir = PAGES / pdf.stem
    out = out_dir / f"{n}-{dpi}.png"
    if out.is_file() and out.stat().st_mtime >= pdf.stat().st_mtime:
        return out
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / f"render-{n}-{dpi}"
    try:
        subprocess.run([render, "-f", str(n), "-l", str(n), "-r", str(int(dpi)), "-png",
                        "-singlefile", str(pdf), str(stem)],
                       capture_output=True, timeout=60, check=True)
    except subprocess.CalledProcessError as exc:
        # Usually a page past the end - a stale link, an old index - which
        # is an ordinary ask and not a fault of the unit's.
        log.debug("library: pdftoppm would not render page %d of %s (exit %s)", n, pdf.name, exc.returncode)
        return None
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("library: could not render page %d of %s: %s", n, pdf.name, exc)
        return None
    made = stem.with_suffix(".png")
    if not made.is_file():
        return None
    made.replace(out)
    return out


def can_draw_pages():
    """Whether the reader can draw pages itself - poppler is here."""
    return bool(tool("pdftoppm"))


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
    chapter on the shelf whose title contains one of the words, with the
    book and the page. A book none of whose chapters say the word - or
    with no chapters at all - is read by its own title instead: a one-page
    fact sheet never has an outline, and "Hamstick Dipole Fact Sheet" says
    what it is as plainly as any chapter heading, so it points at page 1
    when the title carries one of the words. Nothing is inferred beyond
    that; search still reaches into every page.
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
        chapters = []
        for item in outline:
            hit = matched(item["title"])
            if hit:
                chapters.append({"book": pdf.name, "book_title": book_title,
                                 "title": item["title"], "page": item["page"],
                                 "level": item["level"], "matched": hit})
        if chapters:
            out.extend(chapters)
        elif meta is not None:
            # No chapter of the book says the word, or the book has none.
            # The file's own name counts as well as the title inside it: a
            # scanned instruction sheet saved as "Lakeview_Hamsticks_HF_
            # antenna_user.pdf" says "antenna" in the one place its maker's
            # metadata ("Hamstiks instructions") does not, and a paper on
            # FT8 whose chapters are "Modulation" and "Decoding" is an FT8
            # paper by its name, whole.
            hit = matched(book_title) or matched(pdf.stem.replace("_", " ").replace("-", " "))
            if hit:
                out.append({"book": pdf.name, "book_title": book_title,
                            "title": book_title, "page": 1, "level": 0,
                            "matched": hit, "by_title": True})
    # A whole book on the topic ahead of a chapter in a book about something
    # else: the Hamstick fact sheet before the FT-991A's antenna page.
    out.sort(key=lambda p: (not p.get("by_title"), p["book"], p["page"]))
    return out


def topic_map():
    """Every topic with its pointers - the Library page's second half."""
    return [{"key": k, "label": v["label"], "pointers": pointers(k)}
            for k, v in TOPICS.items()]
