#!/usr/bin/env python3
"""Where a band opens, and what the Lab is told about a frequency.

    python3 tests/test_bands.py

The hop slider runs 1.8 to 30 MHz and spends most of that travel between
bands, and the Lab has five places to type a frequency. What is checked here
is the server half of the meter that now sits under each of them: every band
with its edges, a calling frequency to open on, and the activity that lets the
meter say "20 m - FT8" rather than only "20 m".

The calling frequency is where somebody who has just chosen a band should be
put: a real frequency people actually call on, preferring voice, then FT8,
then CW - not the middle of the band, which is a number nobody has ever tuned
to on purpose. 60 m has no band to be in the middle of: it is five channels,
and the answer there is the first channel's dial setting.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import bandplan  # noqa: E402
from elmer.app import app  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


print("\nwhere a band opens")
check("20 m opens on FT8, which is where the band is busiest",
      bandplan.calling_frequency("20 m"), (14.074, "FT8"))
check("15 m has a voice calling frequency, so it opens there",
      bandplan.calling_frequency("15 m"), (21.385, "SSB QRP calling"))
# Two voice calling frequencies on one band tie on kind, and the lower wins:
# 144.200 over 146.520. That is the whole rule; it is not a view about either.
check("2 m: two voice calling frequencies, the lower one",
      bandplan.calling_frequency("2 m")[0], 144.2)
check("60 m is channels, so it opens on channel 1's dial setting",
      bandplan.calling_frequency("60 m"), (5.3305, "Channel 1, dial setting"))
check("every band has somewhere to open",
      all(bandplan.calling_frequency(b["name"]) for b in bandplan.BANDS), True)
check("  and it is inside the band",
      all(b["low"] <= bandplan.calling_frequency(b["name"])[0] <= b["high"]
          for b in bandplan.BANDS), True)

print("\nwhat the Lab is told")
app.config["TESTING"] = True
reply = app.test_client().get("/api/bands")
check("the endpoint answers", reply.status_code, 200)
bands = reply.get_json()["bands"]
check("every band is there", len(bands), len(bandplan.BANDS))
twenty = next(b for b in bands if b["key"] == "20m")
check("a key the band plan's hash understands", twenty["key"], "20m")
check("edges", [twenty["low"], twenty["high"]], [14.0, 14.35])
check("where to open, and what that is", [twenty["calling"], twenty["calling_label"]],
      [14.074, "FT8"])
check("the activity, so the meter can name the spot",
      any(row[2] == "calling" and row[3] == "FT8" for row in twenty["activity"]), True)
sixty = next(b for b in bands if b["key"] == "60m")
check("60 m says it is channels", sixty["channelised"], True)
check("small enough to load once", len(reply.data) < 20000, True)

print("\none colour a band, everywhere")
from elmer import palette  # noqa: E402
names = [b["name"] for b in bandplan.BANDS] + [b["name"] for b in bandplan.PERSONAL_BANDS]
check("every band has a colour for the screen",
      all(palette.band_colour(n) for n in names), True)
check("  and an ink for paper",
      all(palette.band_colour(n, ink=True) for n in names), True)
check("no two bands share a colour",
      len({palette.band_colour(n) for n in names}), len(names))
check("20 m and 20m are the same band", palette.band_colour("20m"), palette.band_colour("20 m"))
check("a name that is not a band has no colour", palette.band_colour("13 m"), None)
pal = bandplan.band_palette()
check("the palette is in frequency order, 11 m after 12 m",
      [b["key"] for b in pal][8:11], ["12m", "11m", "10m"])
check("a CSS name that is an ident, even for 1.25 m",
      next(b["css"] for b in pal if b["key"] == "1.25m"), "band-1-25m")
check("the rgb triple matches the hex",
      next(b["rgb"] for b in pal if b["key"] == "20m"),
      ",".join(str(int(palette.band_colour("20m")[i:i + 2], 16)) for i in (1, 3, 5)))
check("the activity family has every kind, the same on every band",
      set(palette.KIND_COLOUR), {k for k, _ in bandplan.KINDS})
check("  and an ink for each", set(palette.KIND_INK), set(palette.KIND_COLOUR))
page = app.test_client().get("/bandplan").get_data(as_text=True)
check("the page head carries the tokens", "--band-20m: " + palette.band_colour("20m") + ";" in page, True)
check("  and the map for the scripts", "window.BAND_PALETTE" in page, True)
check("  and the activity colours for the band plan", '"cw": "#a6caff"' in page, True)
check("  and the attention colour", "--attention: " + palette.ATTENTION in page, True)
check("the licence family is earth, for none, GMRS and every class",
      {"none", "gmrs", "ham", "Technician", "General", "Extra"} <= set(palette.CLASS_COLOUR), True)
check("every band reads on the dark panel at 4.5:1 or better",
      all(palette.contrast(palette.band_colour(n)) >= 4.5 for n in names), True)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
