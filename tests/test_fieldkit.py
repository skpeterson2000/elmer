#!/usr/bin/env python3
"""Checks on the two claims Make Contact now makes about working metal.

    python3 tests/test_fieldkit.py

Most of what that page says is judgement, and judgement cannot be tested. Two
parts of it are not judgement.

The first is which metals take solder. Copper does, and the whole reason the
plumbing entries are there is that they solder. Zinc, aluminium oxide and the
paint on a coat hanger do not, with anything a person has in a vehicle - and
somebody standing at a fence at dusk with an iron and a reel of solder is
being sent to fail. So no entry that is not copper may recommend soldering,
and the copper ones have to say which heat: an iron will not take half-inch
pipe anywhere near tin, and telling somebody it will is telling them their
joint is cold when it is only cool.

The second is the arc-welding note. It describes something that genuinely
works and can genuinely blind somebody, and the half-remembered version of it
is the dangerous one. The eye, the hydrogen, the cables and the zinc all have
to still be there. A later edit that trims it for length is exactly what these
checks exist to catch.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import conductors, fieldkit  # noqa: E402

FAILS = []

# Anything that reads as an instruction to solder. "Will not take", "refuses"
# and the rest are the negations that make a mention safe.
NEGATED = ("will not take", "will not solder", "not solder", "refuses solder",
           "does not need to")


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    rows = conductors.improvised()
    print("\n-- every material somebody is sent looking for can be worked --")
    check("there are some", len(rows) > 0, True)
    check("each says where it is found",
          all(r["found"].strip() for r in rows), True)
    check("each says how to cut and join it",
          all(r["work"].strip() for r in rows), True)

    print("\n-- and only the copper ones are told to solder --")
    for row in rows:
        spec = conductors.INDEX[row["key"]]
        work = row["work"].lower()
        if spec["material"] == "copper":
            check(f"{row['key']} solders, and says so", "solder" in work, True)
        elif "solder" in work:
            check(f"{row['key']} says solder will not take",
                  any(n in work for n in NEGATED), True)
        else:
            check(f"{row['key']} does not mention solder", True, True)

    print("\n-- fat copper wants a torch, not an iron --")
    by_key = {r["key"]: r["work"].lower() for r in rows}
    check("half-inch pipe says torch", "torch" in by_key["pipe12"], True)
    check("  and says an iron will not do it",
          "iron cannot" in by_key["pipe12"], True)

    print("\n-- every operation offers a way through without the tool --")
    for op in fieldkit.ladder():
        check(f"{op['key']} names the tool it wants",
              bool(op["first"].strip()), True)
        check(f"  and {len(op['instead'])} things that have stood in for it",
              len(op["instead"]) >= 3, True)
        check("  and says why it matters", bool(op["why"].strip()), True)
    check("checking it names the instrument that answers which way to cut",
          "VNA" in dict((o["key"], o["first"]) for o in fieldkit.ladder())
          ["check"], True)

    print("\n-- cutting by fatigue says where the crack starts --")
    cut = dict((o["key"], o) for o in fieldkit.ladder())["cut"]
    aside = cut.get("aside") or {}
    body = " ".join(aside.get("body", [])).lower()
    check("there is a note about it", bool(body), True)
    check("it names the mechanism", "fatigue crack" in body, True)
    check("  and work hardening alongside it", "work-" in body, True)
    check("the nick is what decides where it breaks",
          "nick" in body and "decides where" in body, True)
    check("a wide bend is said not to work", "will never crack" in body, True)
    # The popular account of the Comets blames square windows. The crack was
    # traced to a rivet hole by a cutout corner, and a program that repeats
    # the tidy version to teach a real technique has taught the wrong lesson:
    # it is the flaw that starts it, which is the whole reason to file a nick.
    check("and the Comet is told accurately, not as the myth",
          ("rivet hole" in body) if "comet" in body else True, True)

    print("\n-- and it says where fatigue stops being the answer --")
    check("not on stock too thick to work by hand",
          "half-inch pipe" in body, True)
    check("and the end it leaves is called brittle", "brittle" in body, True)

    print("\n-- and the welding note still carries every warning --")
    dangers = " ".join(fieldkit.ARC["dangers"]).lower()
    check("the eye", "cornea" in dangers, True)
    check("  and that sunglasses are not it", "sunglasses" in dangers, True)
    check("the hydrogen a battery vents", "hydrogen" in dangers, True)
    check("the cables getting hot", "insulation" in dangers, True)
    check("zinc fumes off galvanised steel", "zinc" in dangers, True)
    check("and that it is the battery you leave on",
          "starts the vehicle" in dangers, True)
    check("it still ends by saying not to, for an antenna",
          "bolted joint" in fieldkit.ARC["but"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
