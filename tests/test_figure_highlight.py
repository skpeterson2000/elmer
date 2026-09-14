#!/usr/bin/env python3
"""The part a figure question names, cut out and enlarged beside the figure.

    python3 tests/test_figure_highlight.py

"What is component 3 in figure T-2?" names a part, and gets its box from
the pool's map; "Which symbol in figure G7-1 represents a Zener diode?"
names nothing - the answer is a place in the figure - and gets no box,
whatever the map says. Every Technician figure question is of the first
kind and every part it names is on the map; every General and Extra one
is of the second.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer.content import get_pool, load_pools  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def run():
    load_pools()
    print("\n-- a part named is a part shown --")
    tech = get_pool("tech2026")
    h = tech.figure_highlight(tech.by_id["T6C04"])
    check("component 3 of T-1 has a box", (h or {}).get("part"), "3")
    check("  as four fractions of the image", len((h or {}).get("box", [])), 4)
    check("  inside it", all(0.0 <= v <= 1.0 for v in h["box"]), True)
    check("  which is the lamp, upper right", h["box"][0] > 0.5 and h["box"][1] < 0.3, True)

    print("\n-- every Technician figure question is covered --")
    missing = []
    for q in tech.by_id.values():
        if not q.get("figure"):
            continue
        if tech.figure_highlight(q) is None:
            missing.append(q["id"])
    check("no Technician figure question without its part on the map", missing, [])

    print("\n-- a which-symbol question gets no cut-out --")
    gen = get_pool("gen2023")
    check("G7A10 names no part", gen.figure_highlight(gen.by_id["G7A10"]), None)
    extra = get_pool("extra2024")
    named = [q["id"] for q in extra.by_id.values()
             if q.get("figure") and re.search(r"component\s+\d+", q["text"], re.I)]
    check("and no Extra figure question names a component", named, [])
    check("  so none has a cut-out",
          all(extra.figure_highlight(q) is None for q in extra.by_id.values() if q.get("figure")), True)

    print("\n-- a question with no figure has nothing to show --")
    plain = next(q for q in tech.by_id.values() if not q.get("figure"))
    check("none", tech.figure_highlight(plain), None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
