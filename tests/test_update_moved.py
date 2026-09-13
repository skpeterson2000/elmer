#!/usr/bin/env python3
"""The updater follows a rewritten history, and only when it can prove that
nothing here would be lost.

    python3 tests/test_update_moved.py

Two small repositories are made for it: one standing in for GitHub, one for a
unit. The unit is brought level, the repository's history is then rewritten
underneath it - the shape a purged password leaves - and the unit is asked
to update. It follows. Then the other shape: a unit with a commit of its own
on top, which the same rewrite must not take from it. It is held back, with
the same words as before.

The updater is pointed at the unit's directory for the duration; nothing here
touches this checkout.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import update  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x",
           GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)


def git(where, *args):
    done = subprocess.run(("git",) + args, cwd=where, env=ENV,
                          capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args)} in {where}: {done.stderr.strip()}")
    return done.stdout.strip()


def commit(where, name, text):
    (Path(where) / name).write_text(text)
    git(where, "add", name)
    git(where, "commit", "-q", "-m", f"add {name}")
    return git(where, "rev-parse", "--short", "HEAD")


def run():
    work = Path(tempfile.mkdtemp(prefix="elmer-update-"))
    upstream, unit = work / "upstream", work / "unit"
    upstream.mkdir()
    git(upstream, "init", "-q", "-b", "main")
    commit(upstream, "a.txt", "a")
    commit(upstream, "secret.json", '{"password": "hunter2"}')
    commit(upstream, "b.txt", "b")
    git(work, "clone", "-q", str(upstream), str(unit))
    git(unit, "checkout", "-q", "main")

    # Point the updater at the unit. ROOT is where _git runs.
    real_root, real_cache = update.ROOT, update.CACHE
    update.ROOT = unit
    update.CACHE = work / "update.json"
    try:
        print("\n-- level with the repository, and known to be --")
        st = update.check()
        check("nothing behind, nothing ahead", (st["behind"], st["ahead"]), (0, 0))
        check("  this commit written down as the repository's", st["known"], st["head"])
        check("  not moved", st["moved"], False)
        check("  not blocked", update.blocked(st), None)

        print("\n-- the repository rewrites its history --")
        # The password comes out of every commit; every hash after it changes.
        git(upstream, "filter-branch", "-f", "--index-filter",
            "git rm -q --cached --ignore-unmatch secret.json", "HEAD")
        tip = git(upstream, "rev-parse", "--short", "HEAD")
        check("the tip changed", tip != st["head"], True)
        check("  the secret is gone from it",
              "secret.json" in git(upstream, "ls-tree", "--name-only", "-r", "HEAD"), False)
        st = update.check()
        check("the unit is now ahead and behind at once",
              (st["ahead"] > 0, st["behind"] > 0), (True, True))
        check("  but its HEAD is still the one written down", st["head"], st["known"])
        check("  so the repository moved, not the unit", st["moved"], True)
        check("  and it is not blocked", update.blocked(st), None)

        print("\n-- and is followed --")
        ok, msg, detail = update.apply()
        check("applied", ok, True)
        check("  to the repository's tip", git(unit, "rev-parse", "--short", "HEAD"), tip)
        check("  saying so", "updated to" in msg, True)
        check("  the secret gone here too",
              "secret.json" in git(unit, "ls-tree", "--name-only", "-r", "HEAD"), False)
        check("  the other files kept", (unit / "a.txt").exists() and (unit / "b.txt").exists(), True)
        st = update.check()
        check("  level again", (st["behind"], st["ahead"], st["moved"]), (0, 0, False))

        print("\n-- a unit with work of its own is not followed off it --")
        mine = commit(unit, "mine.txt", "somebody's own commit")
        st = update.check()
        check("ahead by its own commit", st["ahead"], 1)
        check("  HEAD is not the one written down", st["head"] == st["known"], False)
        check("  so not moved", st["moved"], False)
        why = update.blocked(st)
        check("  and blocked, in the old words", "history has diverged" in (why or ""), True)
        ok, msg, _ = update.apply()
        check("  apply refuses", ok, False)
        check("  and the commit is still there", git(unit, "rev-parse", "--short", "HEAD"), mine)

        print("\n-- nor one with edits on the floor --")
        git(unit, "reset", "-q", "--hard", "HEAD~1")
        commit(upstream, "c.txt", "c")
        git(upstream, "filter-branch", "-f", "--index-filter",
            "git rm -q --cached --ignore-unmatch a.txt", "HEAD")
        update.check()                          # HEAD known, then upstream moved
        (unit / "b.txt").write_text("edited, not committed")
        st = update.check()
        check("the repository moved", st["ahead"] > 0, True)
        check("  but the tree is dirty, so not followed", st["moved"], False)
        check("  and blocked for the edits", "local changes" in (update.blocked(st) or ""), True)
    finally:
        update.ROOT, update.CACHE = real_root, real_cache

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
