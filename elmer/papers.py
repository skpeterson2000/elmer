"""The operator's own license papers, kept for them and shown back to them.

The FCC issues a license as a PDF - the "official copy" from ULS, with the
full-size certificate and the wallet cut-outs on it - and the paper the
rules ask an operator to be able to produce is that file, printed. ELMER
already reads PDFs for the Library; this keeps each person's licenses the
same way, with one difference that matters: the shelf is shared by everyone
on the unit, because a manual is useful to the whole table, and a license is
not. It carries a name and a mailing address. So papers live in a folder of
the account that brought them, are served only to that account, and are
never on the shelf, never indexed for search, and never in a report.

What ELMER does with a paper is show it back - every page, drawn by poppler,
printable - and read the callsign and the dates off it where the file has
text under the picture, so the paper and the FCC record can be laid side by
side. That is verification in both directions and nothing more: ELMER does
not decide a license is valid from a PDF, any more than from a lookup.
"""
import logging
import re
import subprocess
import time
from datetime import datetime

from . import library, paths

log = logging.getLogger("elmer")

PAPERS = paths.STATE / "papers"
MAX_MB = 25                              # a license is a page or two; a scan of one is not much more
DPI = 150                                # legible on a screen and on paper

# The kinds of license a person might hold, in the order the card lists them.
KINDS = {
    "amateur": "Amateur license",
    "gmrs": "GMRS license",
    "grol": "General Radiotelephone Operator License",
    "mrop": "Marine Radio Operator Permit",
    "radar": "Ship Radar endorsement",
    "other": "Another license or permit",
}

RE_CALL = re.compile(r"\b(?:[AKNW][A-Z]?\d[A-Z]{1,3}|W[QR][A-Z]{2}\d{3}|K[A-Z]{2}\d{4})\b")
RE_DATE = re.compile(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{4}-\d{2}-\d{2}|"
                     r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
                     r" \d{1,2}, \d{4})\b")


def folder(user_id):
    return PAPERS / str(int(user_id))


def _path(user_id, kind):
    if kind not in KINDS:
        return None
    return folder(user_id) / f"{kind}.pdf"


def paper(user_id, kind):
    """The PDF of this kind this person holds, or None."""
    p = _path(user_id, kind)
    return p if p and p.is_file() else None


def _date(text):
    for fmt in ("%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def read(pdf):
    """What the paper says, where it has text to read: the callsigns on it
    and the latest date, which on a license is the expiry. A scan with no
    text under it reads as nothing, and says so."""
    if not library.tool("pdftotext"):
        return {"readable": False, "note": "poppler is not on this unit, so the paper cannot be read"}
    try:
        pages = library._pages(pdf)
    except RuntimeError as exc:
        return {"readable": False, "note": str(exc)}
    text = "\n".join(pages)
    if not text.strip():
        return {"readable": False, "pages": len(pages), "note": "a scan - the pages are pictures with no text under them"}
    calls = list(dict.fromkeys(RE_CALL.findall(text.upper())))
    dates = sorted(d for d in (_date(m) for m in RE_DATE.findall(text)) if d)
    return {"readable": True, "pages": len(pages), "calls": calls,
            "expires": dates[-1].isoformat() if dates else None,
            "granted": dates[0].isoformat() if len(dates) > 1 else None}


def _count_pages(pdf):
    try:
        return len(library._pages(pdf))
    except RuntimeError:
        return 0


def held(user_id, records=None):
    """Every paper this person has handed over, with what it says beside
    what the FCC record says, where ELMER holds one for the same call."""
    records = records or {}
    out = []
    for kind, label in KINDS.items():
        pdf = paper(user_id, kind)
        if not pdf:
            continue
        said = read(pdf)
        entry = {"kind": kind, "label": label, "name": pdf.name,
                 "added": pdf.stat().st_mtime, "pages": said.get("pages") or _count_pages(pdf),
                 "says": said, "agrees": None, "record": None}
        # The record for whichever of the person's calls is on the paper.
        for call in said.get("calls") or []:
            rec = records.get(call)
            if rec and rec.get("found"):
                entry["record"] = {"callsign": call, "expires": rec.get("expires"),
                                   "source": rec.get("source")}
                if said.get("expires") and rec.get("expires"):
                    # As dates: callook writes 05/14/2031, the paper is read
                    # to ISO, and the same day must not be called different.
                    theirs = _date(str(rec["expires"]))
                    entry["agrees"] = bool(theirs) and theirs.isoformat() == said["expires"]
                break
        out.append(entry)
    return out


def add(user_id, kind, stream):
    """Keep a paper. Returns (ok, message). The file is checked for being a
    PDF and for size, and nothing else - it is the person's own."""
    target = _path(user_id, kind)
    if target is None:
        return False, "not a kind of license ELMER keeps"
    head = stream.read(5)
    stream.seek(0)
    if head != b"%PDF-":
        return False, "that is not a PDF - the FCC's official copy is one"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    with tmp.open("wb") as out:
        size = 0
        while True:
            chunk = stream.read(1 << 16)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_MB * 1024 * 1024:
                out.close()
                tmp.unlink(missing_ok=True)
                return False, f"larger than {MAX_MB} MB - a license is a page or two"
            out.write(chunk)
    tmp.replace(target)
    _drop_pages(target)
    log.info("papers: %s kept for user %s", KINDS[kind], user_id)
    return True, f"{KINDS[kind]} kept"


def remove(user_id, kind):
    pdf = paper(user_id, kind)
    if not pdf:
        return False
    _drop_pages(pdf)
    pdf.unlink()
    log.info("papers: %s removed for user %s", KINDS[kind], user_id)
    return True


def remove_all(user_id):
    """Everything of a person's, when the person goes."""
    here = folder(user_id)
    if not here.is_dir():
        return
    for p in sorted(here.rglob("*"), reverse=True):
        try:
            p.unlink() if p.is_file() else p.rmdir()
        except OSError:
            pass
    try:
        here.rmdir()
    except OSError:
        pass


def _pages_dir(pdf):
    return pdf.parent / ".pages" / pdf.stem


def _drop_pages(pdf):
    here = _pages_dir(pdf)
    if here.is_dir():
        for p in here.iterdir():
            p.unlink(missing_ok=True)


def page_image(user_id, kind, n, dpi=DPI):
    """Page `n` of a paper as a PNG, rendered once and kept beside it."""
    pdf = paper(user_id, kind)
    if pdf is None or n < 1:
        return None
    render = library.tool("pdftoppm")
    if not render:
        return None
    out_dir = _pages_dir(pdf)
    out = out_dir / f"{n}-{dpi}.png"
    if out.is_file() and out.stat().st_mtime >= pdf.stat().st_mtime:
        return out
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / f"render-{n}-{dpi}"
    try:
        subprocess.run([render, "-f", str(n), "-l", str(n), "-r", str(int(dpi)), "-png",
                        "-singlefile", str(pdf), str(stem)],
                       capture_output=True, timeout=60, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    made = stem.with_suffix(".png")
    if not made.is_file():
        return None
    made.replace(out)
    return out


def when(stamp):
    return time.strftime("%Y-%m-%d", time.localtime(stamp))
