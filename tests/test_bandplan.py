#!/usr/bin/env python3
"""Checks for the part of the band plan that is law rather than convention.

    python3 tests/test_bandplan.py

Most of the band plan is a picture of custom, and being wrong about it is
embarrassing. 60 m is not: 47 CFR 97.303(h) permits five 2.8 kHz channels and
nothing at all between them, and a program that draws that as one continuous
bar is telling an operator they may transmit where they may not.

Two frequencies belong to each channel and they are not the same number - the
centre the rules name, and the dial setting 1.5 kHz below it that an operator
types into the radio. Both have to answer "yes".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import bandplan as B, rfexposure  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- five channels, and nothing between them --")
    check("there are five", len(B.CHANNELS_60M), 5)
    check("named by the rules' centre frequencies",
          [c["centre"] for c in B.CHANNELS_60M],
          [5.3320, 5.3480, 5.3585, 5.3730, 5.4050])
    check("dialled 1.5 kHz below that, for upper sideband",
          [c["dial"] for c in B.CHANNELS_60M],
          [5.3305, 5.3465, 5.3570, 5.3715, 5.4035])
    check("each 2.8 kHz wide from the dial setting up",
          all(abs((c["high"] - c["low"]) - 0.0029) < 1e-6 for c in B.CHANNELS_60M),
          True)

    print("\n-- what a General may actually do there --")
    check("one privilege per channel, not one for the band",
          len(B.privileges_for("60 m", "General")), 5)
    for channel in B.CHANNELS_60M:
        got = B.privilege_at(channel["dial"], "General")
        check(f'{channel["name"]}: the dial setting is permitted',
              got["allowed"], True)
        check("  and knows which channel it is",
              (got["channel"] or {})["name"], channel["name"])
        check("  centred where the rules say",
              B.privilege_at(channel["centre"], "General")["allowed"], True)
    check("and the gap between two channels is not",
          B.privilege_at(5.3400, "General")["allowed"], False)
    check("nor is one 100 Hz outside a channel",
          B.privilege_at(round(B.CHANNELS_60M[0]["high"] + 0.0001, 4),
                         "General")["allowed"], False)

    print("\n-- what may be sent on them --")
    got = B.privilege_at(5.3305, "General")
    check("USB, CW and data", got["emissions"], ["cw", "data", "phone"])
    check("  but not image", "image" in got["emissions"], False)
    check("100 W ERP, which is the limit that binds", got["max_erp"], 100)
    check("a Technician has no 60 m at all",
          B.privilege_at(5.3305, "Technician")["allowed"], False)

    print("\n-- and only one kind of voice --")
    # The emission categories elsewhere are coarse - CW, data, phone, image -
    # which is enough everywhere except here: 97.305(c) permits upper sideband
    # on 60 m and no other voice mode at all.
    check("upper sideband only", B.privilege_at(5.3305, "General")["phone_modes"],
          ["usb"])
    check("  which does not apply to 80 m phone",
          B.privilege_at(3.885, "General")["phone_modes"], None)
    check("an AM carrier on a channel is refused",
          bool(rfexposure.privilege_warnings(
              {"frequency_mhz": 5.3305, "pep_watts": 50, "mode": "am"},
              "General")), True)
    check("  and SSB on the same channel is not",
          rfexposure.privilege_warnings(
              {"frequency_mhz": 5.3305, "pep_watts": 50, "mode": "ssb"},
              "General"), [])
    check("  while AM on 80 m is somebody's ordinary evening",
          rfexposure.privilege_warnings(
              {"frequency_mhz": 3.885, "pep_watts": 50, "mode": "am"},
              "General"), [])

    print("\n-- the picture says the same thing as the rule --")
    activity = B.activity_for("60 m")
    check("five segments on the bar", len(activity), 5)
    check("  and the hatching between them",
          len(B.gaps_for("60 m", "General")), 6)   # both edges, four gaps

    print("\n-- and the exposure record will not bless a bad one --")
    between = rfexposure.privilege_warnings(
        {"frequency_mhz": 5.3400, "pep_watts": 100}, "General")
    check("off channel is refused", bool(between), True)
    check("  for the reason that is true of 60 m",
          "five 60 m channels" in between[0], True)
    check("on channel is not refused", rfexposure.privilege_warnings(
        {"frequency_mhz": 5.3305, "pep_watts": 100}, "General"), [])
    # A class with nothing on the band is told that, not told about channels.
    tech = rfexposure.privilege_warnings(
        {"frequency_mhz": 5.3305, "pep_watts": 100}, "Technician")
    check("a Technician is told the real reason",
          "may transmit on" in tech[0], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
