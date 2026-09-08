"""Every way out of here, ranked, starting with what the operator already has.

Somebody a long way up a forest road with a handheld and a flat tyre does not
need to be told that a Yagi at fifty feet would work well. They need the list
of things that might work *now*, in the order worth trying, with the honest
odds attached - and they need it from a program that will still answer with no
network, because that is the whole situation.

So this is deliberately not a propagation model. It is the reasoning an Elmer
does out loud: what have you got, what does your license let you use it for,
what is within reach of it, and what have you not thought of yet. Half its
value is in the last part. A Technician with a 5 W handheld usually believes
they have one option and no repeater; they in fact have a repeater they cannot
hear from the valley floor, a national calling channel, APRS, the ISS
digipeater passing overhead twice a day, and - if the sun is behaving - ten
metres. Knowing that is the difference between waiting and working.

The odds are stated in words rather than numbers because numbers here would be
invented. "Worth trying" means worth trying.
"""
from datetime import datetime, timezone

from . import bandplan, propagation, repeaters

# How good a bet each avenue is, worst to best. Sorting is by this, then by
# how little it asks of the operator.
ODDS = ["no", "long shot", "worth trying", "good"]
ODDS_RANK = {name: n for n, name in enumerate(ODDS)}

# What somebody might have in a vehicle, in the words they would use.
GEAR = {
    "ht": "A handheld (2 m / 70 cm)",
    "mobile_vhf": "A mobile VHF/UHF rig",
    "hf_mobile": "HF with a vehicle whip",
    "hf_wire": "HF, and room to string a wire",
    "gmrs": "GMRS, FRS, MURS or CB",
}

# 47 CFR 97.301: what a license class may actually key up on.
TECH_HF = "Technician HF is 10 m SSB 28.300-28.500, plus CW on 80, 40 and 15."


def sun_state(lat, lon, now=None):
    """Lit, grey or dark where the operator is standing.

    This still asks nothing of the network - `solar_elevation` is arithmetic -
    but it does now ask the sun rather than the clock. What it replaces read
    local solar hour off longitude alone and called 7 to 19 daylight: no
    latitude, so no season, and at 46 N in September it was calling half eight
    in the morning "night" and telling somebody in full daylight that darkness
    wanted 80 m.

    A boolean would still have been wrong at the ends of the day, which is
    exactly where somebody stuck up a forest road is most likely to be looking
    at it. So this returns the same three states everything else now uses.
    """
    when = (datetime.fromtimestamp(now, timezone.utc) if now is not None
            else datetime.now(timezone.utc))
    return propagation.sun_regime(
        propagation.solar_elevation(lat, lon, when), lat, when)


def _class_rank(license):
    return bandplan.CLASS_RANK.get((license or "").title(), 0)


def _has_hf(gear):
    return bool({"hf_mobile", "hf_wire"} & set(gear))


def _vhf(gear):
    return bool({"ht", "mobile_vhf"} & set(gear))


def repeater_ways(lat, lon, gear, height_ft=6.0, conn=None):
    """The machines in range, which is where anybody should start."""
    if not _vhf(gear):
        return []
    watts = 50 if "mobile_vhf" in gear else 5
    rows, source = repeaters.nearby(lat, lon, None, limit=6,
                                    height_ft=height_ft, conn=conn)
    cover = repeaters.coverage(lat, lon)
    if not rows:
        if not cover["known"]:
            return [{
                "key": "repeater-unknown", "title": "A repeater - but ELMER has "
                "no list for here", "odds": "worth trying",
                "needs": "Any VHF/UHF radio",
                "do": "Scan 145.110-145.490 and 146.610-147.390 for a machine "
                      "identifying in Morse, and 442-445 above that. Repeaters "
                      "announce themselves every few minutes, so a scan of the "
                      "output sub-bands finds them without a list.",
                "why": "ELMER has no repeater data for this area, which is not "
                       "the same as there being none. Let TowerWitch look this "
                       "position up while you still have a signal.",
            }]
        return []
    best = rows[0]
    odds = "good" if best["km"] < 40 else "worth trying"
    if watts == 5 and best["km"] > 40:
        odds = "long shot"
    return [{
        "key": "repeater", "title": f"{best['call']} on {best['output']:.3f}",
        "odds": odds,
        "needs": ("A handheld" if watts == 5 else "A mobile rig")
                 + f" - the nearest is on {best['band']}, and the rest are below",
        "do": (f"{best['output']:.3f} MHz, "
               + (f"offset {best['offset']:+.1f} MHz, " if best.get("offset") else "")
               + (f"tone {best['tone']}. " if best.get("tone") else "no tone listed. ")
               + f"It is {best['miles']} miles away on a bearing of "
                 f"{best['bearing']}\u00b0. Get the antenna high and clear first: "
                 f"at these frequencies moving twenty feet uphill beats "
                 f"twenty watts."),
        "why": (f"{len(rows)} machine{'' if len(rows) == 1 else 's'} within "
                f"reach, nearest {best['miles']} miles. List from {source}."),
        "rows": rows,
    }]


def ways(lat, lon, gear=(), license="Technician", height_ft=6.0, now=None,
         conn=None):
    """Everything worth trying from here, best bet first."""
    gear = set(gear or [])
    out = list(repeater_ways(lat, lon, gear, height_ft, conn))
    state = sun_state(lat, lon, now)
    day = state == "lit"
    rank = _class_rank(license)

    if _vhf(gear):
        out.append({
            "key": "simplex", "title": "The national calling channels",
            "odds": "worth trying",
            "needs": "Any VHF/UHF radio",
            "do": "146.520 MHz FM on 2 m, 446.000 on 70 cm. Call, then listen "
                  "for a full minute before calling again - somebody hearing "
                  "you has to get to their radio. Say where you are in words "
                  "anybody would know, not in a grid square.",
            "why": "These are monitored by people who scan them out of habit, "
                   "including in vehicles on the road you came in on. No "
                   "repeater has to be working for this to reach somebody.",
        })
        out.append({
            "key": "aprs", "title": "APRS - a message, not a voice",
            "odds": "worth trying",
            "needs": "A radio that can do APRS, or a phone app and a cable",
            "do": "144.390 MHz. Beacon your position, then send a message to "
                  "somebody's callsign or to EMAIL-2 to reach an address. A "
                  "digipeater on a hill relays what your voice cannot carry.",
            "why": "Data survives a path that speech does not, and a beacon "
                   "keeps working while you do something else. It also leaves "
                   "a track of where you were, which matters if anybody ends "
                   "up looking.",
        })
        out.append({
            "key": "iss", "title": "The ISS digipeater, overhead twice a day",
            "odds": "long shot",
            "needs": "A handheld, and patience",
            "do": "145.825 MHz FM, APRS, path ARISS. It passes for about ten "
                  "minutes at a time. Hold the antenna vertically, point up "
                  "and away from hills, and beacon steadily through the pass.",
            "why": "This is the one that surprises people: 250 miles of "
                   "altitude means no terrain in the way at all, and a 5 W "
                   "handheld reaches it. When the valley has beaten every "
                   "ground path you have, the sky has not been tried.",
        })
        out.append({
            "key": "satellite", "title": "An FM satellite pass",
            "odds": "long shot",
            "needs": "A handheld, ideally a small hand-held beam",
            "do": "Work a pass on one of the FM birds - full duplex if the "
                  "radio can, and follow the Doppler. Any pass list held on a "
                  "phone works offline once it is downloaded.",
            "why": "A satellite is a repeater that nothing can stand between "
                   "you and. It asks more of you than the ISS digipeater does, "
                   "but people work them from parking spaces with a handful of "
                   "aluminium.",
        })

    if _has_hf(gear):
        # Twilight keeps 40: the absorber never goes, so the band that would
        # normally take over after dark does not get its advantage.
        band = ("40 m (7.175-7.300)" if state in ("lit", "twilight")
                else "80 m (3.800-4.000)")
        # The half hour nobody should be told to sit out. Both bands are worth
        # a call: 40 has not shut and 80 has stopped being absorbed, and the
        # only instruction that fits is to follow the one down to the other.
        timing = {
            "lit": "Daylight wants 40; ",
            "grey": "You are on the grey line - the sun has set here but not "
                    "on the absorbing layer 80 km up, so it is going and 80 is "
                    "opening while 40 is still up. Call on 40, then follow it "
                    "down to 80; ",
            "dark": "Darkness wants 80; ",
            "twilight": "The sun is down but it will not clear the absorbing "
                        "layer tonight - this far north in summer there is no "
                        "real grey line and 80 stays lossy, so 40 is still the "
                        "better bet even though it is dark; ",
        }[state]
        out.append({
            "key": "nvis", "title": f"Regional HF - {band}, straight up",
            "odds": "good" if rank >= bandplan.CLASS_RANK["General"] else "no",
            "needs": "HF phone privileges - General or above",
            "do": (f"Get the wire low and flat - eight to twelve feet is right, "
                   f"not high - and work {band}. Signal goes up, comes back "
                   f"down over the whole area, and there is no skip zone in the "
                   f"middle. Call on the calling frequencies, then tune slowly "
                   f"and answer somebody."),
            "why": ("A low wire is not a compromise here, it is the design: it "
                    "covers everything within about 300 miles, which is where "
                    "the people who can actually come and get you are. "
                    + timing
                    + "the band that works is the one below the critical "
                      "frequency."),
        })
        out.append({
            "key": "dx", "title": "Long-haul HF - 20 m and up",
            "odds": "worth trying" if rank >= bandplan.CLASS_RANK["General"] else "no",
            "needs": "HF phone privileges - General or above",
            "do": "14.200-14.300 by day. A vehicle whip is inefficient and "
                  "works anyway; get the feedpoint away from the body and put "
                  "counterpoise wires on the ground.",
            "why": "Distance is easier than the middle distance on HF. Talking "
                   "to somebody a thousand miles away who can telephone "
                   "somebody fifty miles from you is a perfectly good rescue.",
        })
        if rank < bandplan.CLASS_RANK["General"]:
            out.append({
                "key": "tech-hf", "title": "Ten metres, which your license does allow",
                "odds": "worth trying" if day else "long shot",
                "needs": "A Technician license and an HF radio",
                "do": "28.300-28.500 MHz SSB. Also CW on 80, 40 and 15 if you "
                      "have the key and the code.",
                "why": TECH_HF + " It is widely believed that a Technician has "
                       "no HF at all, and people sit next to a radio they are "
                       "allowed to use. When 10 m is open it goes a very long "
                       "way on very little.",
            })

    if "gmrs" in gear or not gear:
        out.append({
            "key": "other-services", "title": "The radios that are not amateur",
            "odds": "worth trying",
            "needs": "GMRS, FRS, MURS or CB",
            "do": "GMRS 462.675 is the traditional travellers' assistance "
                  "channel and has repeaters on it. CB channel 9 is the "
                  "emergency channel and 19 is where the trucks are - on a "
                  "road with any freight on it, 19 is often the busiest "
                  "frequency for a hundred miles.",
            "why": "The point is to reach a human being, not to reach one on "
                   "an amateur band. A trucker on 19 has a working radio and "
                   "is going somewhere with a telephone.",
        })

    out.append({
        "key": "emergency", "title": "If it is life or property: any means at all",
        "odds": "the rule",
        "needs": "Nothing but the situation being genuine",
        "do": "Call for help on whatever will carry - any frequency, any "
              "service, any power, licensed or not. Say MAYDAY or EMERGENCY, "
              "who you are, where you are, and what is wrong. Then stay put "
              "and keep the radio on.",
        "why": "47 CFR 97.403 says an amateur station may use any means of "
               "radiocommunication at its disposal to provide essential "
               "communication when life or property is in immediate danger and "
               "normal systems are not available. That is the rule that makes "
               "the box the box: everything above is about being effective, "
               "and this one is about being allowed. It is not a loophole and "
               "it is not for convenience - but when it applies, it applies "
               "completely, and nobody has ever been penalised for it.",
    })

    def sort_key(way):
        # The emergency rule is the floor under the list, not the top of it.
        # Offering it first would answer "how do I get a message out" with
        # "declare an emergency", which is wrong for a flat tyre and dulls the
        # one entry that must keep its force for the day it is needed.
        return (way["key"] == "emergency",
                -ODDS_RANK.get(way["odds"], 0),
                way["key"] != "repeater")
    return [w for w in sorted(out, key=sort_key) if w["odds"] != "no"]


def summary(lat, lon, gear=(), license="Technician", now=None, conn=None):
    """The whole answer, with the reasoning that produced it attached."""
    found = ways(lat, lon, gear, license, now=now, conn=conn)
    cover = repeaters.coverage(lat, lon)
    return {
        "ways": found,
        "coverage": cover,
        "sun": sun_state(lat, lon, now),
        # Kept for anything still asking the old question. "Daytime" now means
        # the absorber is up, which is what it was always taken to mean.
        "daytime": sun_state(lat, lon, now) == "lit",
        "license": license,
        "gear": sorted(gear or []),
        "note": ("Start with the top of this list and work down. Every entry "
                 "is something that has worked for somebody; none of them is "
                 "a promise. Height and a clear horizon do more than power at "
                 "VHF, and patience does more than either."),
    }
