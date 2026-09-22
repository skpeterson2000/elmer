#!/usr/bin/env python3
"""What the ball does when it lands, as a table.

    python3 tools/golf_roll.py                  the run, every club on every surface
    python3 tools/golf_roll.py --fringe         the fringe argument, both ways
    python3 tools/golf_roll.py --skip           how often a stinger skips off water
    python3 tools/golf_roll.py --wind           what the wind does to the run

The landing model has real knobs in it now - a descent angle, a landing
speed, a spin check, and a friction for every surface - and knobs are only
worth having if they can be turned while looking at something. Playing
eighteen holes and squinting is not looking at something.

Nothing here touches a course, a database or the network. It is arithmetic
over the constants in elmer/golf.py, printed.
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elmer import golf  # noqa: E402

CLUBS = ("driver", "wood", "iron", "wedge")
SURFACES = ("green", "fringe", "fairway", "rough", "sand")


def table(firmness=1.0, friction=None, note=""):
    """Yards of run, full swing, no wind, by club and surface."""
    was = dict(golf.FRICTION)
    if friction:
        golf.FRICTION.update(friction)
    try:
        print(f"\n  run in yards - full swing, no wind, firmness {firmness:.2f}{note}")
        print("  " + "surface".ljust(10) + "".join(c.rjust(9) for c in CLUBS))
        for lie in SURFACES:
            row = [golf.run_yards(c, lie, firmness=firmness) for c in CLUBS]
            print("  " + lie.ljust(10) + "".join(f"{v:9.1f}" for v in row))
    finally:
        golf.FRICTION.clear()
        golf.FRICTION.update(was)


def fringe():
    """The argument, both ways, side by side.

    The model has the collar braking harder than the fairway, which is
    what the game has always done and what test_golf.py pins. The other
    reading is that a collar is cut near fairway height, so it should run
    a touch faster. Here is what each does to a ball.
    """
    print("\nTHE FRINGE, BOTH WAYS")
    print("\n  as it stands - the collar brakes harder than the fairway")
    table(friction={"fringe": golf.FRICTION["fringe"]}, note="  [fringe as shipped]")
    print("\n  the other reading - a collar runs a touch faster than the fairway")
    table(friction={"fringe": golf.FRINGE_IF_FAST}, note="  [fringe if fast]")
    a = golf.run_yards("wedge", "fringe")
    b = golf.run_yards("wedge", "fairway")
    print(f"\n  as shipped, a wedge onto the collar runs {a:.1f} yards "
          f"against {b:.1f} on the fairway.")
    was = golf.FRICTION["fringe"]
    golf.FRICTION["fringe"] = golf.FRINGE_IF_FAST
    c = golf.run_yards("wedge", "fringe")
    golf.FRICTION["fringe"] = was
    print(f"  the other way it runs {c:.1f}, which is {c - b:+.1f} against the fairway.")
    print("\n  A chip that has to stop on the collar is the shot to judge it by.")


def skip(trials=20000):
    """How often a ball arriving at water actually comes out of it."""
    rng = random.Random(7)
    print("\nTHE SKIP - how often a ball at water comes out of it\n")
    print("  " + "club".ljust(9) + "shot".ljust(12) + "descent".rjust(9)
          + "pace".rjust(7) + "skips".rjust(9))
    for club in CLUBS:
        for flair in (None, "stinger"):
            angle = golf.descent_angle(club, flair)
            pace = golf.landing_speed(club)
            hits = sum(golf.skips(angle, pace, rng) for _ in range(trials))
            print("  " + club.ljust(9) + (flair or "ordinary").ljust(12)
                  + f"{angle:7.1f}   " + f"{pace:7.2f}"
                  + f"{100.0 * hits / trials:8.1f}%")
    print(f"\n  Skips need flatter than {golf.SKIP_ANGLE:.0f} deg and quicker than "
          f"{golf.SKIP_SPEED:.2f}.")
    print("  An ordinary shot comes down between "
          f"{min(golf.DESCENT.values()):.0f} and {max(golf.DESCENT.values()):.0f} degrees "
          "and can never do it.")


def wind():
    """What the wind does to the run, by the clock."""
    print("\nTHE WIND ON THE RUN - a driver on a fairway\n")
    print("  " + "out of".ljust(10) + "roll x".rjust(8) + "run".rjust(8))
    for hour in (12, 1, 3, 5, 6, 7, 9, 11):
        print("  " + f"{hour} o'clock".ljust(10)
              + f"{golf.wind_roll(hour):8.3f}"
              + f"{golf.run_yards('driver', 'fairway', hour):8.1f}")
    print(f"\n  and with no wind at all: "
          f"{golf.run_yards('driver', 'fairway'):.1f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fringe", action="store_true", help="the fringe argument, both ways")
    ap.add_argument("--skip", action="store_true", help="how often a stinger skips")
    ap.add_argument("--wind", action="store_true", help="what the wind does to the run")
    args = ap.parse_args()

    if args.fringe:
        return fringe()
    if args.skip:
        return skip()
    if args.wind:
        return wind()

    print("THE LANDING MODEL, AS IT STANDS")
    print(f"\n  {'club':9}{'descent':>9}{'lands at':>10}{'spin':>7}")
    for c in CLUBS:
        print(f"  {c:9}{golf.DESCENT[c]:8.0f} deg{golf.V_LAND[c]:10.3f}"
              f"{golf.SPIN_RATE[c]:7.2f}")
    for firm in (0.65, 1.0, 1.35):
        table(firmness=firm)
    print("\n  Firmness runs 0.65 (soaked) to 1.35 (bone dry); a fairway at 1.00 is "
          "the calibration\n  point, where the four clubs reproduce the 24 / 19 / 11 / 6 "
          "this model replaced.")
    print("\n  --fringe, --skip and --wind show the rest.")


if __name__ == "__main__":
    main()
