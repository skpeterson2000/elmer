"""The other ELMERs on this machine: found, described, and tidied by consent.

A Windows machine collects copies. A zip from the repository's page unzips
as elmer-main; a second download unzips as elmer-main (1); a clone lands
somewhere else again; OneDrive puts Desktop and Documents somewhere the
person did not choose. Then a double-click lands on whichever one Explorer
happened to be showing, which is usually the one that was never installed,
and the window says "No module named flask" - true, and no help.

So the copies are looked for, in the places a person actually puts things,
and each is described in the terms that matter: is it installed, is it
connected to the repository, which build is it, how much study is in it,
when was it last used. A copy that is not installed can then hand the press
to one that is. And the installer, once, can offer to remove the ones that
hold nothing - one question each, never the one being run from, and never
one with progress in it. A copy with answers logged is somebody's study;
it is named, and left where it is.

Standard library only. This runs before Flask is known to exist, which is
the whole point of it.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# How deep under a starting point to look. Desktop\ELMER\elmer-main is
# three; deeper than four is not where anybody unzips anything.
DEPTH = 4
# Never descend into these: they are big, and no ELMER is inside them.
SKIP = {".venv", "venv", ".git", "node_modules", "site-packages", "__pycache__",
        "python", "Lib", "AppData", "Library", "Windows", "Program Files",
        "Program Files (x86)", "$Recycle.Bin", "System Volume Information"}
MARKERS = ("elmer.py", "elmer/app.py")


def is_copy(folder):
    """A folder is an ELMER if it has the program's two fixed points."""
    try:
        return all((folder / m).is_file() for m in MARKERS)
    except OSError:
        return False


def starting_points():
    """Where people put things, on this machine: home and its usual rooms,
    OneDrive's versions of the same, and the root of the system drive."""
    home = Path.home()
    rooms = ["", "Desktop", "Downloads", "Documents", "ELMER", "elmer"]
    bases = [home]
    one = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if one:
        bases.append(Path(one))
    drive = Path(os.environ.get("SystemDrive", "C:") + os.sep) if os.name == "nt" else None
    out = []
    for base in bases:
        for room in rooms:
            p = base / room if room else base
            if p.is_dir():
                out.append((p, DEPTH))
    # The drive's root, one level: C:\ELMER, not every folder on C:.
    if drive and drive.is_dir():
        out.append((drive, 1))
    # Wherever this copy is - its parent may hold the others beside it.
    out.append((ROOT.parent, 2))
    seen, unique = set(), []
    for p, depth in out:
        key = str(p.resolve()).lower()
        if key not in seen:
            seen.add(key)
            unique.append((p, depth))
    return unique


def find(points=None, budget_s=8.0):
    """Every ELMER under the starting points, this one included, as paths.

    `points` is a list of (folder, depth). Bounded: a few levels deep, the
    big folders skipped, and a clock on the whole walk, because a launcher
    that spends a minute looking for its siblings has become the problem it
    was looking for.
    """
    points = points if points is not None else starting_points()
    started = time.monotonic()
    found, seen = [], set()

    def note(folder):
        key = str(folder.resolve()).lower()
        if key not in seen:
            seen.add(key)
            found.append(folder.resolve())

    def walk(folder, level, depth):
        if time.monotonic() - started > budget_s:
            return
        if is_copy(folder):
            note(folder)
        if level >= depth:
            return
        try:
            with os.scandir(folder) as it:
                subs = [e for e in it if e.is_dir(follow_symlinks=False)]
        except OSError:
            return
        for e in subs:
            if e.name in SKIP or e.name.startswith("."):
                continue
            walk(Path(e.path), level + 1, depth)

    for p, depth in points:
        walk(Path(p), 0, depth)
    return sorted(found, key=lambda p: str(p).lower())


def _build(folder):
    """Commit, date and kind, from git when it is a checkout, else BUILD.json."""
    if (folder / ".git").exists():
        try:
            head = subprocess.run(["git", "-C", str(folder), "log", "-1", "--format=%h%x1f%cs%x1f%s"],
                                  capture_output=True, text=True, timeout=10).stdout.strip()
            if head:
                commit, date, subject = (head.split("\x1f") + ["", ""])[:3]
                return {"commit": commit, "date": date, "subject": subject, "kind": "checkout"}
        except (OSError, subprocess.SubprocessError):
            pass
        return {"commit": "", "date": "", "subject": "", "kind": "checkout"}
    try:
        b = json.loads((folder / "BUILD.json").read_text(encoding="utf-8-sig"))
        return {"commit": b.get("commit", ""), "date": b.get("date", ""),
                "subject": b.get("subject", ""), "kind": "portable"}
    except (OSError, ValueError):
        return {"commit": "", "date": "", "subject": "", "kind": "download"}


def _answers(folder):
    """How much study a copy holds: answers logged, or 0."""
    db = folder / "data" / "elmer.db"
    if not db.is_file():
        return 0
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=2)
        try:
            return int(conn.execute("SELECT COUNT(*) FROM answer_log").fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return 0


def _last_used(folder):
    log = folder / "data" / "elmer.log"
    try:
        return log.stat().st_mtime
    except OSError:
        return 0.0


def describe(folder):
    """One copy, in the terms that matter."""
    folder = Path(folder)
    installed = ((folder / ".venv" / "Scripts" / "python.exe").is_file()
                 or (folder / ".venv" / "bin" / "python").is_file()
                 or (folder / "python" / "python.exe").is_file())
    build = _build(folder)
    answers = _answers(folder)
    settings = [n for n in ("mail.json", "drop.json") if (folder / "data" / n).is_file()]
    reports = list((folder / "data").glob("elmer-report-*.txt")) if (folder / "data").is_dir() else []
    return {
        "path": str(folder),
        "this": folder.resolve() == ROOT.resolve(),
        "installed": installed,
        "connected": build["kind"] == "checkout",
        "kind": build["kind"],
        "commit": build["commit"],
        "date": build["date"],
        "answers": answers,
        # Progress is anything of the operator's: study, settings, reports.
        "progress": bool(answers or settings or reports),
        "last_used": _last_used(folder),
    }


def survey(points=None):
    """Every copy, described, best first: installed and connected before
    not, then newest, then most used."""
    rows = [describe(p) for p in find(points)]
    rows.sort(key=lambda r: (r["installed"], r["connected"], r["date"] or "",
                             r["last_used"]), reverse=True)
    return rows


def best_other(rows=None):
    """The copy to hand a press to: installed, and not this one."""
    rows = rows if rows is not None else survey()
    for r in rows:
        if r["installed"] and not r["this"]:
            return r
    return None


def line(r):
    """One copy as a line somebody can read."""
    what = "installed" if r["installed"] else "not installed"
    if r["connected"]:
        what += ", connected"
    build = f"build {r['commit']}" + (f" of {r['date']}" if r["date"] else "") if r["commit"] else "no build named"
    study = f"{r['answers']} answers logged" if r["answers"] else "no study in it"
    if r["progress"] and not r["answers"]:
        study = "settings or reports in it"
    used = time.strftime("last used %Y-%m-%d", time.localtime(r["last_used"])) if r["last_used"] else "never run"
    return f"{r['path']}\n      {what}; {build}; {study}; {used}" + ("  <- this one" if r["this"] else "")


def launcher(folder):
    """The command that starts a copy the way a double-click does."""
    folder = Path(folder)
    if os.name == "nt":
        return [str(folder / "elmer.cmd")]
    return [str(folder / "elmer.py")]


def remove(folder):
    """Delete a copy. Refuses this one, and refuses one with progress in it -
    the caller asks, this checks again, because the two are different
    moments and a folder can gain a database between them."""
    r = describe(folder)
    if r["this"]:
        return False, "that is the copy being run from"
    if r["progress"]:
        return False, "it has study, settings or reports in it"
    try:
        shutil.rmtree(folder)
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, "removed"
