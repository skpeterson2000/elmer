"""The other radios in America: FRS, GMRS, MURS and CB - 47 CFR Part 95.

Most of the two-way radios in the country are not amateur radios. They are
the blister-pack pair from the sporting-goods aisle, the GMRS mobile in the
Jeep, the CB in the truck, the MURS handhelds on the farm. An amateur who
knows only the amateur bands is a person who cannot tell you what the radio
in the next car is, cannot read the channel number on a child's handheld,
and will not think of channel 19 when the repeater does not answer. That is
a gap in operating knowledge, and it is this program's job to close gaps of
that kind - so these services get the same treatment as the amateur bands:
the channels exactly, the law that governs them cited, and the conventions
marked as conventions.

Three things about the law, because they decide what an operator may do:

* These are the **Personal Radio Services**. Nobody holds a license for FRS,
  MURS or CB - 47 CFR 95.305 authorises anyone to operate them, by rule.
  GMRS is the exception: an individual license, 95.1705, that costs money and
  no examination, and covers the licensee's whole immediate family.
* They are **equipment-certified** services. 95.335: "no person shall operate
  a transmitter in any Personal Radio Service unless it is a certified
  transmitter" - certified for *that* service. An amateur handheld that can
  tune 462.5625 has not been, and 95.1761(c) says one never will be while it
  can also do amateur frequencies; for CB, 95.935 names amateur transmitters
  specifically. So the fact that the radio *can* is not the question.
* The emergency provisions are real and they are not a loophole. 97.403 and
  97.405 for the amateur; 95.1731(a) and 95.931(a) for the services, which
  put emergency traffic first on every channel; 95.1705(c)(3), which lets a
  GMRS licensee hand the radio to anyone to pass an emergency message. What
  none of them does is rank the options, so `LADDER` does, in the order an
  Elmer would: your own bands first, then these channels where the humans
  are, and a public-safety frequency only for immediate danger to life when
  nothing else has answered.

Frequencies are MHz. Every number below is copied from the eCFR text of the
section cited beside it, fetched 2026-09-10; the FCC restructured Part 95 in
2017 (82 FR 41104) and amended it in 2021 (86 FR 53565 - FM on CB, GMRS
channel wording) and 2025 (90 FR 57711).
"""

# --------------------------------------------------------------- the services

SERVICES = {
    "frs": {
        "key": "frs", "name": "FRS", "long": "Family Radio Service",
        "cite": "47 CFR Part 95 subpart B",
        "band": "UHF, 462 and 467 MHz - 22 channels shared with GMRS",
        "license": "None. Authorised by rule (95.305); anyone may use one.",
        "power": "2 W ERP on channels 1-7 and 15-22; 0.5 W ERP on 8-14 "
                 "(95.567). FM voice only, 12.5 kHz (95.571, 95.573).",
        "antenna": "Fixed to the radio, not replaceable (95.587). Height is "
                   "your arm.",
        "id": "No call sign; none is issued.",
        "range": "A mile or two in the open, less among buildings and "
                 "trees; line of sight, so a hilltop changes everything.",
        "equipment": "A Part 95 B certified radio. Since December 2017 no "
                     "handheld is certified for both FRS and GMRS "
                     "(95.1761(d)): if it does more than 2 W it is a GMRS "
                     "radio and needs the license.",
        "uses": "Plain-language voice; brief text and position data between "
                "units (95.531). Emergency and traveller-assistance messages "
                "are one of the few permitted one-way transmissions.",
    },
    "gmrs": {
        "key": "gmrs", "name": "GMRS", "long": "General Mobile Radio Service",
        "cite": "47 CFR Part 95 subpart E",
        "band": "UHF, 462 and 467 MHz - 30 channels: the 22 shared with FRS "
                "plus 8 repeater inputs",
        "license": "An individual license (95.1705): 18 or older, no "
                   "examination, $35 for ten years, and it covers the "
                   "licensee's immediate family - spouse, children, "
                   "grandchildren, parents, siblings, in-laws (95.1705(c)). "
                   "Anyone may use a licensee's station to pass an emergency "
                   "message (95.1705(c)(3)).",
        "power": "50 W on the main channels 15-22 and their repeater inputs "
                 "(mobile, base, repeater); 5 W ERP on 1-7; 0.5 W ERP on "
                 "8-14, handhelds only (95.1767).",
        "antenna": "Any antenna; external and elevated antennas are the "
                   "point of the service. Repeaters are permitted (95.1763(a)) "
                   "- inputs are 5 MHz above the 462 main channels.",
        "id": "Your call sign at the end of a transmission or series, and "
              "every 15 minutes during a long one, by voice or Morse "
              "(95.1751). GMRS calls look like WRXX123.",
        "range": "Handheld to handheld like FRS; a 50 W mobile with a roof "
                 "antenna reaches 10-20 miles; through a repeater on a hill, "
                 "the county.",
        "equipment": "A Part 95 E certified radio. No radio that can also "
                     "transmit on amateur frequencies will be certified "
                     "(95.1761(c)).",
        "uses": "Plain-language voice about personal or business "
                "activities, with FRS units too (95.1731). Not to amateur "
                "stations - except emergency messages (95.1733(a)(9)). "
                "'Mayday' is reserved for a vehicle in immediate danger "
                "(95.1733(a)(7)); say EMERGENCY.",
    },
    "murs": {
        "key": "murs", "name": "MURS", "long": "Multi-Use Radio Service",
        "cite": "47 CFR Part 95 subpart J",
        "band": "VHF, 151 and 154 MHz - 5 channels",
        "license": "None. Authorised by rule (95.305).",
        "power": "2 W transmitter output (95.2767) - output, not ERP, so a "
                 "gain antenna is allowed to help.",
        "antenna": "External antennas are allowed, up to 60 ft above ground "
                   "or 20 ft above the structure (95.2741). No repeaters "
                   "and no store-and-forward (95.2733).",
        "id": "No call sign.",
        "range": "A few miles handheld; a base with a roof antenna and 2 W "
                 "on VHF carries surprisingly far over flat country.",
        "equipment": "A Part 95 J certified radio (95.2761). Older Part 90 "
                     "business radios on these frequencies are grandfathered "
                     "(95.2705).",
        "uses": "Voice, data, image, telemetry and telecommand (95.2731). "
                "Farms, hunting camps, stores and driveway alarms live "
                "here; the two 154 MHz channels were the old business "
                "'Blue Dot' and 'Green Dot' frequencies.",
    },
    "cb": {
        "key": "cb", "name": "CB", "long": "Citizens Band Radio Service (11 m)",
        "cite": "47 CFR Part 95 subpart D",
        "band": "HF, 26.965-27.405 MHz - 40 channels",
        "license": "None since 1983. Authorised by rule (95.305). No call "
                   "sign; a handle is fine.",
        "power": "4 W carrier on AM or FM; 12 W PEP on SSB (95.967). No "
                 "external amplifier under any circumstances (95.939).",
        "antenna": "Any antenna, up to 60 ft above ground or 20 ft above "
                   "the building or tree it is on (95.941).",
        "id": "None required.",
        "range": "A few miles mobile to mobile, more with SSB. When 10 m is "
                 "open 11 m is open too, and skip carries a 4 W call "
                 "hundreds of miles - the old 155-mile rule was dropped in "
                 "2017.",
        "equipment": "A Part 95 D certified radio. 95.935 says in so many "
                     "words that an amateur transmitter capable of 26-30 "
                     "MHz is not one, and using it on the channels is a "
                     "violation of section 301.",
        "uses": "Plain-language voice with other CB stations (95.931), and "
                "with Canadian General Radio Service stations only "
                "(95.933(d)). Channel 9 is emergency and traveller "
                "assistance and nothing else - that one is law, 95.931(a)(2).",
    },
}
ORDER = ["frs", "gmrs", "murs", "cb"]

# --------------------------------------------------- FRS / GMRS, 95.563 & 95.1763

# The 22 shared channels. FRS numbers them; GMRS talks in frequencies and
# calls 1-7 the "462 interstitial", 8-14 the "467 interstitial" and 15-22 the
# "462 main" channels. Both vocabularies are carried because the radio in
# your hand uses one and the rule book the other.
_FRS_GMRS = [
    # n, MHz, FRS ERP W, GMRS limit, GMRS kind, GMRS bandwidth kHz
    (1, 462.5625, 2.0, "5 W ERP", "462 interstitial", 20),
    (2, 462.5875, 2.0, "5 W ERP", "462 interstitial", 20),
    (3, 462.6125, 2.0, "5 W ERP", "462 interstitial", 20),
    (4, 462.6375, 2.0, "5 W ERP", "462 interstitial", 20),
    (5, 462.6625, 2.0, "5 W ERP", "462 interstitial", 20),
    (6, 462.6875, 2.0, "5 W ERP", "462 interstitial", 20),
    (7, 462.7125, 2.0, "5 W ERP", "462 interstitial", 20),
    (8, 467.5625, 0.5, "0.5 W ERP", "467 interstitial", 12.5),
    (9, 467.5875, 0.5, "0.5 W ERP", "467 interstitial", 12.5),
    (10, 467.6125, 0.5, "0.5 W ERP", "467 interstitial", 12.5),
    (11, 467.6375, 0.5, "0.5 W ERP", "467 interstitial", 12.5),
    (12, 467.6625, 0.5, "0.5 W ERP", "467 interstitial", 12.5),
    (13, 467.6875, 0.5, "0.5 W ERP", "467 interstitial", 12.5),
    (14, 467.7125, 0.5, "0.5 W ERP", "467 interstitial", 12.5),
    (15, 462.5500, 2.0, "50 W", "462 main", 20),
    (16, 462.5750, 2.0, "50 W", "462 main", 20),
    (17, 462.6000, 2.0, "50 W", "462 main", 20),
    (18, 462.6250, 2.0, "50 W", "462 main", 20),
    (19, 462.6500, 2.0, "50 W", "462 main", 20),
    (20, 462.6750, 2.0, "50 W", "462 main", 20),
    (21, 462.7000, 2.0, "50 W", "462 main", 20),
    (22, 462.7250, 2.0, "50 W", "462 main", 20),
]

# What people have agreed to do on them. Convention, not law - except the
# emergency priority, which is 95.1731(a) on every channel.
FRS_GMRS_NOTES = {
    20: "Travellers' assistance and emergency calling by long convention - "
        "462.675 with a 141.3 Hz tone (the 'travel tone'). Many GMRS "
        "repeaters sit on it.",
    16: "Off-road and 4x4 groups' convention; one of the busier trail "
        "channels.",
    1: "Where a blister-pack radio comes out of the box; the FRS 'calling' "
       "channel by default rather than agreement.",
    19: "The other common GMRS repeater output; a good scan stop.",
}


def frs_gmrs_channels():
    rows = []
    for n, mhz, frs_w, gmrs, kind, bw in _FRS_GMRS:
        row = {"n": n, "mhz": mhz, "frs_erp_w": frs_w, "gmrs": gmrs,
               "gmrs_kind": kind, "gmrs_bandwidth_khz": bw,
               "frs": f"{frs_w:g} W ERP", "note": FRS_GMRS_NOTES.get(n, "")}
        if kind == "462 main":
            # 95.1763(c): the 467 main channels are the repeater inputs, 5 MHz
            # up, and a mobile or handheld may transmit there only through a
            # repeater. Radios label them 15R-22R or RPT15-RPT22.
            row["repeater_input"] = round(mhz + 5.0, 4)
            row["handheld_only"] = False
        else:
            row["repeater_input"] = None
            row["handheld_only"] = kind == "467 interstitial"
        rows.append(row)
    return rows


FRS_GMRS_CHANNELS = frs_gmrs_channels()
GMRS_REPEATER_INPUTS = [c["repeater_input"] for c in FRS_GMRS_CHANNELS
                        if c["repeater_input"]]

# ------------------------------------------------------------- MURS, 95.2763

MURS_CHANNELS = [
    {"n": 1, "mhz": 151.820, "bandwidth_khz": 11.25, "note": ""},
    {"n": 2, "mhz": 151.880, "bandwidth_khz": 11.25, "note": ""},
    {"n": 3, "mhz": 151.940, "bandwidth_khz": 11.25, "note": ""},
    {"n": 4, "mhz": 154.570, "bandwidth_khz": 20.0,
     "note": "'Blue Dot' - the old itinerant business channel; most MURS "
             "radios and driveway alarms ship on this or the next."},
    {"n": 5, "mhz": 154.600, "bandwidth_khz": 20.0,
     "note": "'Green Dot' - the other old business channel; big-box stores "
             "used it for years."},
]
# 95.2773: 11.25 kHz on the three 151 MHz channels, 20 kHz on the two 154 MHz
# channels - narrowband FM on the first three, which a radio set to wide will
# splatter.

# ------------------------------------------------------------- CB, 95.963

_CB = [26.965, 26.975, 26.985, 27.005, 27.015, 27.025, 27.035, 27.055,
       27.065, 27.075, 27.085, 27.105, 27.115, 27.125, 27.135, 27.155,
       27.165, 27.175, 27.185, 27.205, 27.215, 27.225, 27.255, 27.235,
       27.245, 27.265, 27.275, 27.285, 27.295, 27.305, 27.315, 27.325,
       27.335, 27.345, 27.355, 27.365, 27.375, 27.385, 27.395, 27.405]
# Channels 23-25 are out of frequency order (27.255, 27.235, 27.245): 24 and
# 25 were added into gaps when the band went from 23 to 40 channels in 1977,
# and 23 kept its old frequency. A program that "fixes" this is wrong.

CB_NOTES = {
    9: "Emergency and traveller assistance only - law, 95.931(a)(2), not "
       "convention. Monitored where REACT teams and some sheriffs' offices "
       "still do; fewer than there were.",
    19: "The highway channel by convention. On a road with freight on it, "
        "the busiest frequency for a hundred miles, and every trucker on it "
        "has a telephone.",
    17: "North-south highway convention on the west coast.",
    6: "'The Superbowl' - the loud AM skip channel; not where to be heard.",
    16: "SSB by convention (and 4x4 clubs on AM).",
    36: "SSB territory begins - 36 to 40, lower sideband.",
    38: "The SSB calling channel by convention, LSB. 12 W PEP and no "
        "carrier: the quietest place on the band to be heard at distance.",
}


def cb_channels():
    return [{"n": n, "mhz": mhz, "note": CB_NOTES.get(n, ""),
             "law": n == 9} for n, mhz in enumerate(_CB, start=1)]


CB_CHANNELS = cb_channels()
CB_LOW, CB_HIGH = _CB[0], _CB[-1]

# --------------------------------------------------------------- lookups


def _near(a, b, khz):
    return abs(a - b) * 1000.0 <= khz


def service_at(mhz):
    """Which personal-radio channel a frequency is, or None.

    The tolerance is a kilohertz - rounding, not nearness - because "close
    to channel 3" is not channel 3: the radio is either on it or it is not,
    and a dial 2.5 kHz off an FRS channel is off it.
    """
    try:
        mhz = float(mhz)
    except (TypeError, ValueError):
        return None
    for c in FRS_GMRS_CHANNELS:
        if _near(mhz, c["mhz"], 1.0):
            who = (f"FRS {c['frs']} (no license) / GMRS {c['gmrs']} "
                   f"(GMRS license)")
            return {"service": "frs_gmrs", "name": "FRS/GMRS",
                    "channel": c["n"], "mhz": c["mhz"],
                    "label": f"FRS/GMRS channel {c['n']}", "who": who,
                    "note": c["note"], "cite": "47 CFR 95.563, 95.1763"}
        if c["repeater_input"] and _near(mhz, c["repeater_input"], 1.0):
            return {"service": "gmrs", "name": "GMRS",
                    "channel": c["n"], "mhz": c["repeater_input"],
                    "label": f"GMRS repeater input for channel {c['n']}",
                    "who": "GMRS license; transmit here only through a "
                           "repeater (95.1763(c))",
                    "note": "", "cite": "47 CFR 95.1763(c)"}
    for c in MURS_CHANNELS:
        if _near(mhz, c["mhz"], 1.0):
            return {"service": "murs", "name": "MURS",
                    "channel": c["n"], "mhz": c["mhz"],
                    "label": f"MURS channel {c['n']}",
                    "who": "no license; 2 W output, certified MURS radio",
                    "note": c["note"], "cite": "47 CFR 95.2763"}
    for c in CB_CHANNELS:
        if _near(mhz, c["mhz"], 1.0):
            return {"service": "cb", "name": "CB",
                    "channel": c["n"], "mhz": c["mhz"],
                    "label": f"CB channel {c['n']}",
                    "who": "no license; 4 W AM/FM or 12 W PEP SSB, "
                           "certified CB radio",
                    "note": c["note"], "cite": "47 CFR 95.963"}
    return None


def channel(service, n):
    table = {"frs": FRS_GMRS_CHANNELS, "gmrs": FRS_GMRS_CHANNELS,
             "murs": MURS_CHANNELS, "cb": CB_CHANNELS}.get(service, [])
    for c in table:
        if c["n"] == n:
            return c
    return None


# ------------------------------------------- an amateur radio on these channels

# The honest statement, in one place, so every page says the same thing.
AMATEUR_ON_THESE = {
    "can": "Most amateur VHF/UHF handhelds and mobiles will tune and transmit "
           "on the FRS/GMRS and MURS channels, and many 10 m rigs will go "
           "down to 27 MHz. The radio does not know the rules.",
    "law": "The rules do. Part 95 services are equipment-certified: 95.335 "
           "forbids operating any transmitter not certified for that "
           "service, 95.1761(c) bars GMRS certification for anything that "
           "can also do amateur frequencies, and 95.935 names amateur "
           "transmitters on CB as a section 301 violation. Outside an "
           "emergency, keying an amateur radio on these channels is not "
           "authorised - not by your amateur license and not by anything "
           "else. Listening is legal and always was.",
    "emergency": "In one, 47 CFR 97.403 and 97.405 say no provision of the "
                 "amateur rules prevents an amateur station using any means "
                 "at its disposal for the immediate safety of life or "
                 "protection of property when normal systems are not "
                 "available, or to attract attention when in distress. "
                 "The personal services meet you halfway: every FRS, GMRS "
                 "and CB channel may carry emergency traffic and must give "
                 "it priority (95.1731(a), 95.931(a)); a GMRS licensee may "
                 "hand the radio to anyone for an emergency message "
                 "(95.1705(c)(3)); GMRS may pass emergency messages to "
                 "amateur stations (95.1733(a)(9)).",
    "judgement": "Carry a radio licensed for the service you mean to use it "
                 "in. That is the rule and it is good advice. Extenuating "
                 "circumstances are exactly that - and when they arrive, a "
                 "call on channel 19 or 462.675 with the radio you have is "
                 "the better choice than keying up on a public-safety "
                 "frequency: it reaches a person who can telephone for you, "
                 "and it does not step on the people already answering "
                 "somebody else's emergency.",
}

# The order to try, from an Elmer rather than a rule book. The rules permit
# any means; they do not say which means first. This does.
LADDER = [
    {"step": 1, "what": "Your own bands, with your own license",
     "how": "The repeater, 146.520, the HF calling frequencies - everything "
            "above this on the list. This is what the license is for and "
            "where the people who will recognise the call are listening."},
    {"step": 2, "what": "The personal radio channels, where the humans are",
     "how": "CB channel 9 then 19; GMRS 462.675 with the 141.3 tone, then "
            "FRS 1; MURS 154.570 and 154.600. With a certified radio this "
            "is simply legal. With an amateur radio it is 97.403 territory: "
            "genuine emergency only, plain language, say EMERGENCY, where "
            "you are, what is wrong."},
    {"step": 3, "what": "A public-safety frequency - immediate danger to "
                        "life, nothing else has answered",
     "how": "Dispatch channels are somebody else's working frequencies: a "
            "handheld on a repeater input may not be heard at all, and if it "
            "is, it lands in the middle of a response already under way. "
            "Last, and only when it is life."},
]


def for_bandplan():
    """Everything the band plan page shows about these services."""
    return {
        "services": [SERVICES[k] for k in ORDER],
        "frs_gmrs": FRS_GMRS_CHANNELS,
        "murs": MURS_CHANNELS,
        "cb": CB_CHANNELS,
        "amateur": AMATEUR_ON_THESE,
        "ladder": LADDER,
    }
