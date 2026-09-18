#!/usr/bin/env python3
"""The bank shot off a soft cushion: the layer as the ray sees it.

    python3 tests/test_bankshot.py

The reach map used to bank every ray off a mirror at the F2 peak and rate
every cell, near or far, against the 3000 km hop's ceiling with the 3000 km
hop's absorption. That is right for DX and wrong for the county: at noon
on 40 m under a critical frequency of 8 MHz the near cells went dark, when
they are the best on the map. Now the mirror is the parabolic layer's
virtual height, which climbs with frequency and runs away at the critical
frequency; the ceiling for a hop of any length is foF2 times a factor the
layer's own shape gives, pinned to the sonde's M(3000); absorption is
charged by how obliquely the hop crosses the D layer; and the antenna's
weighting keeps the ground's real gain, so a wire a fifth of a wave up is
credited overhead and a wire half a wave up is charged the hole.
"""
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import patterns as P, propagation as prop  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    hm, ym = 280.0, 100.0
    print("\n-- the cushion: a parabolic layer's virtual height --")
    check("at the layer's base for a ray far under the critical frequency", round(P.virtual_height_km(0.0, hm, ym)), 180)
    check("  climbing with frequency", P.virtual_height_km(0.5, hm, ym) < P.virtual_height_km(0.8, hm, ym) < P.virtual_height_km(0.95, hm, ym), True)
    check("  above the peak itself near the critical frequency", P.virtual_height_km(0.99, hm, ym) > hm, True)
    check("  and it never blows up on the page", math.isfinite(P.virtual_height_km(1.0, hm, ym)), True)

    print("\n-- the ray, banked off it --")
    got = P.hop_for(45.0, 7.1, 8.0, hm, ym)
    check("a 40 m ray at 45 degrees under an 8 MHz foF2 comes back", got is not None, True)
    check("  off a mirror between the base and the peak", 180 < got[1] < hm + 5, True)
    check("  and lands a few hundred km out", 300 < got[0] < 900, True)
    check("a 20 m ray straight up goes through", P.hop_for(89.0, 14.1, 8.0, hm, ym), None)
    check("  but banks back at a shallow angle", P.hop_for(10.0, 14.1, 8.0, hm, ym) is not None, True)

    print("\n-- the ceiling, by distance --")
    check("straight up the ceiling is the critical frequency", P.muf_factor(0.0, hm, ym), 1.0)
    f300, f1000, f3000 = (P.muf_factor(d, hm, ym) for d in (300, 1000, 3000))
    check("  rising with distance", 1.0 < f300 < f1000 < f3000, True)
    check("  a few hundred km out is only a little over it", (1.02 < f300 < 1.15, 1.1 < P.muf_factor(500, hm, ym) < 1.5), (True, True))
    check("  and 3000 km is where the sonde's factor lives", 2.4 < f3000 < 3.8, True)
    check("the thickness is a third of the height, and the base stays in the F region",
          (round(P.layer_thickness(hm)), P.layer_thickness(200.0) <= 60.0), (98, True))
    table = P.muf_factor_table(hm, ym)
    check("  the table agrees with the function", abs(table(1000.0) - f1000) < 0.02, True)
    check("  and is interpolated between its steps", abs(table(325.0) - (table(300.0) + table(350.0)) / 2) < 0.02, True)
    pinned = P.muf_factor_table(hm, ym, m3000=2.9)
    check("with the sonde's M(3000) the curve is scaled to pass through it", (pinned(0.0), round(pinned(3000.0), 2)), (1.0, 2.9))
    check("  keeping the layer's shape between", 1.0 < pinned(300.0) < pinned(1000.0) < pinned(3000.0), True)

    print("\n-- absorption, by how the ray crosses the D layer --")
    near, far = P.absorption_secant(200.0, hm), P.absorption_secant(3000.0, hm)
    check("a near-vertical hop crosses it nearly straight", near < 1.3, True)
    check("  a long hop, obliquely - several times the pass", far > 3.0, True)
    noon = prop.band_score(7.1, 8.0 * 1.15, 60.0, 1.0, fof2=8.0, hmf2=hm, absorb_scale=near / far)
    dx = prop.band_score(7.1, 8.0 * 2.9, 60.0, 1.0, fof2=8.0, hmf2=hm)
    check("40 m at noon under foF2 8: the county rates well", noon["score"] >= 60, True)
    check("  and the 3000 km hop on the same band, absorbed and far under its ceiling, does not", dx["score"] < noon["score"] - 20, True)

    print("\n-- the antenna's real gain, kept --")
    low = P.elevation_raw("invertedv", 0.2, mhz=7.1)
    high = P.elevation_raw("invertedv", 0.5, mhz=7.1)
    up = lambda curve: next(p["field"] for p in curve if p["deg"] == 90.0)
    check("a wire a fifth of a wave up is reinforced straight up", up(low) > 1.6, True)
    # real ground reflects only about half the field at normal incidence,
    # so the half-wave wire's hole overhead is a seven-decibel dip, not a
    # null - which is what perfect ground had been promising
    check("  a wire half a wave up has a hole there - a dip, over real ground", 0.3 < up(high) < 0.55, True)
    w_low = prop.takeoff_weights("invertedv", 0.2, hm, mhz=7.1)
    w_high = prop.takeoff_weights("invertedv", 0.5, hm, mhz=7.1)
    check("the weighting credits the low wire overhead beyond 1", w_low(150.0) > 1.0, True)
    check("  no further than the 6 dB the image can give", w_low(150.0) <= prop.WEIGHT_CAP + 1e-9, True)
    check("  and charges the high wire the hole", w_high(150.0) < 0.7 < w_low(150.0), True)

    print("\n-- the numbers behind the colours --")
    g25, g50 = P.height_gains("invertedv", 0.25, mhz=7.1), P.height_gains("invertedv", 0.5, mhz=7.1)
    check("a quarter wave up: the reflection adds straight up", 3.0 < g25["overhead_db"] < 5.0, True)
    check("  half a wave up: a dip of about seven decibels there", -9.0 < g50["overhead_db"] < -5.0, True)
    check("  and the best angle moves from overhead to the twenties", (g25["best_deg"] >= 60, 20 <= g50["best_deg"] <= 35), (True, True))
    check("  the low angle gains with height", g50["low_db"] > g25["low_db"], True)

    print("\n-- the map: the county at noon on 40 m --")
    lat, lon = 46.6, -94.3
    when = datetime(2026, 6, 21, 18, 0, tzinfo=timezone.utc)      # local noon in Minnesota
    base_muf, base_fof2 = prop.levels(150.0, 66.0, lat, 2.9, when=when)
    anchor = 8.0 / base_fof2                                   # a sky with foF2 at 8 over the station
    snap = {"sfi": 150.0, "k_index": 1.0, "hmf2": hm, "fof2": 8.0, "muf": 8.0 * 2.9,
            "calibration": {"factor": anchor, "m3000": 2.9}}
    window = (lat + 4.0, lat - 4.0, lon - 6.0, 12.0)
    low_map = prop.reach_map(7.1, lat, lon, snap, step=1.0, when=when, window=window,
                             antenna={"kind": "invertedv", "height_wl": 0.2, "ground": "average"})
    high_map = prop.reach_map(7.1, lat, lon, snap, step=1.0, when=when, window=window,
                              antenna={"kind": "invertedv", "height_wl": 0.5, "ground": "average"})

    def near_cells(m):
        cols = m["cols"]
        out = []
        for i in range(m["rows"]):
            for j in range(cols):
                glat = m["lat0"] - i * m["step"]
                glon = m["lon0"] + j * m["step"]
                km = math.hypot((glat - lat) * 111.0, (glon - lon) * 111.0 * math.cos(math.radians(lat)))
                if 60 < km < 250:
                    out.append(m["cells"][i * cols + j])
        return out
    low_near, high_near = near_cells(low_map), near_cells(high_map)
    check("cells in the county light up from a low wire", sum(low_near) / len(low_near) >= 55, True)
    check("  and go dark from the same wire half a wave up", sum(high_near) / len(high_near) < sum(low_near) / len(low_near) - 25, True)
    check("the NVIS words say open, with the door the cells use", (low_map["nvis"]["open"], 8.0 < low_map["nvis"]["door_mhz"] < 9.5), (True, True))
    check("the map carries the height's gains for the readout", (low_map["antenna"]["gain"]["overhead_db"] > 2, high_map["antenna"]["gain"]["overhead_db"] < -4), (True, True))
    check("  and the layer's own M(3000) is the sonde's", abs(low_map["nvis"]["m3000_of_layer"] - 2.9) < 0.05, True)
    twenty = prop.reach_map(14.1, lat, lon, snap, step=1.0, when=when, window=window,
                            antenna={"kind": "invertedv", "height_wl": 0.2, "ground": "average"})
    t_near = near_cells(twenty)
    check("20 m over foF2 has a hole in the county whatever the wire", sum(t_near) / len(t_near) < 15, True)
    check("  and says the door is shut", twenty["nvis"]["open"], False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
