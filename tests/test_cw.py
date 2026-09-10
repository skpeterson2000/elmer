#!/usr/bin/env python3
"""Checks for the Morse tables and the encoder behind the CW page.

    python3 tests/test_cw.py

What matters here is not the timing arithmetic - PARIS is arithmetic and it
either is or is not - but the things that are audibly wrong if they slip: a
prosign sent as two letters, a character that encodes to somebody else's code,
a chart that quietly omits half the alphabet.

Nothing here touches the network or the browser.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import cw  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def codes(text):
    """Flat list of (character, code) for everything encode() produces."""
    return [(s["char"], s["code"]) for word in cw.encode(text) for s in word]


def main():
    print("\n-- the code is a code --")
    # Two characters sharing one code would make the decoder a coin toss.
    check("no two characters share a code",
          len(set(cw.MORSE.values())), len(cw.MORSE))
    check("every code is dits and dahs and nothing else",
          {c for code in cw.MORSE.values() for c in code}, {".", "-"})
    check("the Koch order is the alphabet and then some, with no repeats",
          len(cw.KOCH_ORDER), len(set(cw.KOCH_ORDER)))
    check("  and every character in it can actually be sent",
          [c for c in cw.KOCH_ORDER if c not in cw.MORSE], [])

    print("\n-- a prosign is one sound, not two letters --")
    # This is the whole point of the brackets. AR sent as A R has a three-dit
    # gap in the middle of it and is a different thing to hear.
    check("<AR> is one symbol", codes("<AR>"), [("AR", ".-.-.")])
    check("  and it is not the letters A R",
          codes("AR"), [("A", ".-"), ("R", ".-.")])
    # The elements are the same either way - ".-" + ".-." is ".-.-." - and the
    # difference is entirely the gap: one symbol runs them together, two
    # symbols put three dits between them. That is why sending a prosign as its
    # letters is such an easy mistake to make and such an obvious one to hear.
    check("  the elements are identical, which is the trap",
          cw.PROSIGNS["AR"][0], cw.MORSE["A"] + cw.MORSE["R"])
    check("  so what separates them is the count of symbols, not the code",
          (len(codes("<AR>")), len(codes("AR"))), (1, 2))
    check("a prosign is found with punctuation after it",
          codes("<AR>;"), [("AR", ".-.-.")])
    check("  and in the middle of a line",
          codes("HW? <BT> OK")[3], ("BT", "-...-"))
    check("brackets that are not a prosign are just letters",
          codes("<XY>"), [("X", "-..-"), ("Y", "-.--")])
    check("a bare word is never guessed at as a prosign",
          codes("AS"), [("A", ".-"), ("S", "...")])

    print("\n-- what is sent, and what you write down --")
    check("the angle brackets are not something you can hear",
          cw.plain("W1AW DE K1ABC <BT> HW? <AR>"),
          "W1AW DE K1ABC BT HW? AR")
    check("  and plain text passes through unharmed",
          cw.plain("cq cq de w1aw k"), "CQ CQ DE W1AW K")

    print("\n-- generated material means what it says --")
    # Prosign practice used to send A then R and call it AR, which taught the
    # wrong sound to anybody who believed it.
    prosigns = cw.practice("prosigns", 4, seed=7)[0]
    sent = codes(prosigns)
    check("prosign practice sends prosigns, not their letters",
          all(char in cw.PROSIGNS for char, _ in sent), True)
    check("  one symbol each", len(sent), len(prosigns.split()))
    for template in cw.QSO_TEMPLATES:
        filled = template.format(me="K1ABC", you="W1AW", rst="599", name="JIM",
                                 qth="MN", wx="SUNNY", watts=100)
        for name in ("AR", "SK", "BT"):
            if f"<{name}>" in template:
                check(f"a QSO's {name} is the prosign",
                      (name, cw.PROSIGNS[name][0]) in codes(filled), True)

    print("\n-- the chart shows the whole code --")
    sections = cw.chart()
    shown = {item["char"] for s in sections for item in s["items"]}
    check("every letter and digit is on it",
          [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" if c not in shown],
          [])
    check("every prosign is on it",
          [p for p in cw.PROSIGNS if p not in shown], [])
    check("and every cell has a code to draw",
          [i["char"] for s in sections for i in s["items"] if not i["code"]], [])
    check("the prosigns get the room their meanings need",
          [s["title"] for s in sections if s.get("wide")], ["Prosigns"])

    print("\n-- timing --")
    at20 = cw.timing(20)
    check("a dit is 1200/wpm milliseconds", at20["dit"], 60.0)
    check("  and a dah is three of them", at20["dah"], 180.0)
    check("full speed is not Farnsworth", at20["farnsworth"], False)
    slow = cw.timing(20, 10)
    check("Farnsworth stretches the gaps", slow["char_gap"] > at20["char_gap"], True)
    check("  and never the characters", slow["dit"], at20["dit"])
    check("  and asking for faster spacing than the characters does nothing",
          cw.timing(20, 30)["farnsworth"], False)

    print("\n-- the Q signals, as three letters and not as one --")
    chart = {section["title"]: section for section in cw.chart()}
    check("they are on the chart", "Q signals" in chart, True)
    q = chart["Q signals"]
    check("all of them", len(q["items"]), len(cw.Q_SIGNALS))
    check("  laid out with the code under the name", q.get("stacked"), True)
    qcode = {item["char"]: item["code"] for item in q["items"]}
    check("QRM is Q, R and M with the gaps between them",
          qcode["QRM"], "--.- .-. --")
    check("  which is not what a prosign looks like",
          " " in cw.PROSIGNS["AR"][0], False)
    # The distinction the whole section is about: run together, --.- .-. --
    # would be a single symbol and a different sound entirely.
    check("a Q signal has two gaps in it, one between each pair",
          qcode["QTH"].count(" "), 2)
    check("every one of them carries its meaning",
          all(item["meaning"] for item in q["items"]), True)
    check("  and it is the one the module already had",
          q["items"][0]["meaning"],
          cw.Q_SIGNALS[q["items"][0]["char"]])
    check("the section says how to ask one rather than state it",
          "QRL?" in q["note"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
