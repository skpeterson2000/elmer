"""The people who have thanked the developer with a coffee, named where the build is.

A supporter was promised their callsign in the credits, and a promise
needs a place. The place is SUPPORTERS.md at the top of the checkout,
beside the README - a plain list anyone can read on the repository - and
the dashboard's Software panel, under the build, which is where somebody
looks for their own name on their own unit.

The file is the list; this reads it. One entry a line, a dash and a name
or a callsign, and after a spaced dash anything the person wants said, a
month or a word. Blank lines and the prose above the list are ignored, so
the file can explain itself.

    - KC9SP - since September 2026
    - W1AW
"""
import re

from . import paths

SOURCE = paths.ROOT / "SUPPORTERS.md"
_ENTRY = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
_SPLIT = re.compile(r"\s+[-–—]\s+")     # " - ", " – ", " — "

_cache = {"stamp": None, "list": []}


def parse(text):
    """The entries in the text, in order: [{"who", "note"}]."""
    out = []
    for line in str(text or "").splitlines():
        m = _ENTRY.match(line)
        if not m:
            continue
        parts = _SPLIT.split(m.group(1), maxsplit=1)
        who = parts[0].strip()
        if not who:
            continue
        out.append({"who": who, "note": parts[1].strip() if len(parts) > 1 else ""})
    return out


def supporters(source=None):
    """The list, read again only when the file has changed."""
    path = source or SOURCE
    try:
        stamp = (path.stat().st_mtime_ns, path.stat().st_size)
    except OSError:
        return []
    if source is None and _cache["stamp"] == stamp:
        return list(_cache["list"])
    try:
        found = parse(path.read_text(encoding="utf-8"))
    except OSError:
        found = []
    if source is None:
        _cache["stamp"], _cache["list"] = stamp, found
    return list(found)


def words(entries, most=6):
    """The line the dashboard prints: the first few names, and how many more."""
    names = [e["who"] for e in entries]
    if not names:
        return ""
    shown = names[:most]
    rest = len(names) - len(shown)
    if len(shown) == 1:
        line = shown[0]
    else:
        line = ", ".join(shown[:-1]) + " and " + shown[-1]
    if rest:
        line += f" and {rest} more"
    return line
