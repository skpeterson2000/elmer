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
    check("a callsign is a callsign", [voice.looks_like_callsign(n) for n in ("KC9SP", "W1AW", "VE3ABC", "Scott", "Ann Lee", "4X4")],
          [True, True, True, False, False, False])
    voice.set_shelf(["phon-k", "phon-c", "nine", "phon-s", "phon-p", "name-scott"])
    check("a callsign with no name file is spelled phonetically", voice.name_tokens("KC9SP"), ["phon-k", "phon-c", "nine", "phon-s", "phon-p"])
    check("  a name with a file is the file", voice.name_tokens("Scott"), ["name-scott"])
    check("  a callsign with a file is the file too", (voice.set_shelf(["name-kc9sp"]), voice.name_tokens("KC9SP"))[1], ["name-kc9sp"])
    voice.set_shelf(None)
    check("  and with no shelf known, the name file", voice.name_tokens("KC9SP"), ["name-kc9sp"])
    voice.set_shelf(["player-2-is-away", "player-1-has-honors", "the-driver", "in-hand"])
    check("the slot on the sheet is called when it is recorded", voice.address("Scott", "driver", 377, "tee", slot=2)[:1], ["player-2-is-away"])
    check("  first off the tee, the honors", voice.address("Scott", "driver", 377, "tee", slot=1, honors=True)[:1], ["player-1-has-honors"])
    check("  a slot with no file falls back to the name", voice.address("Scott", "driver", 377, "tee", slot=3)[:2], ["name-scott", "addresses-the-ball"])
    voice.set_shelf(["hole-pebble-beach-1", "the-breeze-is-behind-you", "twelve", "miles-an-hour", "the-first", "par"])
    check("a hole recorded whole is read whole at the tee, then the wind",
          voice.hole(1, 4, 377, "with", 12, "pebble-beach"), ["hole-pebble-beach-1", "the-breeze-is-behind-you", "twelve", "miles-an-hour"])
    check("  and the second, with no such file, from the pieces", voice.hole(2, 5, 502, None, None, "pebble-beach")[:2], ["pebble-beach", "hole"] if False else voice.hole(2, 5, 502, None, None, "pebble-beach")[:2])
    voice.set_shelf(["hole-pebble-beach-1", "hole-pebble-beach-1-tee-1", "hole-pebble-beach-1-green-1", "hole-pebble-beach-1-green-2", "the-putter", "in-hand", "on-the-green"])
    check("a hole's colour is not in the read - it comes a line at a time, to each player's address",
          voice.hole(1, 4, 377, None, None, "pebble-beach"), ["hole-pebble-beach-1"])
    voice.set_shelf(["hole-pebble-beach-1", "hole-pebble-beach-1-read-2"])
    reads = {voice.hole(1, 4, 377, None, None, "pebble-beach")[0] for _ in range(40)}
    check("  a hole with two reads is read either way, over an evening", reads, {"hole-pebble-beach-1", "hole-pebble-beach-1-read-2"})
    voice.set_shelf(["hole-pebble-beach-1", "hole-pebble-beach-1-tee-1", "hole-pebble-beach-1-green-1", "hole-pebble-beach-1-green-2", "the-putter", "in-hand", "on-the-green"])
    check("  and the green's colour comes with the first putt, when it is asked for",
          voice.address("Scott", "putter", 0, "green", green_notes=voice.notes("pebble-beach", 1, "green"))[-2:],
          ["hole-pebble-beach-1-green-1", "hole-pebble-beach-1-green-2"])
    check("  but not with every putt", voice.address("Scott", "putter", 0, "green")[-1], "on-the-green")
    voice.set_shelf(["hole-pebble-beach-1-sand-1", "the-wedge", "in-hand", "to-go", "from-the-sand"])
    check("  the sand's colour comes after the lie, when asked for",
          voice.address("Scott", "wedge", 40, "sand", green_notes=voice.notes("pebble-beach", 1, "sand"))[-2:], ["from-the-sand", "hole-pebble-beach-1-sand-1"])
    voice.set_shelf(["hole", "one", "is", "par", "four", "rough", "green", "bunker", "the-driver", "two", "yards"])
    check("with 'the first' unrecorded, the pieces say it: hole, one, is", voice.hole(1, 4, 377)[:5], ["hole", "one", "is", "par", "four"])
    check("  and a stroke into the rough says 'rough' when the phrase is not there",
          voice.shot({"kind": "rough", "club": "driver", "carry": 200})[-1], "rough")
    check("  the green likewise", "green" in voice.shot({"kind": "green", "club": "driver", "carry": 200, "feet": 12}), True)
    voice.set_shelf(["the-first", "hole", "one", "is", "into-the-rough", "rough"])
    check("  the phrase wins when it is recorded", (voice.hole(1, 4, 377)[0], voice.shot({"kind": "rough", "club": "driver", "carry": 200})[-1]),
          ("the-first", "into-the-rough"))
    voice.set_shelf(None)
    check("200", voice.number(200), ["two", "hundred"])
    check("0", voice.number(0), ["zero"])
    check("the ninth", voice.ordinal(9), ["the-ninth"])
    check("  and no nineteenth", voice.ordinal(19), [])

    print("\n-- the address --")
    a = voice.address("Scott", "driver", 377, "tee")
    check("Scott addresses the ball, the driver in hand, 377 yards to go, from the tee - the shelf unknown, the fuller piece", a,
          ["name-scott", "addresses-the-ball", "the-driver", "in-hand",
           "three", "hundred", "and", "seventy", "seven", "yards-to-go", "from-the-tee"])
    check("  inside a hundred it is 'to go'", voice.address("Scott", "wedge", 80, "fairway")[-2:], ["to-go", "from-the-fairway"])
    voice.set_shelf(["to-go", "from-the-tee", "the-driver", "in-hand", "addresses-the-ball", "name-scott",
                     "three", "hundred", "and", "seventy", "seven"])
    check("  and 'to go' throughout when 'yards to go' is not recorded", voice.address("Scott", "driver", 377, "tee")[-2:], ["to-go", "from-the-tee"])
    voice.set_shelf(None)
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
           "one", "hundred", "and", "twenty", "two", "yards-to-go"])
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

    print("\n-- the colour, a line at a time, one to each player --")
    from elmer.party import _lie_notes
    shelf_was = voice._shelf
    voice.set_shelf({"hole-pebble-beach-2", "hole-pebble-beach-2-tee-1", "hole-pebble-beach-2-tee-2",
                     "hole-pebble-beach-2-tee-3", "hole-pebble-beach-2-fairway-1", "hole-pebble-beach-2-sand-1",
                     "hole-pebble-beach-2-green-1"})
    check("the hole's read carries no tee lines of its own",
          [t for t in voice.hole(2, 5, 502, "with", 10, "pebble-beach") if "-tee-" in t], [])

    class G:                                   # a round's history, as the notes read it
        history = []
        players = ["a", "b", "c", "d"]
    d = {"course": "pebble-beach", "hole": 2}
    tee = {"lie": "tee"}
    check("the first player on the tee gets the first line", _lie_notes(G, d, tee, "a"), ["hole-pebble-beach-2-tee-1"])
    G.history = [{"hole": 2, "shots": {"a": {"from": "tee", "kind": "fairway"}}}]
    check("  the second the second", _lie_notes(G, d, tee, "b"), ["hole-pebble-beach-2-tee-2"])
    G.history.append({"hole": 2, "shots": {"b": {"from": "tee", "kind": "rough"}}})
    check("  the third the third", _lie_notes(G, d, tee, "c"), ["hole-pebble-beach-2-tee-3"])
    G.history.append({"hole": 2, "shots": {"c": {"from": "tee", "kind": "sand"}}})
    check("  and a fourth, with three lines, hears the hole without one", _lie_notes(G, d, tee, "d"), None)
    check("the first from the fairway gets the fairway's line", _lie_notes(G, d, {"lie": "fairway"}, "a"),
          ["hole-pebble-beach-2-fairway-1"])
    G.history.append({"hole": 2, "shots": {"a": {"from": "fairway", "kind": "fairway"}}})
    check("  a second stroke from it, nothing more", _lie_notes(G, d, {"lie": "fairway"}, "a"), None)
    check("  and the next player from the fairway, nothing - there is one line",
          _lie_notes(G, d, {"lie": "fairway"}, "b"), None)
    check("the sand's line is the player in the sand's", _lie_notes(G, d, {"lie": "sand"}, "c"), ["hole-pebble-beach-2-sand-1"])
    G.history.append({"hole": 2, "shots": {"a": {"from": "fairway", "putt": False, "kind": "green"}}})
    G.history.append({"hole": 2, "shots": {"a": {"putt": True, "kind": "green"}}})
    check("the first putt of the hole took the green's line; the next player's does not",
          _lie_notes(G, d, {"lie": "green"}, "b"), None)
    check("  another hole starts the count again", _lie_notes(G, {"course": "pebble-beach", "hole": 3}, tee, "b"), None)

    print("\n-- alone, the hole is told to the one player, two lines a stroke --")
    class Solo:
        history = []
        players = ["a"]
    check("the first stroke from the tee gets the first two lines", _lie_notes(Solo, d, tee, "a"),
          ["hole-pebble-beach-2-tee-1", "hole-pebble-beach-2-tee-2"])
    Solo.history = [{"hole": 2, "shots": {"a": {"from": "tee", "kind": "fairway"}}}]
    check("  the fairway's one line on the first stroke from there", _lie_notes(Solo, d, {"lie": "fairway"}, "a"),
          ["hole-pebble-beach-2-fairway-1"])
    Solo.history.append({"hole": 2, "shots": {"a": {"from": "fairway", "kind": "rough"}}})
    check("  and nothing more from the fairway once it is used up", _lie_notes(Solo, d, {"lie": "fairway"}, "a"), None)
    Solo.history = [{"hole": 2, "shots": {"a": {"from": "tee", "kind": "water"}}}]
    check("  a second stroke from the tee - after a splash - gets the third line", _lie_notes(Solo, d, tee, "a"),
          ["hole-pebble-beach-2-tee-3"])
    class Pair(Solo):
        history = []
        players = ["a", "b"]
    check("a pair is told the hole the same way", _lie_notes(Pair, d, tee, "b"),
          ["hole-pebble-beach-2-tee-1", "hole-pebble-beach-2-tee-2"])
    voice.set_shelf(shelf_was)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
