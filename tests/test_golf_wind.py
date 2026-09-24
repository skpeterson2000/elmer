#!/usr/bin/env python3
"""The wind by the clock, and what it does to a ball.

    python3 tests/test_golf_wind.py

The wind used to be one of four buckets - with, into, across, swirling -
and three constants read it. It is a bearing now, an hour of the clock with
twelve straight down the hole, and the head, cross and roll components are
cosine and sine of the same angle. A caddie says "out of eight o'clock"
because that is one fact with both components in it; the game now means the
same thing by it.

The properties worth holding: at the four cardinal hours the new model
reproduces the four old numbers exactly, so nothing about a dead headwind
or a pure crosswind changed; a quartering wind is most of a headwind and a
bit of a crosswind rather than having to be called one or the other; the
hour a hole plays is inside the arc its card asked for, and is the same
every round; drift follows how long the ball is actually in the air, so a
laid-up wedge holds its line where a driver is moved several yards; and the
narrator is given the same hour the ball is flown with, so the two cannot
disagree.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import golf, voice  # noqa: E402

FAILS = []
ROOT = Path(__file__).resolve().parents[1]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def near(label, got, want, slack=0.02):
    ok = abs(got - want) <= slack
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got:.3f}"
          + ("" if ok else f"  (wanted {want:.3f})"))
    if not ok:
        FAILS.append(label)


print("\nthe four cardinal hours are the four numbers this replaced")
# What WIND_EFFECT and WIND_ROLL used to say, before the wind was a bearing.
near("out of twelve costs 0.8 yards a mile an hour", golf.wind_carry(12), -0.8)
near("  out of six gives 0.6", golf.wind_carry(6), 0.6)
near("  a crosswind off the right costs 0.2", golf.wind_carry(3), -0.2)
near("  and off the left, the same", golf.wind_carry(9), -0.2)
near("roll into it is 0.70 of normal", golf.wind_roll(12), 0.70)
near("  downwind, 1.25", golf.wind_roll(6), 1.25)
near("  across, untouched", golf.wind_roll(3), 1.0)

print("\na quartering wind is most of a headwind and a bit of a crosswind")
tail, cross = golf.wind_parts(11)
near("out of eleven is 0.87 headwind", tail, -0.866)
near("  and half a crosswind, off the left", cross, -0.5)
check("  which costs carry, but less than a dead headwind",
      -0.8 < golf.wind_carry(11) < -0.7, True)
check("  and eleven o'clock pushes the ball right, as a left wind does",
      golf.wind_drift(11, 20, "driver") > 0, True)
check("  where one o'clock pushes it left",
      golf.wind_drift(1, 20, "driver") < 0, True)

print("\n  the head and tail of it are symmetric about the twelve-six line")
near("eleven and one cost the same carry",
     golf.wind_carry(11), golf.wind_carry(1))
near("  and drift the same, opposite ways",
     golf.wind_drift(11, 20, "driver"), -golf.wind_drift(1, 20, "driver"))

print("\nno wind at all is what a stinger earns")
check("no hour, no parts", golf.wind_parts(None), (0.0, 0.0))
check("  no carry", golf.wind_carry(None), 0.0)
check("  no roll either way", golf.wind_roll(None), 1.0)
check("  and no drift", golf.wind_drift(None, 30, "driver"), 0.0)


print("\ndrift follows how long the ball is up there")
MPH = 20
driver = golf.wind_drift(9, MPH, "driver", 250, 250)
wedge = golf.wind_drift(9, MPH, "sand-wedge", 100, 100)
laid = golf.wind_drift(9, MPH, "sand-wedge", 40, 100)
check("a full driver in twenty across moves several yards",
      4 <= driver <= 8, True)
# A full wedge is still up there a good while - three and a half seconds
# against a driver's six - so it is moved appreciably, just less. The one
# that holds its line is the wedge laid up short, which is up half as long.
check("  a full wedge moves appreciably less", wedge < driver * 0.7, True)
check("  and one laid up forty yards holds its line by comparison",
      laid < driver / 2, True)
check("  which is the surprise this removes: they are not all the same",
      len({round(driver), round(wedge), round(laid)}), 3)
near("  a driver is about what the flat figure used to give for everything",
     driver, golf.WIND_DRIFT_PER_SECOND * 20 * golf.FLIGHT_SECONDS["driver"], 0.01)

print("\n  and a stinger is punched under it")
straight = golf.wind_drift(9, MPH, "7-iron", 180, 180)
punched = golf.wind_drift(9, MPH, "7-iron", 180, 180, flair="stinger")
check("a punched iron drifts less than a struck one", punched < straight, True)
near("  by the hang it gives up", punched / straight, golf.STINGER_HANG)

print("\n  a ball that is not in the air does not drift")
check("the putter has no flight", golf.flight_seconds("putter"), 0.0)
check("  so no wind moves it", golf.wind_drift(9, 40, "putter"), 0.0)


print("\nthe hour is inside the arc the card asked for, and holds still")
course = json.loads((ROOT / "data" / "golf" / "pebble-beach.json").read_text(encoding="utf-8"))
game = golf.Golf(["a"], course, seed=1, seconds=30)
hours = {}
for h in course["holes"]:
    hour = game.wind_clock(h)
    hours[h["n"]] = hour
    kind = h["wind"]
    arc = golf.WIND_ARC.get(kind if kind != "across" else f"across-{game.wind_from(h)}")
    if arc and hour not in arc:
        check(f"  hole {h['n']} ({kind}) is inside its arc", hour, arc)
check("every hole has an hour", sorted(hours) == list(range(1, 19)), True)
check("  each one inside the arc its card asked for",
      all(hours[h["n"]] in golf.WIND_ARC.get(
          h["wind"] if h["wind"] != "across" else f"across-{game.wind_from(h)}", (hours[h["n"]],))
          for h in course["holes"]), True)

again = golf.Golf(["a"], course, seed=99, seconds=30)
check("  the same hole is the same wind in a different round",
      {h["n"]: again.wind_clock(h) for h in course["holes"]}, hours)
check("  but the eighteen are not all quartering the same way",
      len(set(hours.values())) >= 4, True)

print("\n  a swirling hole is never given an hour")
swirl = {"n": 12, "wind": "swirling", "yards": 200, "par": 3}
check("no bearing for what has none", game.wind_clock(swirl, "swirling"), None)
check("  but the shot it is drawn as does have one",
      game.wind_clock(swirl, "into"), 12)


print("\nthe narrator is handed the hour the ball is flown with")
voice.set_shelf(sorted(p.stem for p in
                       (ROOT / "elmer" / "static" / "golf" / "voice").glob("*.mp3")))
said = voice.wind("with", 14, hour=6)
check("it says the clock when the clip is on the shelf",
      said, ["the-wind-is", "fourteen", "miles-an-hour", "out-of-six-oclock"])
check("  every hour of the clock is recorded",
      sorted(t for t in voice.WIND_CLOCK.values() if t in voice._shelf) ==
      sorted(voice.WIND_CLOCK.values()), True)
check("  and every one is in the vocabulary to be recorded from",
      all(t in voice.VOCABULARY for t in voice.WIND_CLOCK.values()), True)

print("\n  and falls back the way the rest of the shelf does")
voice.set_shelf(["the-wind-is", "in-your-face", "miles-an-hour", "fourteen"])
check("no clock recorded, so the older phrase",
      voice.wind("into", 14, hour=12),
      ["the-wind-is", "fourteen", "miles-an-hour", "in-your-face"])
voice.set_shelf(["into-the-breeze"])
check("  nor that, so the oldest", voice.wind("into", None, hour=12),
      ["into-the-breeze"])

print("\n  a swirling hole is not given a bearing even when one is offered")
voice.set_shelf(sorted(p.stem for p in
                       (ROOT / "elmer" / "static" / "golf" / "voice").glob("*.mp3")))
check("it refuses the hour", "out-of-three-oclock" in voice.wind("swirling", 14, hour=3), False)

print("\n  twelve and zero are the same o'clock")
check("hour 12", voice.clock(12), "out-of-twelve-oclock")
check("  hour 0 is midnight, which is twelve", voice.clock(0), "out-of-twelve-oclock")
check("  and no hour says nothing", voice.clock(None), None)


print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
