#!/usr/bin/env python3
"""Every control on the antenna bench is wired to something.

    python3 tests/test_labcontrols.py

The slope slider sat on that page for a long time doing nothing at all. It was
shown for an end-fed and a dipole, its value was read in four places, and its
id was missing from the one list that decides what re-runs when something
moves - so turning it changed no drawing, no number and no advice.

A control that does nothing is worse than no control. It tells an operator the
program has considered their arrangement when it has not, and it fails
silently: nothing errors, the page just sits there looking answered.

Nothing here reads intent. It reads the ids out of lab.html, the wired list out
of lab.js, and asks that every input the antenna pane offers appears in one or
the other - the shared list, or a listener of its own.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "elmer" / "templates" / "lab.html").read_text()
JS = (ROOT / "elmer" / "static" / "lab.js").read_text()

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# Readouts the script writes into, not controls anybody touches.
READOUTS = {"an-cond-v", "an-droop-v", "an-el-v", "an-head-v", "an-radials-v",
            "an-slope-v", "an-sp-v"}
# Panels, canvases and buttons: each has its own handler and none of them is a
# value the pattern is computed from.
NOT_INPUTS = {"an-advice", "an-advise", "an-out", "an-pattern", "an-print",
              "an-suggest", "an-svg", "an-topath", "an-torf", "an-use"}


def inputs_on_the_page():
    """Every <input> or <select> the antenna pane offers, by id."""
    found = set()
    for tag in re.findall(r"<(?:input|select)\b[^>]*>", HTML):
        got = re.search(r'id="(an-[a-z0-9-]+)"', tag)
        if got:
            found.add(got.group(1))
    return found


def wired():
    """Ids that re-run the calculation when they move."""
    block = re.search(r"\[('an-type'.*?)\]\s*\n\s*\.forEach", JS, re.S)
    listed = set(re.findall(r"'(an-[a-z0-9-]+)'", block.group(1))) if block else set()
    # Anything with a listener of its own counts as wired too.
    own = set(re.findall(
        r"getElementById\('(an-[a-z0-9-]+)'\)\.addEventListener", JS))
    return listed | own


print("\nthe page's controls are found")
controls = inputs_on_the_page() - READOUTS - NOT_INPUTS
check("there are some", len(controls) >= 10, True)
check("and the slope is one of them", "an-slope" in controls, True)

print("\nevery one of them re-runs something when it moves")
live = wired()
for name in sorted(controls):
    check(name, name in live, True)

print("\nthe slope specifically, which is the one this was written for")
check("in the recompute list", "an-slope" in live, True)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
