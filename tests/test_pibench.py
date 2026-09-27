#!/usr/bin/env python3
"""The Pi benchmark runs, answers sanely, and writes its numbers.

    python3 tests/test_pibench.py

tools/pibench.py is carried to each Pi to measure what the numerical work
costs there, so it has to run first time on a machine nobody is watching.
Held here, in its quick mode:

  - it exits 0 with no network;
  - the solver's stand-in gives a half-wave dipole a feed impedance in the
    right neighborhood, which is what says the machine's numpy is sound;
  - every ground-wave curve falls with distance;
  - the golf timings come from the game's own code, and a cold launch
    speed takes no more than 12 flights;
  - --json writes every section.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
ROOT = Path(__file__).resolve().parents[1]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    scratch = Path(tempfile.mkdtemp(prefix="elmer-pibench-"))
    try:
        out = scratch / "bench.json"
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "pibench.py"), "--quick", "--json", str(out)],
                              capture_output=True, text=True, timeout=600)
        print("\n-- the quick run --")
        check("it exits 0", done.returncode, 0)
        if done.returncode != 0:
            print(done.stdout[-2000:], done.stderr[-2000:])
        try:
            r = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            check("it wrote its numbers", False, True)
            return 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    check("every section is in the file", sorted(r), ["golf", "groundwave", "imports_ms", "machine", "solver"])
    check("  and BLAS was held to one thread", r["machine"]["blas_threads"], "1")
    d = r["solver"]["dipole_check"]
    print(f"     half-wave dipole: {d['r_ohm']} {d['x_ohm']:+} j ohm")
    check("the solver's dipole is in the right neighborhood", d["ok"], True)
    check("  and it timed a fill and a solve at 100 unknowns",
          all(r["solver"]["100"][k] > 0 for k in ("fill_ms", "solve_ms")), True)
    check("every ground-wave curve falls with distance", all(g["ok"] for g in r["groundwave"].values()), True)
    check("a cold launch speed takes no more than 12 flights", r["golf"]["launch_solve_flights"] <= 12, True)
    check("  and the club yards were timed", r["golf"]["club_yards_after_slider_ms"] > 0, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
