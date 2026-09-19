#!/usr/bin/env python3
"""What the card draws is what the ball obeys.

    python3 tests/test_golf_card.py

Reported from a round on the first hole at Pebble Beach: a drive called
"Nice shot!" and put on the fairway, drawn sitting in a bunker; and a ball
called into the bunker, drawn far out in the rough. Two models of the same
hole, disagreeing.

They disagreed because they were two models. The map drew a hazard where the
card says it is, across the hole as well as along it. The rules asked only
two questions - is the ball's yardage inside the hazard's band, and is the
ball on the same side of the line - so every hazard on the left caught every
ball to the left of the line however wide of it, and no hazard on the left
could catch a ball that was still between the fairway's edges, however
exactly it was drawn on top of one.

There is one statement of a hazard's shape now, golf.hazard_spans, and the
map draws from it and the rules test against it. This holds that down: over
a few hundred shots on real holes, a ball called sand is inside a bunker and
a ball called fairway is inside none.

It also pins the reading of a side hazard's offset, which is the other half
of the same bug. The offset is measured from the fairway's edge. Read as
yards from the line of play instead, fifty-three of the ninety side hazards
on the shipped courses sit inside their own fairway, which is not how a golf
course is built - and the card drew them there.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import golf  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def hazard_at(h, at, off, kinds):
    """What the card draws under a ball at these yards, of these kinds."""
    for hz in h.get("hazards", []):
        if hz["kind"] not in kinds:
            continue
        if not (hz["from"] <= at <= hz["to"]):
            continue
        if golf.hazard_covers(h, hz, off):
            return hz
    return None


def main():
    print("\n-- a side hazard is measured from the fairway's edge --")
    hole = {"yards": 400, "par": 4, "green": 30, "width": 18, "hazards": []}
    check("nought is the edge itself",
          golf.hazard_off(hole, {"kind": "bunker", "side": "right", "off": 0}), 18.0)
    check("  twelve is twelve into the rough",
          golf.hazard_off(hole, {"kind": "bunker", "side": "right", "off": 12}), 30.0)
    check("  and the sign follows the side",
          golf.hazard_off(hole, {"kind": "bunker", "side": "left", "off": -12}), -30.0)
    # Read the other way, most of the shipped hazards would be in the fairway.
    inside = sum(1 for c in golf.courses().values() for h in c["holes"]
                 for hz in h.get("hazards") or []
                 if hz.get("side") in ("left", "right") and hz.get("off") is not None
                 and abs(float(hz["off"])) < golf.fairway_half(h))
    check("  which is why: most stated offsets are smaller than the fairway's half-width",
          inside > 0, True)
    check("  and none of them lands inside the fairway once read from the edge",
          [1 for c in golf.courses().values() for h in c["holes"]
           for hz in h.get("hazards") or []
           if hz.get("side") in ("left", "right")
           and abs(golf.hazard_off(h, hz)) < golf.fairway_half(h)], [])

    print("\n-- the rules and the card agree, shot after shot --")
    disagreed = []
    played = 0
    for course_id in golf.courses():
        course = golf.course(course_id)
        for hole_no in (1, 2, 3, 4, 5, 6):
            for seed in range(12):
                game = golf.Golf(["a"], course, holes=[hole_no], seed=seed)
                for _ in range(6):
                    h = game.hole()
                    if h is None or game.balls["a"].done():
                        break
                    row = game.play_one("a", {"correct": seed % 3 != 0})
                    shot = row["shots"]["a"]
                    ball = game.balls["a"]
                    played += 1
                    if ball.lie == "sand":
                        if hazard_at(h, ball.at, ball.off, ("bunker",)) is None:
                            disagreed.append(("called sand, drawn out of every bunker",
                                              course_id, hole_no, shot["kind"], ball.at, ball.off))
                    elif ball.lie == "fairway":
                        drawn = hazard_at(h, ball.at, ball.off, ("bunker", "water"))
                        if drawn is not None:
                            disagreed.append(("called fairway, drawn in " + (drawn["name"] or drawn["kind"]),
                                              course_id, hole_no, shot["kind"], ball.at, ball.off))
    check("shots played", played > 400, True)
    check("  and not one of them is drawn somewhere it was not called",
          disagreed[:3], [])

    print("\n-- the hole the round was reported on --")
    pb = golf.course("pebble-beach")
    first = pb["holes"][0]
    check("the first at Pebble has its bunkers off the fairway, not in it",
          [round(c) for hz in first["hazards"] for c, _ in golf.hazard_spans(first, hz)],
          [-31, -30, -29, 28])
    kinds = {}
    for seed in range(200):
        game = golf.Golf(["a"], pb, holes=[1], seed=seed)
        kind = game.play_one("a", {"correct": True, "club": "driver"})["shots"]["a"]["kind"]
        kinds[kind] = kinds.get(kind, 0) + 1
    # A driven ball that answers the question right belongs on the fairway
    # most of the time. It used to find sand a third of the time, because
    # three bunkers were drawn across the left half of the fairway.
    check("  and a good drive finds it, rather than the sand",
          (kinds.get("fairway", 0) / 200 > 0.75, kinds.get("sand", 0) / 200 < 0.1), (True, True))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
