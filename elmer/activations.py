"""Whether the day out you are planning will actually count, and why not.

Parks on the Air and Summits on the Air are the two things that get people to
carry a radio somewhere, and both are programmes with rules rather than games
with vibes. The rules are short, they are public, and almost every wasted trip
comes from not having read them - somebody works ten stations through the
repeater on the hill and finds that none of the ten counted, or drives to the
trailhead, operates off the car battery a hundred metres below the top, and
learns afterwards that neither the vehicle nor the position was allowed.

That is the failure this module exists to prevent, and it is a planning
failure. It happens at the kitchen table, days early, where it is free to fix.
So this asks the question in that direction: given the programme, the licence
and what the operator intends to carry, what will count, what will not, and
what has to change before anybody leaves.

Two things are worth noticing about the rules themselves, because they are
not arbitrary and knowing why makes them stick.

**Neither programme counts a terrestrial repeater, and both count a
satellite.** The point of the exercise is the path you made, not the machine
somebody else put on a hill - and a satellite is a repeater nobody can stand
between you and, which is the same reason it is worth trying from a valley.

**SOTA does not let the vehicle near the station.** Not the battery, not the
whip, not the parking space: "no part of the station may be connected in any
way with the motor vehicle". Everything is carried up. A programme that is
about what you can carry has to be, or it measures the road instead.

The rules below are transcribed from the programmes' own documents, with the
issue and date they were read from, because this is the one part of ELMER
that goes stale by somebody else's decision rather than by physics. Where a
figure is set per-association rather than globally - SOTA's vertical distance
is the one that matters - it is stated as the typical value and labelled as
the local Association Manager's to set.
"""

# Both programmes, as data. `source` and `read` are part of the record: an
# operator relying on a rule is entitled to know which document said so and
# how old this copy of it is.
POTA = {
    "key": "pota",
    "name": "Parks on the Air",
    "source": "docs.pota.app/docs/rules.html",
    "read": "2026-09-09",
    "qualifies": 10,
    "qualifies_note": "Ten QSOs from the park inside one UTC day make a "
                      "valid activation. Sessions split across the day add "
                      "up; the same park twice in one UTC day is still one "
                      "activation.",
    "where": "The activator and all of the equipment must be inside the "
             "park's boundary, on public property. Not the car park across "
             "the road, and not the far side of the fence.",
    "power": "No rule about it. A vehicle battery is fine, and so is the "
             "vehicle.",
    "vehicle": True,
    "repeaters": False,
    "satellites": True,
    "self_spot": "Allowed and normal - spotting yourself on the POTA page is "
                 "how hunters find you, and a spot ages out about half an "
                 "hour after the last update.",
    "again": "Once per park per UTC day, however many sessions it took.",
}

SOTA = {
    "key": "sota",
    "name": "Summits on the Air",
    "source": "SOTA General Rules S0.1, issue 1.20, 30 Mar 2015, rule 3.7.1",
    "read": "2026-09-09",
    "qualifies": 4,
    "qualifies_note": "One QSO makes it an activation. Four QSOs, each with "
                      "a different station, are what the summit's points "
                      "want - and a contact with somebody else inside the "
                      "same activation zone is not one of them.",
    "where": "The operating position - meaning where the operator is, not "
             "where the antenna is - must be inside the activation zone: "
             "the closed contour a set vertical distance below the top. "
             "Typically 25 metres, but each Association sets its own and "
             "the local Association Manager is the authority on it.",
    "power": "Batteries or solar, carried up with everything else. "
             "Permanently installed supplies and fossil-fuel generators of "
             "any kind are expressly forbidden.",
    "vehicle": False,
    "repeaters": False,
    "satellites": True,
    "self_spot": "Allowed. SOTAwatch is the spotting side, and an alert "
                 "posted the night before is what gets chasers listening at "
                 "the right hour.",
    "again": "A summit may be activated as often as you like, but an "
             "operator claims its points once per calendar year. A later "
             "activation still collects a seasonal bonus if one has opened.",
}

PROGRAMS = {p["key"]: p for p in (POTA, SOTA)}

# What each thing on the Make Contact gear list is worth on an activation.
# `pota` and `sota` are the verdicts; the reason is written once and shared,
# because the operator is owed the rule rather than a yes or a no.
GEAR_VERDICTS = {
    "ht": {
        "pota": "counts", "sota": "counts",
        "note": "A handheld is a real activation radio and 2 m FM simplex "
                "activations happen constantly - but the repeater on the "
                "hill counts for neither programme, so it is 146.520 and "
                "calling, not the machine. The satellites and the ISS "
                "digipeater do count, in both.",
    },
    "mobile_vhf": {
        "pota": "counts", "sota": "forbidden",
        "note": "Fine in a park, where operating from the vehicle is "
                "ordinary. On a summit the vehicle is the disqualification: "
                "no part of the station may be connected to it in any way, "
                "and the station may not even be in its close vicinity.",
    },
    "hf_mobile": {
        "pota": "counts", "sota": "forbidden",
        "note": "A whip on the car is a park antenna, not a summit one. "
                "SOTA wants everything carried up and run off a battery you "
                "carried with it.",
    },
    "hf_wire": {
        "pota": "counts", "sota": "counts",
        "note": "The one that works for both, and the reason a wire and a "
                "few ounces of battery is the classic summit station.",
    },
    "gmrs": {
        "pota": "no credit", "sota": "no credit",
        "note": "Not amateur radio, so no credit in either programme. It "
                "will still reach somebody, which is a different and "
                "sometimes more important question.",
    },
}

VERDICT_RANK = {"forbidden": 0, "no credit": 1, "counts": 2}


def program(key):
    """One programme's rules, or None if that is not one of them."""
    return PROGRAMS.get((key or "").lower())


def gear_report(key, gear):
    """What each thing the operator is carrying is worth, worst news first.

    Sorted so the disqualifying item is at the top, because that is the one
    that changes what somebody packs and there is no point burying it under
    three things that are fine.
    """
    prog = program(key)
    if prog is None:
        return []
    rows = []
    for item in gear or ():
        verdict = GEAR_VERDICTS.get(item)
        if verdict is None:
            continue
        rows.append({"key": item, "verdict": verdict[prog["key"]],
                     "note": verdict["note"]})
    return sorted(rows, key=lambda r: VERDICT_RANK.get(r["verdict"], 3))


def blockers(key, gear):
    """The things in this plan that would invalidate the activation."""
    return [r for r in gear_report(key, gear) if r["verdict"] == "forbidden"]
