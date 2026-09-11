#!/usr/bin/env python3
"""Checks for the coordinator directory and the plans that can be read.

    python3 tests/test_regional.py

Forty-nine organisations cover the fifty states and not one per state: SERA
alone covers eight, T-MARC five, NESMC four, and California is carved up five
ways. Naming somebody's coordinator and parsing their plan are two different
jobs and only the first is cheap - there is no registry, no API and no common
format between them - so what is tested here is that every state gets a real
answer either way.

Nothing here touches the network. The parsers are exercised against saved
markup rather than a live site, because a test that fails when somebody else's
web server is down is not testing this program.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import regional as R  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- everybody is covered by somebody --")
    covered = {s for c in R.COORDINATORS for s in c["states"]}
    check("every state and territory has a coordinator listed",
          sorted(set(R.US_STATES.values()) - covered), [])
    check("and every coordinator covers somewhere real",
          sorted({s for s in covered if s not in R.US_STATES.values()}), [])
    check("each carries a name and a link to follow",
          [c["short"] for c in R.COORDINATORS
           if not (c.get("name") and c.get("url"))], [])
    check("the shorthands are unique",
          len({c["short"] for c in R.COORDINATORS}), len(R.COORDINATORS))

    print("\n-- states with more than one, and organisations with more than one state --")
    check("SERA covers eight states", len(R.for_state("GA")[0]["states"]), 8)
    check("California has several bodies", len(R.for_state("CA")) > 1, True)
    check("  and the most specific comes first",
          len(R.for_state("VA")[0]["states"]) <= len(R.for_state("VA")[-1]["states"]),
          True)
    check("a state nobody covers returns nothing rather than raising",
          R.for_state("ZZ"), [])
    check("  and so does no state at all", R.for_state(""), [])

    print("\n-- finding the state from a QTH --")
    # The reverse-geocoded place name carries it and it was being discarded.
    check("a Minnesota QTH resolves to MN",
          R.state_of("Pequot Lakes, Crow Wing County, Minnesota, 56472, United States"),
          "MN")
    check("a Texas one to TX",
          R.state_of("Austin, Travis County, Texas, 78701, United States"), "TX")
    # The trap: counties are named after states.
    check("Washington County, Minnesota is not Washington the state",
          R.state_of("Stillwater, Washington County, Minnesota, United States"), "MN")
    check("West Virginia is not Virginia",
          R.state_of("Charleston, Kanawha County, West Virginia, United States"), "WV")
    check("a place dict works as well as a string",
          R.state_of({"name": "Houston, Harris County, Texas, United States"}), "TX")
    check("and somewhere abroad resolves to nothing",
          R.state_of("Cardiff, Wales, United Kingdom"), None)
    check("  as does an empty place", R.state_of({}), None)

    print("\n-- which plans can actually be read --")
    readable = [c["short"] for c in R.COORDINATORS if c.get("fetch")]
    check("the ones with a parser are wired to a real function",
          [f for f in (c["fetch"] for c in R.COORDINATORS if c.get("fetch"))
           if f not in R.FETCHERS], [])
    check("Minnesota and Texas are readable", sorted(readable), ["MRC", "TXVHFFM"])
    check("a readable state finds its parser", R.readable("TX")["short"], "TXVHFFM")
    check("  and one without a parser finds none, rather than the wrong one",
          R.readable("GA"), None)
    check("but that state still has a coordinator to name",
          R.for_state("GA")[0]["short"], "SERA")
    # Where a coordinator cannot be parsed, the entry says why rather than
    # leaving somebody to wonder whether it is broken.
    for short in ("SERA", "CCARC"):
        entry = next(c for c in R.COORDINATORS if c["short"] == short)
        check(f"  {short} explains why its plan is not read here",
              bool(entry.get("note")), True)

    print("\n-- reading a plan out of saved markup --")
    # The Texas rows are the shape the existing parser already reads, which is
    # why that coordinator was the cheap one to add.
    page = "\n".join([
        "6 Meter Band Plan",
        "50.000 - 50.100 CW (50.06 - 50.08 Beacon sub-band)",
        "50.100 - 50.300 Weak Signal SSB (50.125, 50.200 Calling Freqs.)",
        "148 MHz Band Plan",
        "144.100 - 144.275 Weak Signal SSB (144.200 Calling Freq.)",
        "144.500 - 144.900 Repeater Inputs",
    ])
    rows = page.split("\n")
    bands, band, chunk = {}, None, []
    for row in rows:
        found = R.TX_HEADING.match(row)
        if found:
            if band and chunk:
                bands[band] = R._parse_plan("\n".join(chunk))
            band, chunk = R.TX_BANDS.get(found.group(1).strip().lower()), []
            continue
        if band:
            chunk.append(row)
    if band and chunk:
        bands[band] = R._parse_plan("\n".join(chunk))
    check("the headings map to the band names the page uses",
          sorted(bands), ["2 m", "6 m"])
    check("6 m comes out with both its segments", len(bands["6 m"]), 2)
    check("  with the frequencies read off correctly",
          (bands["6 m"][0]["low"], bands["6 m"][0]["high"]), (50.0, 50.1))
    check("  and the label kept", "CW" in bands["6 m"][0]["label"], True)
    check("their name for 2 m is 148 MHz, and it is mapped",
          R.TX_BANDS["148 mhz"], "2 m")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
