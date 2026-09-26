"""The operator's own certificates - the wall in the pro shop.

What a radio operator actually hangs up: an eWAC, an eDX, a contest
plaque, a first-contact certificate. Each person's are theirs: kept in a
folder of their account's on the unit, hung under their own callsign when
they are the one at the table, and never in the repository - the program
carries nobody's wall. A certificate arrives as a picture (a PNG or JPEG;
eQSL and LoTW hand them out that way), is sized once to the wall, and
carries a caption the person wrote: the title, a line about it, who issued
it and when, the number. A picture with no caption hangs under its file
name; there is no caption without a picture.

The wall is for showing, so the pictures are served to anyone at the
table - that is what a wall is - but only the account that hung them can
take them down, and they leave with the account.
"""
import json
import logging
import re
import subprocess
import tempfile
import time
from pathlib import Path

from . import library, paths

log = logging.getLogger("elmer")

AWARDS = paths.STATE / "awards"
MAX_MB = 20
# A certificate arrives as a PDF at least as often as a picture: that is what
# a contest organizer emails and what LoTW prints. The wall hangs pictures, so
# a PDF is rendered to one at the door - its first page, which is the
# certificate; nobody issues a two-page award.
PDF_DPI = 150
WIDTH = 1400                    # sized to the wall once, not on every look
CAPTIONS = "captions.json"
FIELDS = ("title", "detail", "issued", "number")


def folder(user_id):
    return AWARDS / str(int(user_id))


def _captions(user_id):
    p = folder(user_id) / CAPTIONS
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_captions(user_id, captions):
    folder(user_id).mkdir(parents=True, exist_ok=True)
    (folder(user_id) / CAPTIONS).write_text(json.dumps(captions, indent=1, ensure_ascii=False), encoding="utf-8")


def wall(user_id):
    """This person's certificates, in the order they were hung."""
    here = folder(user_id)
    if not here.is_dir():
        return []
    captions = _captions(user_id)
    out = []
    for p in sorted(here.glob("*.jpg"), key=lambda q: q.stat().st_mtime):
        c = captions.get(p.name, {})
        out.append({"name": p.name, "url": f"/awards/{int(user_id)}/{p.name}",
                    "title": c.get("title") or p.stem.replace("-", " "),
                    "detail": c.get("detail", ""), "issued": c.get("issued", ""), "number": c.get("number", ""),
                    "hung": p.stat().st_mtime})
    return out


def _slug(text):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:40] or "certificate"


def _first_page(data):
    """A PDF's first page as PNG bytes, or None when it cannot be rendered.

    Rendered with poppler, the same tool the Library reads manuals with, so a
    unit that can index a book can hang a certificate and one that cannot is
    told plainly rather than shown a broken frame.
    """
    from . import library
    render = library.tool("pdftoppm")
    if not render:
        return None
    with tempfile.TemporaryDirectory(prefix="elmer-award-") as tmp:
        src = Path(tmp) / "in.pdf"
        src.write_bytes(data)
        stem = Path(tmp) / "page"
        try:
            subprocess.run([render, "-f", "1", "-l", "1", "-r", str(PDF_DPI),
                            "-png", "-singlefile", str(src), str(stem)],
                           capture_output=True, timeout=60, check=True)
        except (OSError, subprocess.SubprocessError):
            return None
        made = stem.with_suffix(".png")
        return made.read_bytes() if made.is_file() else None


def add(user_id, stream, filename, caption):
    """Hang one. The picture is read by PIL, sized to the wall, and kept as
    a JPEG; anything PIL cannot open is refused. Returns (ok, message)."""
    from io import BytesIO
    try:
        from PIL import Image
    except ImportError:
        return False, "PIL is not on this unit, so a picture cannot be sized"
    data = stream.read(MAX_MB * 1024 * 1024 + 1)
    if len(data) > MAX_MB * 1024 * 1024:
        return False, f"larger than {MAX_MB} MB"
    if library.is_pdf(data):
        page = _first_page(data)
        if page is None:
            return False, ("that is a PDF and this unit has no poppler to render "
                           "one - install it from the dashboard's self-check, or "
                           "hang a PNG or a JPEG instead")
        data = page
    try:
        im = Image.open(BytesIO(data))
        im.load()
    except Exception:
        return False, "that is not something ELMER can read - a PDF, a PNG or a JPEG is"
    if im.mode not in ("RGB", "L"):
        # a transparent certificate on a white sheet, as it would be printed
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
        im = bg
    elif im.mode == "L":
        im = im.convert("RGB")
    if im.width > WIDTH:
        im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
    here = folder(user_id)
    here.mkdir(parents=True, exist_ok=True)
    stem = _slug((caption or {}).get("title") or filename.rsplit(".", 1)[0])
    name = f"{stem}.jpg"
    n = 2
    while (here / name).is_file():
        name = f"{stem}-{n}.jpg"
        n += 1
    im.save(here / name, "JPEG", quality=88, optimize=True)
    captions = _captions(user_id)
    captions[name] = {k: str((caption or {}).get(k) or "")[:200] for k in FIELDS}
    _save_captions(user_id, captions)
    log.info("awards: %s hung for user %s", name, user_id)
    return True, name


def recaption(user_id, name, caption):
    if not (folder(user_id) / name).is_file():
        return False
    captions = _captions(user_id)
    captions[name] = {k: str((caption or {}).get(k) or "")[:200] for k in FIELDS}
    _save_captions(user_id, captions)
    return True


def remove(user_id, name):
    if "/" in name or "\\" in name or not name.endswith(".jpg"):
        return False
    p = folder(user_id) / name
    if not p.is_file():
        return False
    p.unlink()
    captions = _captions(user_id)
    captions.pop(name, None)
    _save_captions(user_id, captions)
    log.info("awards: %s taken down for user %s", name, user_id)
    return True


def remove_all(user_id):
    here = folder(user_id)
    if not here.is_dir():
        return
    for p in here.iterdir():
        try:
            p.unlink()
        except OSError:
            pass
    try:
        here.rmdir()
    except OSError:
        pass


def when(stamp):
    return time.strftime("%Y-%m-%d", time.localtime(stamp))
