#!/usr/bin/env python3
"""The self-check says how to put a missing package back, and never says pip.

    python3 tests/test_doctor_advice.py

./elmer.py --doctor reports Flask, numpy and scipy. A unit brought up to
date with a plain git pull does not get new packages, so this is where the
operator finds out one is missing, and what it says next is what they will
type. It used to say "pip3 install flask", which Raspberry Pi OS refuses
(PEP 668) and which, anywhere else, can install into a Python that is not
the one ELMER runs. What is held here:

  - a package that is here is reported with its version;
  - a missing one names the platform's own installer: ./install.sh on Linux
    and the Pi, install.ps1 on Windows;
  - no line of the advice says pip, on either platform;
  - an ImportError is what counts as missing - nothing broader is swallowed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def missing(name):
    raise ImportError(f"No module named {name!r}")


def main():
    from elmer import diagnostics, host

    print("\n-- what is here is reported with its version --")
    here = diagnostics.package_lines()
    check("one line for each of flask, numpy and scipy", [l.split()[0] for l in here], ["flask", "numpy", "scipy"])
    check("  none of them says missing on this machine", any("NOT INSTALLED" in l for l in here), False)

    real = host.WINDOWS
    try:
        for windows, step in ((False, "./install.sh"), (True, "install.ps1")):
            where = "Windows" if windows else "Linux and the Pi"
            host.WINDOWS = windows
            print(f"\n-- missing, on {where} --")
            lines = diagnostics.package_lines(importer=missing)
            check(f"every missing package names {step}", all(f"run {step}" in l for l in lines), True)
            check("  and says it is not installed", all("NOT INSTALLED" in l for l in lines), True)
            check("  and no line says pip", [l for l in lines if "pip" in l.lower()], [])
    finally:
        host.WINDOWS = real

    print("\n-- only an ImportError counts as missing --")

    def broken(name):
        raise RuntimeError("a package that is present but broken")
    try:
        diagnostics.package_lines(importer=broken)
        check("a broken package is not reported as merely missing", "swallowed", "raised")
    except RuntimeError:
        check("a broken package is not reported as merely missing", "raised", "raised")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
