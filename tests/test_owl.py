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
exceed with a person standing in the field, reading privileges above the
ones you hold, and answering out of the network tab (peeking.py).
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
# The picture appears twice on the study page, each inside a function with a
# guard of its own: lapseNote for a forgotten card, wireNote for an answer
# read off the wire. An earlier version of this test searched for the word
# "owl" and matched the comment explaining why it is not used everywhere.


def body(name):
    return STUDY.split("function " + name)[1].split("\nfunction ")[0]


check("the picture is used exactly twice", STUDY.count("owl-mind.png"), 2)
check("  once inside lapseNote", "owl-mind.png" in body("lapseNote"), True)
check("  once inside wireNote", "owl-mind.png" in body("wireNote"), True)
check("  and wireNote draws nothing without a peek", "if (!wire) return ''" in body("wireNote"), True)

print("\nwhat counts as having learned something")
check("a day, not ten minutes", srs.LEARNED_DAYS, 1.0)
# RELEARN_DAYS is ten minutes. A card at ten minutes has not been learned, and
# an earlier draft of this used it as the threshold.
check("and that is well past the relearn step",
      srs.LEARNED_DAYS > srs.RELEARN_DAYS * 10, True)

print("\nreading a license class you do not hold - upward only")
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
        # No license on file is not the same as holding a low one.
        appmod._own_class = lambda: ""
        check("nothing known, nothing claimed",
              client.get("/api/bandplan?class=Extra").get_json()["above_yours"],
              False)
finally:
    appmod._own_class = real

print("\nthe class picker is a view, and not a claim")
BANDPLAN = (ROOT / "elmer" / "static" / "bandplan.js").read_text()
# It used to save the choice to the profile on every change, and that one
# line had two quiet consequences. The study pools are gated on the license,
# so reading Extra here opened every pool on the dashboard and at the table.
# And the owl just above compares the class being read with the class held,
# so with the setting chasing the dropdown the two were never different and
# the owl could not appear at all - the warning defeated by the page it
# warns on.
check("choosing a class to read writes no license anywhere",
      "license_class" in BANDPLAN, False)
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
with app.test_client() as client:
    # A page of somebody's asks who is at the controls before it opens.
    client.post("/api/users/switch", json={"id": 1}, environ_base={"REMOTE_ADDR": "127.0.0.1"})
    from elmer import db
    before = db.get_profile(db.connect())["settings"].get("license_class")
    client.get("/api/bandplan?class=Extra")
    after = db.get_profile(db.connect())["settings"].get("license_class")
    check("  reading Amateur Extra leaves the stored license alone",
          (before, after), (None, None))
    client.post("/api/settings", json={"license_class": "General"}, environ_base=LOCAL)
    client.get("/api/bandplan?class=Extra")
    page = client.get("/bandplan", environ_base=LOCAL).data.decode("utf-8")
    check("  and the page opens on the class held, not the one last read",
          ('<option value="General" selected>' in page,
           '<option value="Extra" selected>' in page), (True, False))
    check("  which is what leaves the owl something to compare",
          client.get("/api/bandplan?class=Extra").get_json()["above_yours"], True)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
