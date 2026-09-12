#!/usr/bin/env python3
"""The other radios in America - FRS, GMRS, MURS and CB - pinned to Part 95.

    python3 tests/test_personal.py

Every frequency and power figure here was read from the eCFR text of the
section named beside it on 2026-09-10 (47 CFR 95.563, 95.567, 95.1763,
95.1767, 95.2763, 95.2767, 95.963, 95.967). If the FCC moves a channel this
is what should fail, and the number in the assertion is the number in the
rule - not the number in the module, which would test nothing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import personal as P, reachout, rigs, activations  # noqa: E402
from elmer import antenna_advice, rfexposure  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"   (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("-- FRS / GMRS, 95.563 and 95.1763 --")
    ch = {c["n"]: c for c in P.FRS_GMRS_CHANNELS}
    check("22 channels", len(ch), 22)
    check("channel 1 is 462.5625", ch[1]["mhz"], 462.5625)
    check("channel 8 is 467.5625", ch[8]["mhz"], 467.5625)
    check("channel 15 is 462.5500", ch[15]["mhz"], 462.55)
    check("channel 20 is 462.6750", ch[20]["mhz"], 462.675)
    check("channel 22 is 462.7250", ch[22]["mhz"], 462.725)
    check("FRS: 2 W ERP on 1-7 and 15-22 (95.567)",
          {ch[n]["frs_erp_w"] for n in list(range(1, 8)) + list(range(15, 23))}, {2.0})
    check("  and 0.5 W ERP on 8-14", {ch[n]["frs_erp_w"] for n in range(8, 15)}, {0.5})
    check("GMRS: 50 W on the main channels 15-22 (95.1767(a))",
          {ch[n]["gmrs"] for n in range(15, 23)}, {"50 W"})
    check("  5 W ERP on 1-7 (95.1767(b))", {ch[n]["gmrs"] for n in range(1, 8)}, {"5 W ERP"})
    check("  0.5 W ERP on 8-14, handhelds only (95.1767(c), 95.1763(d))",
          ({ch[n]["gmrs"] for n in range(8, 15)}, all(ch[n]["handheld_only"] for n in range(8, 15))),
          ({"0.5 W ERP"}, True))
    check("repeater inputs are 5 MHz above the main channels (95.1763(c))",
          [ch[n]["repeater_input"] for n in range(15, 23)],
          [467.55, 467.575, 467.6, 467.625, 467.65, 467.675, 467.7, 467.725])
    check("  and no interstitial channel has one",
          all(ch[n]["repeater_input"] is None for n in range(1, 15)), True)
    check("  eight of them", len(P.GMRS_REPEATER_INPUTS), 8)
    check("bandwidth: 12.5 kHz on the 467 interstitials, 20 kHz elsewhere (95.1773)",
          ({ch[n]["gmrs_bandwidth_khz"] for n in range(8, 15)},
           {ch[n]["gmrs_bandwidth_khz"] for n in list(range(1, 8)) + list(range(15, 23))}),
          ({12.5}, {20}))
    check("channel 20 carries the travel-tone convention", "141.3" in ch[20]["note"], True)

    print("\n-- MURS, 95.2763 --")
    check("five channels", [c["mhz"] for c in P.MURS_CHANNELS],
          [151.82, 151.88, 151.94, 154.57, 154.6])
    check("11.25 kHz on the 151s, 20 kHz on the 154s (95.2773)",
          [c["bandwidth_khz"] for c in P.MURS_CHANNELS], [11.25, 11.25, 11.25, 20.0, 20.0])
    check("2 W output, said in the service facts", "2 W" in P.SERVICES["murs"]["power"], True)

    print("\n-- CB, 95.963 --")
    cb = {c["n"]: c for c in P.CB_CHANNELS}
    check("40 channels", len(cb), 40)
    check("channel 1 is 26.965", cb[1]["mhz"], 26.965)
    check("channel 9 is 27.065", cb[9]["mhz"], 27.065)
    check("channel 19 is 27.185", cb[19]["mhz"], 27.185)
    check("channel 40 is 27.405", cb[40]["mhz"], 27.405)
    check("23, 24, 25 keep their historical order: 27.255, 27.235, 27.245",
          [cb[23]["mhz"], cb[24]["mhz"], cb[25]["mhz"]], [27.255, 27.235, 27.245])
    check("channel 9 is marked as law, not convention", (cb[9]["law"], cb[19]["law"]), (True, False))
    check("  and its note cites 95.931", "95.931" in cb[9]["note"], True)
    check("4 W AM/FM and 12 W PEP SSB in the facts (95.967)",
          ("4 W" in P.SERVICES["cb"]["power"], "12 W PEP" in P.SERVICES["cb"]["power"]), (True, True))

    print("\n-- the law, in the words the pages use --")
    for key in P.ORDER:
        svc = P.SERVICES[key]
        check(f"{svc['name']} says who may use it", bool(svc["license"]), True)
    check("GMRS names the license and the no-exam", "no examination" in P.SERVICES["gmrs"]["license"], True)
    check("  and the family (95.1705(c))", "immediate family" in P.SERVICES["gmrs"]["license"], True)
    check("  and the 15-minute identification (95.1751)", "15 minutes" in P.SERVICES["gmrs"]["id"], True)
    check("FRS, MURS and CB need no license",
          all("None" in P.SERVICES[k]["license"] for k in ("frs", "murs", "cb")), True)
    check("the amateur note cites 95.335", "95.335" in P.AMATEUR_ON_THESE["law"], True)
    check("  and 97.403 and 97.405", ("97.403" in P.AMATEUR_ON_THESE["emergency"],
                                      "97.405" in P.AMATEUR_ON_THESE["emergency"]), (True, True))
    check("  and does not call listening illegal", "Listening is legal" in P.AMATEUR_ON_THESE["law"], True)
    check("the ladder is own bands, then personal channels, then public safety",
          [s["step"] for s in P.LADDER], [1, 2, 3])
    check("  public safety is last and for life only",
          "life" in P.LADDER[2]["what"].lower(), True)

    print("\n-- what frequency is this? --")
    check("462.5625 is FRS/GMRS channel 1", P.service_at(462.5625)["label"], "FRS/GMRS channel 1")
    check("  and says who may use it",
          ("no license" in P.service_at(462.5625)["who"], "GMRS license" in P.service_at(462.5625)["who"]),
          (True, True))
    check("467.675 is the repeater input for channel 20",
          P.service_at(467.675)["label"], "GMRS repeater input for channel 20")
    check("154.600 is MURS channel 5", P.service_at(154.6)["label"], "MURS channel 5")
    check("27.065 is CB channel 9", P.service_at(27.065)["label"], "CB channel 9")
    check("27.185 is CB channel 19", P.service_at(27.185)["channel"], 19)
    check("146.520 is nobody's channel here", P.service_at(146.52), None)
    check("462.700 close but not on a channel (462.7000 is ch 21)", P.service_at(462.7)["channel"], 21)
    check("  462.6900 is between channels and is not one", P.service_at(462.69), None)
    check("garbage is None, not an exception", P.service_at("x"), None)
    check("channel() finds by service and number", P.channel("cb", 19)["mhz"], 27.185)

    print("\n-- the rest of the program knows them --")
    check("the gear list has GMRS/FRS, MURS and CB",
          all(k in reachout.GEAR for k in ("gmrs", "murs", "cb")), True)
    check("  and every gear key is judged for POTA/SOTA",
          all(k in activations.GEAR_VERDICTS for k in reachout.GEAR), True)
    check("a CB manual on the shelf ticks CB", rigs.gear_from([rigs.identify("Cobra 29 LTD Classic")]), ["cb"])
    check("a MURS radio ticks MURS", rigs.gear_from([rigs.identify("BTECH MURS-V1")]), ["murs"])
    check("a GMRS mobile still ticks gmrs", rigs.gear_from([rigs.identify("Midland MXT575")]), ["gmrs"])
    ways = reachout.ways(46.35, -94.2, gear=["cb"], license="Technician", now=1_800_000_000)
    keys = [w["key"] for w in ways]
    check("a CB owner gets the CB card and the rule, and nothing amateur",
          keys, ["cb", "emergency"])
    ways = reachout.ways(46.35, -94.2, gear=["gmrs", "murs"], license="Technician", now=1_800_000_000)
    check("GMRS and MURS each get a card", {"frs-gmrs", "murs"} <= set(w["key"] for w in ways), True)
    ways = reachout.ways(46.35, -94.2, gear=["ht"], license="Technician", now=1_800_000_000)
    ham = [w for w in ways if w["key"] == "ham-on-frs"]
    check("a handheld alone gets the listen-there card", len(ham), 1)
    check("  which says listening is legal and transmitting is not authorised",
          ("Listening is legal" in ham[0]["why"], "not authorised" in ham[0]["why"]), (True, True))
    check("  and is in receive", "receive" in ham[0]["needs"], True)
    ways = reachout.ways(46.35, -94.2, gear=["ht", "gmrs"], license="Technician", now=1_800_000_000)
    check("with a GMRS radio as well the listen-there card gives way to the FRS/GMRS one",
          ("ham-on-frs" in [w["key"] for w in ways], "frs-gmrs" in [w["key"] for w in ways]), (False, True))
    rule = [w for w in ways if w["key"] == "emergency"][0]
    check("the emergency card carries the ladder", [s["step"] for s in rule["ladder"]], [1, 2, 3])
    check("  and stays last", [w["key"] for w in ways][-1], "emergency")
    check("no gear at all still offers FRS/GMRS and CB",
          {"frs-gmrs", "cb"} <= set(w["key"] for w in reachout.ways(46.35, -94.2, gear=[], now=1_800_000_000)), True)

    whip_only = [w for w in reachout.ways(46.35, -94.2, gear=["hf_mobile"], license="General", now=1_800_000_000)
                 if w["key"] == "nvis"][0]
    check("a whip-only HF operator is told two whips make a dipole", "dipole mount" in whip_only["do"], True)
    with_wire = [w for w in reachout.ways(46.35, -94.2, gear=["hf_wire"], license="General", now=1_800_000_000)
                 if w["key"] == "nvis"][0]
    check("  and somebody with a wire is not", "dipole mount" in with_wire["do"], False)

    ssb = [w for w in reachout.ways(46.35, -94.2, gear=["vhf_ssb"], license="Technician", now=1_800_000_000)
           if w["key"] == "vhf-ssb"]
    check("an all-mode VHF rig gets the 2 m SSB calling card", len(ssb), 1)
    check("  at 144.200, read from the band plan", "144.200" in ssb[0]["title"], True)
    check("  with 6 m and 70 cm beside it", ("50.125" in ssb[0]["do"], "432.100" in ssb[0]["do"]), (True, True))
    check("  and the FM calling channels too", any(w["key"] == "simplex" for w in
          reachout.ways(46.35, -94.2, gear=["vhf_ssb"], license="Technician", now=1_800_000_000)), True)
    check("an FM-only mobile does not", any(w["key"] == "vhf-ssb" for w in
          reachout.ways(46.35, -94.2, gear=["mobile_vhf"], license="Technician", now=1_800_000_000)), False)
    check("the shelf ticks it for an all-mode set", "vhf_ssb" in rigs.gear_from([rigs.identify("IC-705")]), True)
    check("  and for a VHF all-mode set", rigs.gear_from([rigs.identify("IC-9700")]), ["mobile_vhf", "vhf_ssb"])

    ctx = antenna_advice.frequency_context(462.675)
    check("the antenna designer knows 462.675 is channel 20",
          (ctx["label"], ctx["band"]), ("FRS/GMRS channel 20", "FRS/GMRS"))
    check("  and assumes local FM for it", antenna_advice.default_use(462.675), "local")
    check("  and regional for a CB whip", antenna_advice.default_use(27.185), "regional")
    check("  and still nothing for a frequency nobody owns", antenna_advice.frequency_context(100.0), None)
    warn = rfexposure.validate({"frequency_mhz": 462.55, "pep_watts": 50, "gain_dbd": 3,
                                "distance_uncontrolled_ft": 30, "distance_controlled_ft": 20,
                                "mode": "fm"})
    check("the exposure check names the channel instead of doubting the number",
          any("FRS/GMRS channel 15" in w for w in warn), True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
