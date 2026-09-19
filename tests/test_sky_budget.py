#!/usr/bin/env python3
"""The skywave prediction considers power.

    python3 tests/test_sky_budget.py

Reported: "the propagation prediction model is not considering power output.
I'm pretty certain that makes a big difference." It does, and it was not.
The skywave half of path_bands() answered one question - does the band come
back from the layer over this distance - and called it the whole answer, so
20 m over 1500 km read "Excellent 85" at five watts and at a kilowatt alike,
twenty-five decibels apart.

Two questions, and they have different owners:

  - whether a band comes back is the ionosphere's, and no power changes it:
    above the MUF a kilowatt goes through to space the same as five watts,
    and inside the skip zone nothing lands however loud;
  - whether what comes back can be copied is power against loss against
    noise, and that is where the watts live.

sky_budget() is the second half: free space over the ray as it actually
travels, the D layer by day, a ground touch per extra hop, a little at each
turn, polarisation - against the same noise floor and the same per-mode
requirement the ground-wave and VHF budgets already use. The row carries a
margin, a verdict, and where it is short, the power that would close it -
or, past the legal limit, the honest advice instead: nightfall, or a mode
that hears deeper.

The reporter's own test was 11 m at 12 W against 10 m and 12 m at 1500 W.
Those three sit on a sky that is either open to all of them or shut to all
of them, so the band verdicts agree at any power - which is right - and the
budget is where they part.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer import propagation as P

    # A generous evening sky, so the bands under test are open by geometry
    # and the budget is the only thing in the way.
    NIGHT = dict(fof2=6.0, hmf2=300.0, elevation=-20.0, k_index=2.0, muf=21.0)
    NOON = dict(NIGHT, elevation=60.0)

    def row(km, band, watts, mode="ssb", sky=NIGHT):
        rows = P.path_bands(km, watts=watts, emission=mode, **sky)
        return next(r for r in rows["bands"] if r["band"] == band)

    print("\n-- the sky decides whether it comes back; the watts decide whether it is heard --")
    a, b = row(1500, "20m", 5), row(1500, "20m", 1500)
    check("20 m over 1500 km comes back at five watts and at a kilowatt alike",
          (a["sky"], b["sky"], a["hops"], b["hops"]), (True, True, 1, 1))
    check("  and the budgets are twenty-five decibels apart",
          round(b["budget"]["margin_db"] - a["budget"]["margin_db"], 1), 24.8)
    check("  a kilowatt is solid", b["budget"]["verdict"], "solid")
    check("  five watts is heard but not solid", a["budget"]["verdict"] in ("workable", "marginal"), True)

    print("\n-- two hops of 40 m at five watts is short, and says what would do --")
    r = row(3500, "40m", 5)
    check("the sky carries it", (r["sky"], r["hops"]), (True, 2))
    check("  but five watts does not", r["works"], False)
    check("  the label says which of the two it failed on", r["label"], "Open, short at 5 W")
    check("  and names a power that would", (r["budget"]["watts_for"] or 0) > 5, True)
    check("  which is under the legal limit here", r["budget"]["legal"], True)
    check("  and the why says so rather than the geometry's line",
          "arrives" in r["why"] and "short" in r["why"], True)
    more = row(3500, "40m", r["budget"]["watts_for"])
    check("  and at that power it is workable",
          (more["works"], more["budget"]["verdict"]), (True, "workable"))

    print("\n-- a narrower mode hears deeper at the same watts --")
    ssb, cw, ft8 = (row(3500, "40m", 5, m)["budget"]["margin_db"] for m in ("ssb", "cw", "ft8"))
    check("CW has about fourteen decibels on SSB", round(cw - ssb, 1), 13.8)
    check("  and FT8 about twenty-eight", round(ft8 - ssb, 1), 28.0)

    print("\n-- the D layer by day, and the honest advice past the legal limit --")
    day, night = row(1000, "160m", 100, sky=NOON), row(1000, "160m", 100)
    check("160 m at noon is charged for the D layer", day["budget"]["absorb_db"] > 30, True)
    check("  and at night is not", night["budget"]["absorb_db"], 0.0)
    check("  by day no legal power closes it, and it says so",
          (day["budget"]["legal"], day["budget"]["daylight"], "after dark" in day["why"]), (False, True, True))
    check("  by night a hundred watts is heard", night["works"], True)

    print("\n-- a band that does not come back says so, whatever the watts --")
    near = row(300, "20m", 1500)
    check("20 m over 300 km is inside its skip zone", near["sky"], False)
    check("  the label says that, not the band's rating", near["label"], "Inside the skip zone")
    check("  and there is no budget to argue with", near["budget"], None)

    print("\n-- the reporter's own test: 11 m at 12 W, 10 m and 12 m at 1500 W --")
    # 11 m is capped by law at 12 W SSB whatever is typed, and the three sit
    # on one sky: the verdicts agree on whether they come back, and where
    # they do, the kilowatt is the one in hand.
    # On foF2 9 the three bands' skip zones run 1900-2600 km, so the path
    # is 3000 km: past every skip zone and inside one hop.
    open_sky = dict(fof2=9.0, hmf2=300.0, elevation=30.0, k_index=2.0, muf=32.0)
    cb, ten, twelve = (row(3000, b, w, sky=open_sky) for b, w in (("11m", 1500), ("10m", 1500), ("12m", 1500)))
    check("11 m is held to the law's 12 W whatever was asked for", cb["watts"], 12.0)
    check("  all three come back on an open sky", (cb["sky"], ten["sky"], twelve["sky"]), (True, True, True))
    check("  and the kilowatt bands are solid where 12 W is not",
          (ten["budget"]["verdict"], twelve["budget"]["verdict"], cb["budget"]["verdict"] != "solid"),
          ("solid", "solid", True))
    shut = dict(open_sky, fof2=3.4, muf=9.9)
    cb2, ten2 = row(3000, "11m", 1500, sky=shut), row(3000, "10m", 1500, sky=shut)
    check("on a sky shut to them, the kilowatt is no better than 12 W - neither comes back",
          (cb2["sky"], ten2["sky"], cb2["budget"], ten2["budget"]), (False, False, None, None))

    print("\n-- the page's request carries the watts, and FM is never charged on HF --")
    from elmer.app import app
    from elmer import db
    conn = db.connect()
    db.save_settings(conn, {"location": {"lat": 46.6, "lon": -94.3, "grid": "EN26"}})
    client = app.test_client()
    client.set_cookie("elmer_user", str(conn.user_id))
    local = {"REMOTE_ADDR": "127.0.0.1"}
    lo = client.get("/api/path-to?to=EM48&gear=hf_wire&license=Extra&watts=5", environ_base=local).get_json()
    hi = client.get("/api/path-to?to=EM48&gear=hf_wire&license=Extra&watts=1500", environ_base=local).get_json()
    # The live sky. Without a network the snapshot is blind and every row
    # says so; that is the sky's answer and not this test's subject.
    if not any(a.get("margin_db") is not None for a in lo["approach"] + hi["approach"]):
        print("    (no live sky reading here - the watts comparison over the network is skipped)")
    else:
        lo_ok = [a["band"] for a in lo["approach"] if a["odds"] in ("good", "worth trying")]
        hi_ok = [a["band"] for a in hi["approach"] if a["odds"] in ("good", "worth trying")]
        check("more bands are worth trying at a kilowatt than at five watts", len(hi_ok) > len(lo_ok), True)
        check("  and an approach row carries its margin", "margin_db" in lo["approach"][0], True)
    fm = client.get("/api/path-link?to=EM48&band=40m&mode=fm&watts=100", environ_base=local).get_json()
    check("a sky band asked about in FM is answered in SSB", (fm.get("emission") or "").lower(), "ssb")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
