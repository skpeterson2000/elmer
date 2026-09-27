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
import json
import logging
import re
import subprocess
import time
from datetime import date, datetime

from . import callsign, library, paths

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
# The FCC's copy prints the class under "Operator Privileges" ("Amateur
# Extra"); a class word anywhere else on the page is only trusted when it is
# the only one there.
RE_CLASS = re.compile(r"\b(Amateur Extra|Extra|Advanced|General|Technician|Novice)\b")
PRIVILEGES = "Operator Privileges"


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
            "class": _class(text),
            "expires": dates[-1].isoformat() if dates else None,
            "granted": dates[0].isoformat() if len(dates) > 1 else None}


def _class(text):
    """The operator class printed on an amateur license, in the record's
    own names (Extra, General, ...), or None."""
    at = text.find(PRIVILEGES)
    if at >= 0:
        m = RE_CLASS.search(text, at, at + 300)
        if m:
            return class_name(m.group(1))
    found = {class_name(w) for w in RE_CLASS.findall(text)}
    return found.pop() if len(found) == 1 else None


def class_name(text):
    """A class as the FCC record names it, so a paper's "Amateur Extra" and
    a record's "Extra" are the same class."""
    text = str(text or "").strip()
    return callsign.CLASS_NAMES.get(text.upper(), text.title()) if text else ""


def _reading_path(pdf):
    return pdf.parent / ".pages" / f"{pdf.stem}.json"


def reading(user_id, kind):
    """What a paper says, read once per paper rather than once per page.

    Every profile ELMER loads asks this of the amateur paper, and a Pi
    running pdftotext on every page load is a Pi doing nothing else. So
    the reading is kept beside the PDF, keyed on the PDF's own timestamp,
    and read again only when the paper is replaced. A reading that failed
    for want of poppler is not kept: it is not the paper's answer, and the
    paper reads properly the day poppler is installed."""
    pdf = paper(user_id, kind)
    if pdf is None:
        return None
    stamp = pdf.stat().st_mtime
    kept = _reading_path(pdf)
    try:
        cached = json.loads(kept.read_text(encoding="utf-8"))
        if cached.get("mtime") == stamp:
            return cached["says"]
    except FileNotFoundError:
        pass                              # never read yet: read it below
    except (OSError, ValueError, KeyError) as exc:
        log.warning("papers: could not use the kept reading %s, reading the paper again: %s", kept, exc)
    said = read(pdf)
    if said.get("readable") or said.get("pages") is not None:
        try:
            kept.parent.mkdir(parents=True, exist_ok=True)
            kept.write_text(json.dumps({"mtime": stamp, "says": said}), encoding="utf-8")
        except OSError as exc:
            log.warning("papers: could not keep the reading of %s, it will be read again: %s", pdf, exc)
    return said


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
        said = reading(user_id, kind) or {}
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


# ---- evidence: where the license indicator's answer came from
#
# Status (in force, renew, expired, cancelled, no FCC record) is one thing
# and is drawn in color. Evidence - the FCC record, the operator's own paper,
# both, or nothing - is another, and is drawn as a mark with a word on it.
# The two never share a color, and every state has words.

FCC_ANSWERS = ("current", "grace", "expired", "cancelled", "unfound")

LABELS = {
    "current": "licensed",
    "grace": "expired · renew",
    "expired": "expired",
    "cancelled": "cancelled",
    "unfound": "no FCC record",
    "unchecked": "not confirmed",
}

STATUS_WORDS = {
    "current": "in force",
    "grace": "expired, within the two years to renew without retesting",
    "expired": "expired, past the window to renew",
    "cancelled": "cancelled",
    "unfound": "no FCC record",
}


def _paper_side(reading, account_call, record_call):
    """What the amateur paper says, if it says enough to be worth showing:
    the callsign on it (the account's own where it is there), the class and
    the dates."""
    if not reading or not reading.get("readable"):
        return None
    calls = reading.get("calls") or []
    if not calls and not reading.get("expires"):
        return None
    call = next((c for c in (account_call, record_call) if c and c in calls), None) or (calls[0] if calls else None)
    return {"callsign": call, "calls": calls, "class": reading.get("class") or None,
            "expires": reading.get("expires"), "granted": reading.get("granted")}


def _dated(side):
    if side.get("granted"):
        return f"from your paper, dated {side['granted']}"
    if side.get("expires"):
        return f"from your paper, which runs to {side['expires']}"
    return "from your paper"


def evidence(fcc, account_call, record, reading, unreached=None, today=None):
    """Where the license shown for an account stands, and on what evidence.

    `fcc` is db.standing's answer from the FCC record alone. `reading` is
    what the amateur paper says (papers.reading), or None. `unreached` is
    the settings' note of a lookup that could not reach the FCC.

    Five states:
      none     nothing to go on: not looked up yet, or the FCC could not be
               reached, and no paper that can be read. "not confirmed".
      paper    the paper alone - status worked out from its expiry and
               today's date, which needs no network at all.
      fcc      the FCC record alone, as it always was.
      both     the record and the paper agree.
      differ   they disagree on the callsign, the class or the expiry, or
               the FCC has no license in force where the paper shows one.
               The record wins; the paper may be out of date.

    ELMER does not decide a license is valid from a PDF. The paper's words
    are "from your paper, dated X", never "verified".
    """
    record = record if isinstance(record, dict) else {}
    account_call = (account_call or "").strip().upper()
    record_call = (record.get("callsign") or "").strip().upper()
    side = _paper_side(reading, account_call, record_call)
    note = None
    if reading and not reading.get("readable"):
        note = f"your paper is on this unit but cannot be read: {reading.get('note') or 'no text in it'}"
    elif side and account_call and side["callsign"] and account_call not in side["calls"]:
        # A paper for another callsign says nothing about this one.
        note = f"your paper is for {side['callsign']}, not {account_call}"
        side = None

    fcc_answered = fcc in FCC_ANSWERS
    out = {"standing": fcc, "state": "none", "marks": [], "differs": [], "paper": side,
           "callsign": account_call or record_call or (side or {}).get("callsign") or "",
           "note": note, "reason": None, "fcc_says": None, "source": None}

    if fcc_answered:
        out["marks"].append("fcc")
        says = STATUS_WORDS[fcc]
        if record.get("found"):
            parts = (record_call, callsign.record_class(record),
                     f"expires {record['expires']}" if record.get("expires") else "", says)
            says = " · ".join(x for x in parts if x)
        out["fcc_says"] = says
    if side:
        out["marks"].append("paper")

    if fcc_answered and side:
        differs = []
        if record.get("found"):
            if side["calls"] and record_call and record_call not in side["calls"]:
                differs.append("callsign")
            theirs = class_name(callsign.record_class(record))
            if side["class"] and theirs and side["class"] != theirs:
                differs.append("class")
            ours, fccs = _date(side["expires"] or ""), _date(str(record.get("expires") or ""))
            if ours and fccs and ours != fccs:
                differs.append("expiry")
        else:
            differs.append("record")      # the FCC has nothing in force where the paper shows a license
        out["differs"] = differs
        out["state"] = "differ" if differs else "both"
    elif fcc_answered:
        out["state"] = "fcc"
    elif side:
        out["state"] = "paper"
        expires = _date(side["expires"] or "")
        if expires:
            st = _status_on(expires, today or date.today())
            out["standing"] = st["state"]
            out["status"] = st
        else:
            out["standing"] = "unchecked"
    else:
        if fcc == "unchecked":
            pending = record.get("pending") and record.get("callsign", "").upper() == account_call
            if pending:
                out["reason"] = record.get("reason") or "the FCC's file is being read; asked again shortly"
            elif isinstance(unreached, dict) and (unreached.get("callsign") or "").upper() == account_call:
                out["reason"] = f"the FCC could not be reached on {unreached.get('on')} - offline"
            else:
                out["reason"] = "not looked up yet"

    out["label"] = LABELS.get(out["standing"], "")
    out["source"] = {
        "fcc": f"from the FCC record for {record_call}" if record_call else "from the FCC",
        "paper": _dated(side) + " - read off the PDF, not verified with the FCC" if side else None,
        "both": f"from the FCC record for {record_call}, and your paper agrees" if record_call else None,
        "differ": "your paper and the FCC differ",
        "none": "not confirmed" + (f" - {out['reason']}" if out["reason"] else ""),
    }.get(out["state"])
    return out


def _status_on(expires, today):
    """callsign.status_for, as of a given day - so a test can stand on any
    day it likes, and the paper needs nothing but the unit's own clock."""
    days = (expires - today).days
    grace = callsign.GRACE_DAYS
    if days >= 0:
        return {"state": "current", "days": days}
    if -days <= grace:
        return {"state": "grace", "days": days, "renew_within": grace + days}
    return {"state": "expired", "days": days}


def public(ev):
    """Evidence as another person on the unit may see it: the status word,
    the marks and whether the two sources differ - not what the paper says,
    which is its owner's alone."""
    if not ev:
        return None
    source = {"paper": "from a paper held on this unit - not verified with the FCC",
              "both": "from the FCC record, and a paper held on this unit agrees",
              "differ": "a paper held on this unit and the FCC differ"}.get(ev["state"], ev.get("source"))
    return {"standing": ev["standing"], "state": ev["state"], "marks": ev["marks"],
            "label": ev["label"], "source": source}


def add(user_id, kind, stream):
    """Keep a paper. Returns (ok, message). The file is checked for being a
    PDF and for size, and nothing else - it is the person's own."""
    target = _path(user_id, kind)
    if target is None:
        return False, "not a kind of license ELMER keeps"
    head = stream.read(library.PDF_HEAD_BYTES)
    stream.seek(0)
    if not library.is_pdf(head):
        log.warning("papers: refused a %s for user %s - no PDF header in its first bytes: %r",
                    KINDS[kind], user_id, bytes(head[:16]))
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
    _reading_path(target).unlink(missing_ok=True)
    reading(user_id, kind)              # read it now, while the person is waiting on the upload anyway
    log.info("papers: %s kept for user %s", KINDS[kind], user_id)
    return True, f"{KINDS[kind]} kept"


def remove(user_id, kind):
    pdf = paper(user_id, kind)
    if not pdf:
        return False
    _drop_pages(pdf)
    _reading_path(pdf).unlink(missing_ok=True)
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
