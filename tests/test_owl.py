#!/usr/bin/env python3
"""Where the stern owl is allowed to appear, and where it is not.

    python3 tests/test_owl.py

It is a character, and a character spent everywhere is spent. Three moments
earn it and the rest of the program does without.

Not an ordinary wrong answer. Spaced repetition works by finding what you get
wrong - missing is the signal the scheduler runs on - and a disapproving face
on that is disapproving of the mechanism. It also happens dozens of times an
evening, which is how a character stops meaning anything by Thursday.

What earns it: forgetting something you had learned, a limit somebody can
exceed with a person standing in the field, and reading privileges above the
ones you hold.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
STUDY = (ROOT / "elmer" / "static" / "study.js").read_text()

import _isolate  # noqa: E402,F401  - before anything from elmer
import elmer.app as appmod  # noqa: E402
from elmer import srs  # noqa: E402
from elmer.app import app  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


print("\nthe mark exists and is small enough to sit in a line of text")
owl = ROOT / "elmer" / "static" / "owl-mind.png"
check("it is there", owl.is_file(), True)
check("and not a page-weight of it", owl.stat().st_size < 60_000, True)

print("\nan ordinary miss does not get it")
# The guard is in the markup: lapseNote returns nothing unless res.lapsed.
check("the note is behind a lapse test", "if (!res.lapsed) return ''" in STUDY,
      True)
# The picture appears once, and inside the function that is guarded. An
# earlier version of this test searched for the word "owl" and matched the
# comment explaining why it is not used everywhere.
check("the picture is used exactly once", STUDY.count("owl-mind.png"), 1)
check("and that once is inside lapseNote",
      "owl-mind.png" in STUDY.split("function lapseNote")[1]
      .split("\nfunction ")[0], True)

print("\nwhat counts as having learned something")
check("a day, not ten minutes", srs.LEARNED_DAYS, 1.0)
# RELEARN_DAYS is ten minutes. A card at ten minutes has not been learned, and
# an earlier draft of this used it as the threshold.
check("and that is well past the relearn step",
      srs.LEARNED_DAYS > srs.RELEARN_DAYS * 10, True)

print("\nreading a licence class you do not hold - upward only")
app.config["TESTING"] = True
real = appmod._own_class
try:
    with app.test_client() as client:
        def above(held, reading):
            appmod._own_class = lambda: held
            return client.get("/api/bandplan?class=" + reading).get_json()["above_yours"]

        check("Technician reading Extra", above("Technician", "Extra"), True)
        check("Technician reading General", above("Technician", "General"), True)
        check("General reading Extra", above("General", "Extra"), True)
        # Downward is not a claim. An Extra reading the Technician plan is
        # looking at a subset of what they hold, and crying wolf there is how
        # a warning stops being read.
        check("Extra reading Technician", above("Extra", "Technician"), False)
        check("Extra reading General", above("Extra", "General"), False)
        check("and a class reading itself", above("General", "General"), False)
        # No licence on file is not the same as holding a low one.
        appmod._own_class = lambda: ""
        check("nothing known, nothing claimed",
              client.get("/api/bandplan?class=Extra").get_json()["above_yours"],
              False)
finally:
    appmod._own_class = real

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
