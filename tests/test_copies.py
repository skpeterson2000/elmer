#!/usr/bin/env python3
"""The other ELMERs on a machine: found, told apart, and removed only when
empty and only when asked.

    python3 tests/test_copies.py

Four copies are made in a scratch folder: one installed with study in it,
one installed and empty, one a bare download with settings in it, one a
bare download with nothing. The finder is pointed at the scratch folder
only - never at this machine's real homes - and asked what it makes of
them, which one a press should go to, and which it will and will not
remove.
"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import copies  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def make_copy(where, installed=False, answers=0, settings=False, build=None):
    where.mkdir(parents=True)
    (where / "elmer.py").write_text("# stand-in\n")
    (where / "elmer").mkdir()
    (where / "elmer" / "app.py").write_text("# stand-in\n")
    if installed:
        (where / ".venv" / "Scripts").mkdir(parents=True)
        (where / ".venv" / "Scripts" / "python.exe").write_bytes(b"")
    if answers or settings:
        (where / "data").mkdir()
    if answers:
        conn = sqlite3.connect(where / "data" / "elmer.db")
        conn.execute("CREATE TABLE answer_log (id INTEGER)")
        conn.executemany("INSERT INTO answer_log VALUES (?)", [(i,) for i in range(answers)])
        conn.commit()
        conn.close()
    if settings:
        (where / "data" / "mail.json").write_text("{}")
    if build:
        (where / "BUILD.json").write_text(json.dumps(build))
    return where


def run():
    scratch = Path(tempfile.mkdtemp(prefix="elmer-copies-"))
    studied = make_copy(scratch / "Desktop" / "ELMER" / "elmer-main", installed=True, answers=412,
                        build={"commit": "abc1234", "date": "2026-09-01"})
    fresh = make_copy(scratch / "Downloads" / "elmer-main (1)", installed=True,
                      build={"commit": "def5678", "date": "2026-09-13"})
    settings_only = make_copy(scratch / "elmer-old", settings=True)
    empty = make_copy(scratch / "Documents" / "elmer-main")
    (scratch / "Desktop" / "notes").mkdir()             # not an ELMER
    (scratch / "Desktop" / "ELMER" / "elmer-main" / "node_modules").mkdir()
    make_copy(scratch / "Desktop" / "ELMER" / "elmer-main" / "node_modules" / "x")   # skipped

    points = [(scratch, 4)]

    print("\n-- found --")
    found = copies.find(points)
    check("four copies", len(found), 4)
    check("  and not the one under node_modules",
          any("node_modules" in str(p) for p in found), False)
    check("  the plain folder is not one", any(p.name == "notes" for p in found), False)

    print("\n-- told apart --")
    by = {r["path"]: r for r in copies.survey(points)}
    s = by[str(studied.resolve())]
    check("the studied one is installed", s["installed"], True)
    check("  with its answers counted", s["answers"], 412)
    check("  and progress", s["progress"], True)
    check("  a portable build, by its stamp", (s["kind"], s["commit"]), ("portable", "abc1234"))
    f = by[str(fresh.resolve())]
    check("the fresh one is installed and empty", (f["installed"], f["progress"]), (True, False))
    so = by[str(settings_only.resolve())]
    check("settings alone are progress", (so["installed"], so["progress"]), (False, True))
    e = by[str(empty.resolve())]
    check("the bare download is neither", (e["installed"], e["progress"], e["kind"]),
          (False, False, "download"))
    check("none of them is this one", any(r["this"] for r in by.values()), False)

    print("\n-- the one a press goes to --")
    best = copies.best_other(copies.survey(points))
    check("an installed one", best["installed"], True)
    check("  the newest of the installed", best["path"], str(fresh.resolve()))
    check("its launcher is its own", Path(copies.launcher(best["path"])[0]).parent,
          Path(best["path"]))

    print("\n-- a line somebody can read --")
    text = copies.line(s)
    check("says installed", "installed" in text, True)
    check("  the build", "build abc1234" in text, True)
    check("  the study", "412 answers" in text, True)
    check("  and never run, with no log", "never run" in text, True)

    print("\n-- removing: only the empty, only when asked --")
    ok, why = copies.remove(studied)
    check("the studied one is refused", ok, False)
    check("  for its study", "study" in why, True)
    check("  and still there", studied.exists(), True)
    ok, why = copies.remove(settings_only)
    check("settings alone are enough to refuse", ok, False)
    ok, why = copies.remove(copies.ROOT)
    check("this checkout is refused", ok, False)
    check("  as the copy being run from", "run from" in why, True)
    ok, why = copies.remove(empty)
    check("the empty download goes", ok, True)
    check("  and is gone", empty.exists(), False)
    check("  and the rest are not", len(copies.find(points)), 3)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
