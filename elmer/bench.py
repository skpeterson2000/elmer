"""The bench: the instruments and the habits of a station, written down.

The Tools page had three instruments - a network analyser, a sextant, the
exposure evaluation - and the Lab has the arithmetic the exams ask about.
Between them sits the craft nobody examines and everybody needs: how to
read an antenna analyser and which way to cut, what a field strength meter
is for and what it cannot tell you, what a multimeter should read at each
point of a working station, and the handful of habits that keep a person
alive around fuses, towers, lightning and a power supply that has just been
switched off. It is the kind of thing that used to be learned by standing
next to somebody, and this is it written down so it can still be handed on
when there is nobody to stand next to.

Each card says what the thing is, how it is used, what the readings mean,
and why - and names the exam questions that ask about it, because the pool
is the one text every licensee has read and the card should agree with it.
The calculators beside the cards are in static/bench.js; they do the
arithmetic the cards describe, for the numbers of the station in front of
you rather than the textbook's.
"""

# --------------------------------------------------------- the benches

# Where each bench lives. The Lab is what the exams ask about; Tools is the
# instruments - nobody is examined on driving one. Safety is examined end
# to end (T0A, T0B, T0C) and belongs on the Lab; the instruments belong on
# the bench, and say where the exam touches them.
HOME = {"analyser": "tools", "meter": "tools", "safety": "lab"}

BENCHES = [
    {
        "key": "analyser",
        "title": "Analysers & detectors",
        "lead": "The instruments that tell you what the antenna is doing - the dedicated "
                "analyser, the field strength meter, the RF sniffer, the spectrum analyser - "
                "and what each one can and cannot say.",
        "cards": [
            {
                "title": "The SWR meter - the one you already have",
                "what": "Almost every transceiver with a meter on its face has an SWR meter "
                        "in it: switch the meter to SWR, key up, read. An in-line meter "
                        "between the radio and the feedline does the same for a rig that "
                        "does not, and for an amplifier. It reads the standing wave ratio "
                        "on the line - how much of the power is coming back.",
                "how": "A steady carrier at low power - FM, or CW with the key down, or the "
                       "rig's tune button - into the antenna, and read the meter. Read it at "
                       "the bottom, middle and top of the band; the shape says where the "
                       "antenna is happiest. Do it into the dummy load first: that should "
                       "read 1:1, and if it does not the meter or the jumper is the fault.",
                "reads": "1:1 is perfect and 1.5:1 is fine; 2:1 is where a modern rig starts "
                         "to fold its power back; 3:1 and up is a fault or an antenna for "
                         "another band. What the SWR meter cannot say is which way to cut - "
                         "2:1 from an antenna too long reads the same as 2:1 from one too "
                         "short. That is the analyser's job; the SWR meter's is the daily "
                         "glance that says nothing has changed since yesterday.",
                "why": "An SWR that was 1.3 last week and is 2.5 today is water in a "
                       "connector, a broken element, or a branch on the wire - and the "
                       "meter on the radio's face is how it gets noticed before the final "
                       "transistors do. Watching it on every band change is the cheapest "
                       "habit in the hobby.",
                "exam": ["T7C03", "T7C04", "T7C05", "T7C06", "T4A03", "T9B01"],
            },
            {
                "title": "The antenna analyser",
                "what": "A small transmitter and a bridge in one box: it puts a few milliwatts "
                        "into the antenna across a band and measures what comes back - the "
                        "resistance R, the reactance X and their sign, and from those the SWR "
                        "and the impedance. The MFJ-259 and its kin did it with a meter and a "
                        "dial; the RigExpert and the NanoVNA draw the sweep. Same measurement.",
                "how": "Connect it where the radio would be, or at the antenna's own feedpoint "
                       "if you can reach it (the feedline transforms what you see - the VNA "
                       "pane shows how). Sweep the band. Find the frequency of lowest SWR - "
                       "the dip - and read R and X there.",
                "reads": "Resonance is where X passes through zero; a good match is R near 50 "
                         "at the same place. If the dip is below the frequency you want, the "
                         "antenna is too long: cut. Above it: too short, add. Inductive "
                         "reactance (+X) at your frequency means too long; capacitive (-X) "
                         "too short. An SWR that is high everywhere is a joint, a short, or "
                         "an open, not a length. The calculator below turns an R and X into "
                         "the SWR and says which way to cut.",
                "why": "A transmitter into a mismatch heats the feedline and folds back its "
                       "power; a modern rig protects itself by folding back too, so a bad "
                       "match costs you the signal twice. The analyser lets you fix the "
                       "antenna without transmitting into it at all. But 'cut it for the "
                       "best match' is advice for an antenna with a permanent home: "
                       "resonance moves with height and with what is near the wire, so a "
                       "length trimmed here is wrong at the next campsite. In the field, "
                       "let the tuner take the reactance and think about what radiates - "
                       "height, clear ground, the pattern - rather than the dip. And a "
                       "match matters on transmit; the receiver hardly cares.",
                "exam": ["T7C01", "T7C02", "T7C03", "T7C04", "T7C06", "T9A05"],
            },
            {
                "title": "The field strength meter",
                "what": "A short whip, a diode, a capacitor and a meter - the simplest RF "
                        "instrument there is, and one you can build in an evening. It reads "
                        "how much RF is arriving at the whip, relative, uncalibrated.",
                "how": "Set it a few wavelengths from the antenna, transmit a steady carrier, "
                       "and read. Walk it round the antenna and the needle draws the pattern; "
                       "adjust the antenna and the needle says whether the change helped. Two "
                       "readings at the same spot before and after are what it is for.",
                "reads": "Only comparisons. A number on its own means nothing - the meter "
                         "does not know the distance, the height or its own sensitivity. What "
                         "it can say: the antenna radiates, which way it radiates most, and "
                         "whether this adjustment sent more of the power out than the last one.",
                "why": "Everything else about an antenna is measured at the feedpoint. This is "
                       "the one cheap way to look at the far end - to catch a beam pointing "
                       "where its rotator says it is not, or a feedline that is doing the "
                       "radiating.",
                "exam": ["T7C01", "T9A08"],
            },
            {
                "title": "The RF sniffer and the RF probe",
                "what": "A field strength meter with the whip replaced by a short probe - or "
                        "just the field strength meter held close. Where the other instrument "
                        "asks how much RF leaves the antenna, this one asks where RF is that "
                        "should not be: on the coax shield, on the microphone cable, on the "
                        "power lead, on the desk.",
                "how": "Transmit a carrier at low power and run the probe along the outside of "
                       "the coax, the mic cord, the key lead, the power cable. The needle "
                       "kicks where RF is riding the outside of a wire. A ferrite choke at the "
                       "radio end of that wire is usually the cure; move it and probe again.",
                "reads": "RF on the outside of the coax means the feedline is part of the "
                         "antenna - common-mode current - and that is what a hot microphone, "
                         "a stuttering computer and the neighbour's television are. Nothing "
                         "on the leads and trouble still: the trouble is in the air, not on "
                         "the wire.",
                "why": "Half the interference complaints an amateur ever gets are the station "
                       "hearing itself. The probe finds which wire, and the fix is a choke, "
                       "not a lower power.",
                "exam": ["T7B03", "T7B04", "T7B05", "T7B08", "T7B10"],
            },
            {
                "title": "The spectrum analyser",
                "what": "A receiver that sweeps and draws: frequency across, strength up. The "
                        "TinySA made it a hundred-dollar instrument; an SDR dongle and a "
                        "laptop make a slower one for less.",
                "how": "Into a dummy load through an attenuator - never straight from the "
                       "transmitter into the analyser's front end, which is rated for "
                       "milliwatts. Transmit and look at the second and third harmonics "
                       "against the carrier. Then, with an antenna on the analyser, look at "
                       "the band you mean to use before you use it.",
                "reads": "Harmonics should be down 40 dB or more from the carrier on HF (the "
                         "rule says 43 dB below the mean power); a harmonic that is not is a "
                         "spurious emission and a complaint waiting. On the band view: what is "
                         "occupied, what is noise, where a repeater's output is, whether that "
                         "carrier is in the band or a birdie in your own receiver.",
                "why": "A transmitter can sound fine on its own frequency and be trouble on "
                       "three others; the analyser is the only instrument that shows all of "
                       "them at once. It is also the honest answer to 'is the band dead or is "
                       "my antenna' - a look at the waterfall settles it.",
                "exam": ["T7B06", "T7B07", "T7B09", "T4A04", "T8D08"],
            },
        ],
    },
    {
        "key": "meter",
        "title": "The meter",
        "lead": "A multimeter at each point of a station, and what it ought to read - the "
                "supply, the drop along the wire, the coax, the dummy load, the battery - "
                "with the arithmetic beside it.",
        "cards": [
            {
                "title": "Volts at the supply, volts at the radio",
                "what": "A transceiver wants 13.8 V and draws twenty amps on transmit. The "
                        "supply may show 13.8; the radio sees what is left after the wire.",
                "how": "DC volts across the supply's terminals, then across the radio's power "
                       "socket, both while transmitting into a dummy load. The difference is "
                       "the drop along the wire and through its connectors.",
                "reads": "Under half a volt is a good run; a volt is a wire too thin or too "
                         "long for the current; more than that and the radio will fold back "
                         "power or drop out on transmit. Twelve gauge carries twenty amps ten "
                         "feet with a third of a volt lost; sixteen gauge loses a full volt "
                         "on the same run. The calculator below does the wire.",
                "why": "Most 'the radio cuts out on transmit' faults are a thin power lead, "
                       "and most 'the supply is bad' verdicts are a bad crimp. The meter at "
                       "both ends tells them apart in a minute.",
                "exam": ["T4A01", "T4A03", "T5A01", "T5D01", "T5D02", "T5D03"],
            },
            {
                "title": "The fuse",
                "what": "A wire that melts before the one behind it does. Rated for the "
                        "current the circuit is meant to carry, not the current it could.",
                "how": "Size it a quarter above the load's maximum draw - a 20 A rig gets a "
                       "25 A fuse - and put it in the positive lead, at the source end, so "
                       "a short anywhere along the wire is behind it. Both leads fused is "
                       "better still, and the one thing never to do is fit a bigger fuse "
                       "because the right one keeps blowing: the fuse is telling you "
                       "something.",
                "reads": "A blown fuse reads open on the continuity range; a good one, zero. "
                         "A fuse that blows again on a fresh try is a short, not a bad fuse.",
                "why": "The pool asks it straight: a 20 A fuse in a 5 A circuit lets excessive "
                       "current flow and the wire becomes the fuse - which is a fire. The "
                       "purpose of the fuse is to interrupt power in case of overload.",
                "exam": ["T0A04", "T0A05", "T0A08"],
            },
            {
                "title": "Coax, connectors, and the dummy load",
                "what": "Three things a meter can say about a feedline without any RF: is the "
                        "centre open end to end, is the centre shorted to the shield, and does "
                        "the dummy load read fifty.",
                "how": "Disconnect both ends. Ohms from centre pin to centre pin should be "
                       "near zero; centre to shield should be open (infinite). With the dummy "
                       "load on the far end, centre to shield should read about 50 ohms - the "
                       "load through the cable. A connector that reads open on the centre is "
                       "a centre pin that never made contact, the commonest fault there is.",
                "reads": "Fifty ohms through the load, zero end to end, open between: a "
                         "healthy line. Anything else is a connector nine times in ten. An "
                         "analyser does the rest - loss, and where along the line a fault is.",
                "why": "A feedline fault looks exactly like an antenna fault at the radio. "
                       "The meter separates them for nothing, before anything is climbed.",
                "exam": ["T7C05", "T7C07", "T7C09", "T7C10", "T7C11", "T9B02", "T9B03"],
            },
            {
                "title": "The battery",
                "what": "Amp-hours: how many amps for how many hours. A 20 Ah battery gives "
                        "two amps for ten hours or ten for two - less than that in the cold, "
                        "and a lead-acid battery gives up half its life if it is run flat.",
                "how": "Volts across the terminals at rest: 12.7 is a full lead-acid, 12.0 is "
                       "half, 11.8 is empty. A lithium iron phosphate pack sits at 13.2 for "
                       "most of its charge and drops off a cliff at the end. The calculator "
                       "turns the battery's amp-hours and the radio's draw into hours on the "
                       "air, receive and transmit counted separately.",
                "reads": "Receive is one amp or less; transmit is twenty, for the part of "
                         "the minute you are talking. A field day on a 20 Ah battery is a "
                         "morning of listening and an hour of transmitting, not a day.",
                "why": "The pool's battery questions are the hazards - a shorted terminal "
                       "melts a wrench, a rapid charge or discharge of an unprotected cell "
                       "can overheat or burst it. The arithmetic is what keeps the battery "
                       "the right size, so nobody is tempted to push it.",
                "exam": ["T0A01", "T0A10", "T5A06", "T6A10", "T6A11", "T4A11"],
            },
            {
                "title": "Measuring safely",
                "what": "A meter is safe on a 13.8 V supply and is not, without care, on the "
                        "mains or inside a valve amplifier, where the plate supply is two to "
                        "three thousand volts and stays there after the switch is off.",
                "how": "Use a meter rated for the voltage and the category (CAT III for "
                       "anything on the mains side). Meter leads in the right sockets before "
                       "the probes touch anything. One hand in a pocket on anything above "
                       "fifty volts, so a shock cannot cross the chest. Never switch a meter "
                       "to ohms on a live circuit. On a supply just switched off, the filter "
                       "capacitors are still charged: wait, then discharge them through a "
                       "resistor on an insulated handle before reaching in.",
                "reads": "The pool says it in three questions: guard against shock by "
                         "grounding equipment chassis; ensure the meter and leads are rated "
                         "for the voltage; a power supply's capacitors hold a charge after it "
                         "is turned off.",
                "why": "Current through the body is what kills - heating, muscle contraction, "
                       "the heart - and it takes less than a tenth of an amp. Every habit "
                       "here is about keeping the path from going through you.",
                "exam": ["T0A02", "T0A06", "T0A11", "T0A12", "T0A03"],
            },
        ],
    },
    {
        "key": "safety",
        "title": "Safety & grounding",
        "lead": "The habits that keep a station safe: one ground, bonded; lightning "
                "arrested at the entry and the feedline disconnected when it is not in "
                "use; the tower climbed by the rules; the power line never in reach.",
        "cards": [
            {
                "title": "Ground, bonded",
                "what": "Three grounds in a station - the electrical safety ground, the "
                        "lightning ground, the RF ground - and the rule that they be one: "
                        "every ground rod and earth connection bonded together, and to the "
                        "service entrance ground, with heavy conductor.",
                "how": "A ground rod at the feedline's entry, a bonding conductor from it to "
                       "the house's electrical ground, a single-point panel where the coax "
                       "comes in, and every piece of equipment bonded to that panel with "
                       "short, wide strap. Straight runs; no sharp bends in a lightning "
                       "conductor, which a strike will jump rather than follow.",
                "reads": "The pool: all external ground rods must be bonded together with "
                         "heavy wire or conductive strap; sharp bends must be avoided; the "
                         "grounding requirements are in local electrical codes.",
                "why": "Two grounds at two potentials during a strike means the difference "
                       "flows through your equipment - and through you, if you are between "
                       "them. One ground has no difference to flow.",
                "exam": ["T0A09", "T0B01", "T0B08", "T0B10", "T0B11", "T0A06"],
            },
            {
                "title": "Lightning",
                "what": "An arrester on every feedline where it enters the building, on a "
                        "grounded panel; and the plainest protection there is, which the "
                        "arrester does not replace: the feedline unplugged and grounded when "
                        "the station is not in use.",
                "how": "The arrester goes on the grounded panel where the feedline enters "
                       "the building - the pool's words - not at the radio. Ground it with "
                       "the shortest, straightest run to the bonded rod. Then the habit: a "
                       "storm forecast, or a night away, is the cable off the radio and "
                       "onto a grounded jack.",
                "reads": "An arrester that has taken a hit reads shorted or open on the "
                         "meter; replace it. A tower is grounded at its base with its own "
                         "rods, bonded to the rest.",
                "why": "Lightning does not read the arrester's rating. The arrester takes "
                       "the edge off a nearby strike's induced surge; a direct hit wants a "
                       "path to ground that does not go through the house, and no wire "
                       "into the house at all is the only protection that is certain.",
                "exam": ["T0A07", "T0B01", "T0B08", "T0B10"],
            },
            {
                "title": "The power line",
                "what": "An antenna, or a mast, or a ladder, that falls onto a power line "
                        "is how amateurs die, and it is entirely preventable by where things "
                        "are put up.",
                "how": "Site every antenna and its supports so that, if it or the mast "
                       "fell, no part could come within ten feet of a power line - the "
                       "pool's rule. That is the height of the mast plus ten feet, measured "
                       "from the base, in every direction a fall could go. Never attach "
                       "anything to a utility pole. Look up before every raise; the "
                       "calculator below does the arithmetic for a mast of a given height.",
                "reads": "Nothing to read: the line is either inside the fall radius plus "
                         "ten feet or it is not.",
                "why": "A power line is not insulated - the weathered coating is not "
                       "insulation - and contact through a wet rope, an aluminium mast or a "
                       "wire antenna is contact.",
                "exam": ["T0B06", "T0B09", "T0B04"],
            },
            {
                "title": "Noise, and what the antenna keeps company with",
                "what": "The ten-foot rule keeps you alive. This is the next thing: the "
                        "transformer on the pole, the one in the doorbell, every switching "
                        "supply, LED driver, charger and motor in the house is a noise "
                        "source, and any conductor near an antenna - the service drop, the "
                        "gutter, the metal roof, the fence - couples to it: it hears their "
                        "noise, and they detune it.",
                "how": "Put the antenna as far as you can from anything that is not "
                       "intentionally helping it, and the feedpoint furthest of all. Close "
                       "in there is a reactive near field, roughly a sixth of a wavelength "
                       "out - twenty-odd feet on 40 m, a yard on 2 m - and a conductor inside "
                       "it is part of the antenna whether you meant it or not. The "
                       "calculator below says how far that is on a band, and whether the "
                       "thing you are looking at is inside it. Beyond it, distance still "
                       "helps: noise falls off with the square of it.",
                "reads": "The one measurement that matters is the noise floor: the S-meter "
                         "with the antenna connected, against the S-meter on a dummy load, "
                         "on a quiet part of the band. Every S-unit of the difference is "
                         "noise the site is putting into the receiver, and it costs exactly "
                         "what a signal of that strength would gain you. Move the antenna, "
                         "read it again; switch the house's breakers off one by one and read "
                         "it again - that finds the culprit.",
                "why": "You cannot transmit your way out of a noisy receiver. A station that "
                       "hears S5 of noise has thrown away every signal below S5, on every "
                       "band, all the time; a station in the clear hears them all. It is "
                       "the cheapest gain there is, and it is a philosophy most people hold "
                       "and few site by.",
                "exam": ["T8C01", "T7B08", "T4B10", "G4A03"],
            },
            {
                "title": "The tower",
                "what": "A climbing harness, an observer on the ground, and a tower that "
                        "has been checked before anyone leaves the ground - and a crank-up "
                        "tower that is never climbed extended.",
                "how": "A helper or observer every time - the pool's word is never climb "
                       "without one. Harness clipped at all times, the belt's lanyard moved "
                       "one point at a time. Guy lines tensioned with turnbuckles that carry "
                       "a safety wire through them so vibration cannot unscrew them. Before "
                       "climbing: the base, the guys, the bolts, the weather.",
                "reads": "The pool: a crank-up tower must not be climbed unless it is "
                         "retracted or mechanically blocked; the safety wire keeps the "
                         "turnbuckle from loosening; guy anchors are inspected.",
                "why": "Everything on a tower is heavier than it looks and further from the "
                       "ground than it feels, and the observer is the person who calls for "
                       "help when the climber cannot.",
                "exam": ["T0B02", "T0B03", "T0B04", "T0B05", "T0B07"],
            },
            {
                "title": "RF and the body",
                "what": "The evaluation every station must be able to show is on its own "
                        "tab; this is the short version a person can carry: keep people out "
                        "of the near field of an antenna that is transmitting, and never "
                        "touch a driven element with the transmitter keyed.",
                "how": "Height and distance: an antenna above head height and away from "
                       "where people stand is nearly always compliant at amateur power. A "
                       "handheld's antenna is the exception - it is inches from the head, "
                       "so hold it away and keep the power down. An RF burn from a keyed "
                       "antenna is real and deep.",
                "reads": "The exposure tab turns your power, mode, antenna and distance into "
                         "the number the rule wants, and files it.",
                "why": "RF is non-ionising; the hazard is heating, and the limits are set so "
                       "that heating never reaches tissue. Duty cycle and time average count "
                       "in your favour; a directional antenna's gain counts against you in "
                       "the direction it points.",
                "exam": ["T0C01", "T0C02", "T0C04", "T0C05", "T0C06", "T0C08", "T0C11"],
            },
        ],
    },
]

# Copper wire, American Wire Gauge: ohms per thousand feet at room
# temperature, for the voltage-drop calculator. One way; the return doubles it.
AWG_OHMS_PER_KFT = {4: 0.2485, 6: 0.3951, 8: 0.6282, 10: 0.9989, 12: 1.588, 14: 2.525,
                    16: 4.016, 18: 6.385, 20: 10.15, 22: 16.14}


def drop_volts(gauge, feet, amps):
    """The volts lost along a two-wire DC run of this gauge and one-way
    length at this current."""
    ohms = AWG_OHMS_PER_KFT[int(gauge)] / 1000.0 * float(feet) * 2.0
    return ohms * float(amps)


def fuse_for(amps):
    """The fuse for a load: a quarter above its draw, rounded up to a size
    that exists."""
    want = float(amps) * 1.25
    for size in (1, 2, 3, 5, 7.5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100):
        if size >= want:
            return size
    return None


def battery_hours(amp_hours, receive_amps, transmit_amps, transmit_share, usable=0.8):
    """Hours a battery lasts: its usable amp-hours over the average draw,
    with the transmitter on for this share of the time."""
    draw = float(receive_amps) * (1 - float(transmit_share)) + float(transmit_amps) * float(transmit_share)
    if draw <= 0:
        return None
    return float(amp_hours) * float(usable) / draw


def near_field_ft(mhz):
    """How far the reactive near field reaches: a wavelength over two pi,
    in feet. A conductor inside it is part of the antenna."""
    import math
    wavelength_m = 299.792458 / float(mhz)
    return wavelength_m / (2 * math.pi) * 3.28084


def fall_clearance_ft(mast_height_ft, margin_ft=10.0):
    """How far a power line must be from the base of a mast: its height
    plus the pool's ten feet, so a fall cannot reach it."""
    return float(mast_height_ft) + float(margin_ft)


def analyser_reading(r, x, z0=50.0):
    """What an analyser's R and X mean: the SWR, the impedance's magnitude
    and phase, and which way to cut."""
    import math
    r, x = float(r), float(x)
    if r <= 0:
        return None
    mag = math.hypot(r, x)
    num = math.hypot(r - z0, x)
    den = math.hypot(r + z0, x)
    rho = num / den if den else 1.0
    swr = (1 + rho) / (1 - rho) if rho < 1 else float("inf")
    phase = math.degrees(math.atan2(x, r))
    if abs(x) < 3:
        cut = "resonant here - the reactance is gone; what is left is the resistance"
    elif x > 0:
        cut = "inductive: the antenna is long for this frequency - shorten it a little and sweep again"
    else:
        cut = "capacitive: the antenna is short for this frequency - add a little and sweep again"
    # Which way to cut is the arithmetic; whether to cut at all is where the
    # antenna is going to live. Resonance moves with height and with what
    # is near the wire, so a length trimmed to one site is wrong at the
    # next. Cut for a permanent home. In the field, note the number, let a
    # tuner take the reactance, and put the effort into height and clear
    # ground - what the antenna radiates matters more than what the meter
    # reads, and on receive the match matters least of all.
    where = ("If this antenna lives here, cut to it. If it travels, do not: resonance moves with height and "
             "with whatever is near the wire, so a length trimmed to this site is wrong at the next - note "
             "the reading, let the tuner take the reactance, and spend the effort on height and clear "
             "ground. A match matters on transmit; on receive it matters least of all.")
    return {"swr": round(swr, 2), "magnitude": round(mag, 1), "phase": round(phase, 1), "cut": cut, "where": where,
            "match": "a good match" if swr <= 1.5 else "usable - a tuner will take it" if swr <= 3 else
                     "a poor match - look for the fault before you cut anything"}


def for_page(page):
    """The benches that live on this page, in order."""
    return [b for b in BENCHES if HOME.get(b["key"]) == page]


def questions_for(benches, pools):
    """The pool questions the cards name, by id, with the right answer
    written out - so a card and the exam can be read side by side."""
    out = {}
    for bench in benches:
        for card in bench["cards"]:
            for qid in card.get("exam", []):
                if qid in out:
                    continue
                for pool_id, pool in pools.items():
                    q = pool.by_id.get(qid)
                    if q:
                        out[qid] = {"id": qid, "pool": pool_id, "section": q["section"], "text": q["text"],
                                    "answer_text": q["choices"][q["answer"]] if q.get("choices") else ""}
                        break
    return out
