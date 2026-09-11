#!/usr/bin/env python3
"""The tests cannot reach the operator's data/ - and the guard that says so.

    python3 tests/test_isolation.py

Four tests in one day wrote a stranger's club name into a unit setting, left
a certificate on the real print shelf, set a password on a real account, and
read the operator's licence class - each caught by hand, each patched by
hand. This holds the wholesale answer: every test imports _isolate first,
which moves the operator's state to a temporary directory, and a guard on
Python's audit hook that fails the run if this process opened anything under
the real data/ for writing, connected to a database there, or removed or
renamed anything there. An audit hook rather than a fingerprint of the
directory, because a live ELMER on the same machine writes its log and
database every second, and a fingerprint blames whoever wrote last.

The guard is proved against a stand-in directory, by a subprocess that
imports _isolate with the stand-in named as the thing to watch, writes into
it, and must exit 3. Proving it against the real data/ would mean touching
the real data/, which is the one thing the whole arrangement exists to stop.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, paths, prints  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


ROOT = Path(__file__).resolve().parents[1]

print("\nthe state has moved, and the content has not")
check("the state root is not data/", paths.isolated(), True)
check("  the database is under it", str(db.DB_PATH).startswith(str(paths.STATE)), True)
check("  and the print shelf", str(prints.SHELF).startswith(str(paths.STATE)), True)
check("  but the pools are still where they ship",
      (paths.CONTENT / "pools").is_dir(), True)
check("every test imports the helper first",
      sorted(p.name for p in (ROOT / "tests").glob("test_*.py")
             if "from elmer" in p.read_text() and "import _isolate" not in p.read_text()),
      [])

print("\nreading what ships under data/ is not a breach")
check("the pools can be read", (paths.CONTENT / "pools").is_dir(), True)
first = open(next((paths.CONTENT / "pools").glob("*.json"))).read(1)
check("  and reading one records nothing", (bool(first), _isolate._touched), (True, []))

print("\nthe guard fails a test that touches the watched directory")
stand_in = Path(tempfile.mkdtemp(prefix="elmer-standin-"))
(stand_in / "prints").mkdir()
(stand_in / "prints" / "index.json").write_text("[]")
script = (
    "import _isolate\n"
    "from pathlib import Path\n"
    "Path(_isolate.REAL / 'prints' / 'index.json').write_text('[{}]')\n"
    "print('wrote into the watched directory')\n")
env = dict(os.environ, ELMER_ISOLATE_WATCH=str(stand_in))
env.pop("ELMER_STATE", None)
run = subprocess.run([sys.executable, "-c", script], cwd=ROOT / "tests",
                     env=env, capture_output=True, text=True)
check("the process was failed by the guard", run.returncode, 3)
check("  and said why", "ISOLATION BREACH" in run.stderr, True)
check("  naming the file", "prints/index.json" in run.stderr, True)

# ... and one that only connects to a database there, even to read.
script = (
    "import _isolate, sqlite3\n"
    "sqlite3.connect(str(_isolate.REAL / 'elmer.db')).execute('select 1')\n")
run = subprocess.run([sys.executable, "-c", script], cwd=ROOT / "tests",
                     env=env, capture_output=True, text=True)
check("connecting to a database there is a breach even to read", run.returncode, 3)

# ... while a live server writing the same directory is not this process's
# doing, and is not blamed on it.
script = (
    "import _isolate, subprocess, sys\n"
    "subprocess.run([sys.executable, '-c', "
    "'import sys; open(sys.argv[1], \"a\").write(\"x\")', "
    "str(_isolate.REAL / 'prints' / 'index.json')])\n"
    "print('another process wrote there')\n")
run = subprocess.run([sys.executable, "-c", script], cwd=ROOT / "tests",
                     env=env, capture_output=True, text=True)
check("another process writing there is not blamed on this one", run.returncode, 0)

print("\nand passes one that leaves it alone")
script = "import _isolate\nprint('touched nothing')\n"
run = subprocess.run([sys.executable, "-c", script], cwd=ROOT / "tests",
                     env=env, capture_output=True, text=True)
check("a clean test exits clean", run.returncode, 0)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
