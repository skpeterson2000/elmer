#!/usr/bin/env python3
"""The narrator's words, pieced together from recorded snippets.

    python3 tests/test_voice.py

Numbers are reused: 377 is three, hundred, and, seventy, seven. The
address, the hole, the stroke and the card are lists of tokens, each the
stem of a sound file; every token composed here is in the vocabulary, so a
person who records the script has recorded everything the game can say -
except names, which are recorded per regular and said as "the player"
when they are not.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import golf, voice  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def in_vocabulary(tokens):
    return [t for t in tokens if t not in voice.VOCABULARY and not t.startswith("name-")]


def run():
    print("\n-- numbers, from the shelf --")
    check("377", voice.number(377), ["three", "hundred", "and", "seventy", "seven"])
    check("122", voice.number(122), ["one", "hundred", "and", "twenty", "two"])
    check("15", voice.number(15), ["fifteen"])
    check("40", voice.number(40), ["forty"])
    voice.set_shelf(["n-377", "three", "hundred"])
    check("a whole number on the shelf is said in one breath", voice.number(377), ["n-377"])
    check("  one that is not is still the pieces", voice.number(122), ["one", "hundred", "and", "twenty", "two"])
    voice.set_shelf(["n-300", "seventy", "seven"])
    check("  a whole hundred on the shelf carries the hundreds, then the rest, no 'and'", voice.number(377), ["n-300", "seventy", "seven"])
    check("  and a round hundred is the one file", voice.number(300), ["n-300"])
    voice.set_shelf(None)
    check("  and with no shelf known, the pieces", voice.number(377), ["three", "hundred", "and", "seventy", "seven"])
    check("200", voice.number(200), ["two", "hundred"])
    check("0", voice.number(0), ["zero"])
    check("the ninth", voice.ordinal(9), ["the-ninth"])
    check("  and no nineteenth", voice.ordinal(19), [])

    print("\n-- the address --")
    a = voice.address("Scott", "driver", 377, "tee")
    check("Scott addresses the ball, the driver in hand, 377 to go, from the tee", a,
          ["name-scott", "addresses-the-ball", "the-driver", "in-hand",
           "three", "hundred", "and", "seventy", "seven", "to-go", "from-the-tee"])
    check("  on the green, the putter and no yards", voice.address("Ann Lee", "putter", 0, "green"),
          ["name-ann-lee", "addresses-the-ball", "the-putter", "in-hand", "on-the-green"])
    check("  nobody named is the player", voice.address("", None, None, None), ["the-player", "addresses-the-ball"])

    print("\n-- the hole --")
    h = voice.hole(1, 4, 377, "with", 12, "pebble-beach")
    check("Pebble Beach, the first, par four, 377 yards, the breeze behind you, 12 miles an hour", h,
          ["pebble-beach", "the-first", "par", "four", "three", "hundred", "and", "seventy", "seven", "yards",
           "the-breeze-is-behind-you", "twelve", "miles-an-hour"])

    print("\n-- the stroke, in words --")
    check("a drive down the fairway", voice.shot({"kind": "fairway", "club": "driver", "carry": 255, "left": 122}),
          ["the-driver", "two", "hundred", "and", "fifty", "five", "yards", "fairway",
           "one", "hundred", "and", "twenty", "two", "to-go"])
    check("a foul ball into the sand", voice.shot({"kind": "sand", "club": "driver", "carry": 0}),
          ["the-driver", "a-foul-ball", "into-the-sand"])
    check("on the green, nine feet", voice.shot({"kind": "green", "club": "iron", "carry": 122, "feet": 9}),
          ["the-iron", "one", "hundred", "and", "twenty", "two", "yards", "on-the-green", "nine", "feet"])
    check("holed, three for a birdie", voice.shot({"kind": "holed", "holed": True, "strokes": 3, "score": "birdie"}),
          ["putt-holed", "three", "for-a-birdie"])
    check("an ace", voice.shot({"kind": "holed", "holed": True, "ace": True, "club": "iron", "carry": 150,
                                "strokes": 1, "score": "eagle"}),
          ["the-iron", "one", "hundred", "and", "fifty", "yards", "in-the-hole", "an-ace", "one", "for-an-eagle"])
    check("picked up, a triple", voice.shot({"kind": "rough", "club": "wedge", "carry": 0, "picked_up": True,
                                             "score": "triple bogey"}),
          ["the-wedge", "a-foul-ball", "short-and-into-the-rough", "picked-up", "for-a-triple-bogey"])

    print("\n-- the calls --")
    check("every call the rules make has a file", [c for cs in golf.CALLS.values() for c in cs if not voice.call(c)], [])
    check("  and every shot worth making", [c for cs in golf.FLAIR_CALLS.values() for c in cs if not voice.call(c)], [])
    check("holed it from the fairway, in words",
          voice.shot({"kind": "holed", "holed": True, "flair": "holed-out", "club": "iron", "carry": 100, "strokes": 3, "score": "birdie"}),
          ["the-iron", "one", "hundred", "yards", "holed-it-from-the-fairway", "three", "for-a-birdie"])
    check("  and the ace", voice.call("A hole in one!"), ["call-ace"])

    print("\n-- the card --")
    check("that's the hole, Scott a bogey, Ann par, on to the next",
          voice.card([{"name": "Scott", "score": "bogey"}, {"name": "Ann", "score": "par"}]),
          ["thats-the-hole", "name-scott", "for-a-bogey", "name-ann", "for-par", "on-to-the-next"])

    print("\n-- everything composed is on the script --")
    lines = [voice.address("x", c, n, lie) for c in ("driver", "wood", "iron", "wedge", "putter")
             for n in (0, 7, 15, 99, 100, 377, 999) for lie in voice.LIE_TOKENS]
    lines += [voice.hole(n, p, y, w, 17, c) for n in range(1, 19) for p in (3, 4, 5) for y in (150, 377, 555)
              for w in voice.WIND_TOKENS for c in voice.COURSE_TOKENS]
    lines += [voice.shot({"kind": k, "club": "iron", "carry": 42, "left": 8, "feet": 12, "holed": k == "holed",
                          "strokes": 4, "score": s, "picked_up": k == "rough"})
              for k in ("fairway", "green", "long", "sand", "water", "rough", "missed", "holed")
              for s in voice.SCORE_TOKENS]
    stray = sorted({t for line in lines for t in in_vocabulary(line)})
    check("no token outside the vocabulary", stray, [])
    check("the script has a line for every snippet", len(voice.script_lines()), len(voice.VOCABULARY))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
