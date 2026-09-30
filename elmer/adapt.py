"""The antenna you have, on the band you want.

Somebody on the Band Plan sees a band they want to work, picks a segment
inside their privileges and presses "Set up an antenna for this". The Lab
used to take the *kind* of antenna they had and redesign it from scratch
for the new band - a 234 ft V for 160 m on a 70 ft lot - and then list ways
to cram that new wire in. That is not the question a ham asks. The question
is: I have this up, cut for 40 m; how do I get it onto 160?

And there are answers hams use every week:

  - it may already work there - a 40 m dipole is resonant on 15 m;
  - lengthen it electrically: a loading coil in each leg; or tie the
    feedline together and work the whole thing as a top-loaded vertical,
    a Marconi T, against radials - the classic way a dipole gets onto 160;
  - feed it with ladder line and a tuner;
  - add wire - a link or a jumper at each end;
  - or shorten it, for a band above, with jumpers or traps.

Each is worked out for the wire that is up, with its feet and microhenries,
and with an estimate of what it gives up against a full-size antenna. That
estimate is the second half of the answer: a compromise 10 dB down is
marginal on SSB and comfortable on CW and FT8. So the modes the operator may
use there are read against the path - to where they are trying to reach,
now and after dark - and the other bands in their privileges where the
antenna they have already works are offered too, ranked by what is open.

The losses are estimates from standard approximations - a short antenna's
radiation resistance against a coil of Q about 200 and a modest radial
field - said as starting figures, never as measurements.
"""
import logging
import math

from . import antenna_advice as A
from . import bandplan, propagation

log = logging.getLogger("elmer")

# A band's reference frequency, for "cut for": where somebody cuts a wire
# for that band, near its middle. The Lab and the Band Plan offer these.
CUT_FOR = {
    "160m": 1.900, "80m": 3.750, "60m": 5.357, "40m": 7.150, "30m": 10.125,
    "20m": 14.200, "17m": 18.118, "15m": 21.200, "12m": 24.940, "10m": 28.400,
    "6m": 50.125, "2m": 146.000,
}

# What a coil loses: its reactance over its Q. A good air-wound coil on the
# low bands is about 200; a tuner's inductor, working harder, about 100.
COIL_Q = 200.0
TUNER_Q = 100.0
# Ground loss under a vertical: a handful of radials on the grass. Every
# radial added brings it down; a full field of them to about 5.
GROUND_OHMS = 15.0
# The wire's own loss, ohms, near enough for #14 on HF.
WIRE_OHMS = 1.0

# Where somebody is reaching, when they have not said: the use's distance.
USE_KM = {"regional": 400.0, "dx": 6000.0, "digital": 1500.0, "portable": 400.0}
DEFAULT_KM = 800.0

# Modes by the emission the privileges name: phone, CW, data.
MODES = (("ft8", "FT8", "data"), ("cw", "CW", "cw"), ("ssb", "SSB", "phone"))
NIGHT_SUN_DEG = -18.0

# The antennas this knows how to adapt, and what kind of wire each is.
WIRES = {"dipole": 468.0, "bowtie": 468.0, "invertedv": A.V_CUT, "efhw": 468.0}
VERTICALS = {"quarter": 234.0, "groundplane": 234.0}


def band_of(mhz):
    b = bandplan.band_at(float(mhz))
    return b["name"].replace(" ", "") if b else None


def _db(eff):
    return 10.0 * math.log10(max(1e-6, min(1.0, eff)))


def _short_dipole_loss(mhz, overall_ft, q):
    """A dipole shorter than a half wave, centre-loaded with a coil in each
    leg: its radiation resistance against the coils' loss, in dB."""
    lam = A.wavelength_ft(mhz)
    rr = 20.0 * math.pi ** 2 * (overall_ft / lam) ** 2
    uh = A.loading_uh(mhz, overall_ft / 2.0)
    if uh is None:
        return 0.0, None
    x = 2.0 * math.pi * mhz * uh
    return _db(rr / (rr + 2.0 * x / q + WIRE_OHMS)), uh


def _vertical_loss(mhz, height_ft, extra_ft=0.0):
    """A short vertical, top-loaded by `extra_ft` of equivalent length, base
    coil to resonance, over a handful of radials: its loss in dB and the
    coil it wants. A top hat keeps the current up the whole vertical, which
    is what makes a short one worth having."""
    lam = A.wavelength_ft(mhz)
    loaded = extra_ft > 0
    rr = (160.0 if loaded else 40.0) * math.pi ** 2 * (height_ft / lam) ** 2
    uh = A.loading_uh(mhz, height_ft + extra_ft)
    x = 2.0 * math.pi * mhz * uh if uh else 0.0
    return _db(rr / (rr + GROUND_OHMS + x / COIL_Q + WIRE_OHMS)), uh


def ways(kind, cut_mhz, want_mhz, height_ft=None, room_ft=None):
    """How to get the antenna that is up onto this frequency, each with its
    estimated cost in dB against a full-size antenna. A list of
    {"lead", "text", "loss_db"}; the first entries are the best."""
    cut_mhz, want_mhz = float(cut_mhz), float(want_mhz)
    key = band_of(want_mhz)
    # Said as the rest of ELMER says a band: "160 m".
    band = _spaced(key) if key else f"{want_mhz:g} MHz"
    cut_band = _spaced(band_of(cut_mhz)) if band_of(cut_mhz) else f"{cut_mhz:g} MHz"
    out = []
    # Already resonant there?
    for hm in A.harmonics(kind, cut_mhz) if kind in A.HARMONIC_SERIES else []:
        if hm.get("band") and _band_key(hm["band"]) == key:
            out.append({"lead": "It already works here.",
                        "text": f"A {cut_band} {A.TYPES.get(kind, {}).get('label', kind).lower()} is resonant "
                                f"on {band} too, near {hm['mhz']:.3f} MHz - its {A._ordinal(hm['n'])} harmonic. "
                                "Feed it as it is; the pattern breaks into more lobes than on "
                                f"{cut_band}, which is often a gain in some directions.",
                        "loss_db": 0.0})
            return out

    if kind in WIRES:
        k = WIRES[kind]
        overall = k / cut_mhz                       # the wire that is up
        full = k / want_mhz                         # the wire this band wants
        if want_mhz < cut_mhz:
            # Lower: lengthen it, electrically or with wire.
            if kind != "efhw" and height_ft:
                top = overall * (math.cos(math.radians(A.DEFAULT_DROOP_DEG)) if kind == "invertedv" else 1.0)
                loss, uh = _vertical_loss(want_mhz, float(height_ft), extra_ft=top / 2.0)
                coil = (f"about {uh:.0f} µH of base coil" if uh
                        else "a series capacitor or the tuner, since the T is long enough by itself")
                out.append({"lead": "Feed it as a Marconi T.",
                            "text": f"Short the feedline's centre and braid together where it reaches the "
                                    f"ground, and feed that against radials or a ground rod and "
                                    f"counterpoise: the {float(height_ft):.0f} ft down-lead is a vertical, "
                                    f"and the {overall:.0f} ft of wire at the top is its top hat. It wants "
                                    f"{coil} to resonate on {band}, as a starting figure to trim. This is "
                                    f"the classic way a {cut_band} dipole gets onto {band}, and the dipole "
                                    f"still works as it is on {cut_band} - switch the bottom of the feedline.",
                            "loss_db": round(loss, 1)})
            loss, uh = _short_dipole_loss(want_mhz, overall, COIL_Q)
            if uh:
                out.append({"lead": "Load it.",
                            "text": f"Put a coil in each leg of the {overall:.0f} ft that is up - about "
                                    f"{uh:.0f} µH at the feed end of each, as a starting figure; moved out "
                                    f"along the leg it needs more and radiates better. On {band} the wire is "
                                    f"{overall / A.wavelength_ft(want_mhz):.2f} of a wavelength, so it is "
                                    "narrow and gives up some signal, and it works.",
                            "loss_db": round(loss, 1)})
            extra = (full - overall) / (1.0 if kind == "efhw" else 2.0)
            bend = (f" - bent down the support or along the fence where your {room_ft:.0f} ft runs out"
                    if room_ft and full > room_ft else "")
            out.append({"lead": "Add wire.",
                        "text": f"A link or a jumper at {'the far end' if kind == 'efhw' else 'each end'}, "
                                f"{extra:.0f} ft of wire{'' if kind == 'efhw' else ' each side'}, makes it a "
                                f"full-size {band} antenna{bend}; open the links and it is your {cut_band} "
                                "antenna again.",
                        # Bent, it gives up a little: the ends still radiate, in
                        # other directions and polarisations, so an estimate
                        # of up to 3 dB as the straight part shrinks.
                        "loss_db": 0.0 if not bend else -3.0 * (1.0 - min(1.0, room_ft / full))})
            tuner_loss, _ = _short_dipole_loss(want_mhz, overall, TUNER_Q)
            short = overall / A.wavelength_ft(want_mhz) < 0.25
            out.append({"lead": "Feed it with ladder line and a tuner.",
                        "text": ("Ladder line all the way to a tuner in the shack, or a remote tuner at "
                                 "the feed point. " +
                                 (f"At {overall / A.wavelength_ft(want_mhz):.2f} of a wavelength it is short "
                                  f"for {band}, so the tuner works hard and more of the power goes into its "
                                  "coil - it will make contacts, and the Marconi T or coils do it better."
                                  if short else
                                  f"At {overall / A.wavelength_ft(want_mhz):.2f} of a wavelength it takes a "
                                  "tuner comfortably, and this is how one wire covers several bands.")),
                        "loss_db": round(tuner_loss if short else -1.0, 1)})
        else:
            # Higher: shorten it, or feed it as a doublet.
            leg = full / (1.0 if kind == "efhw" else 2.0)
            out.append({"lead": "Shorten it with jumpers or traps.",
                        "text": f"Open a link {leg:.1f} ft {'from the feed' if kind == 'efhw' else 'out from the centre on each leg'} "
                                f"and it is a {band} antenna; close it for {cut_band}. Traps do the same "
                                "without climbing: a parallel-tuned trap at that point, resonant on "
                                f"{band}, and the wire beyond it serves {cut_band}.",
                        "loss_db": 0.0})
            out.append({"lead": "Feed it with ladder line and a tuner.",
                        "text": f"Longer than a half wave on {band}, it takes a tuner comfortably on ladder "
                                "line - the pattern breaks into lobes, stronger in some directions and "
                                "weaker in others.",
                        "loss_db": -1.0})
    elif kind in VERTICALS:
        up = VERTICALS[kind] / cut_mhz
        if want_mhz < cut_mhz:
            loss, uh = _vertical_loss(want_mhz, up)
            out.append({"lead": "Load it at the base.",
                        "text": f"The {up:.0f} ft radiator wants about {uh:.0f} µH at its base on {band}, "
                                "as a starting figure. A capacitance hat at the top - a few spokes of wire - "
                                "cuts the coil and the loss a good deal. Add radials: on a short vertical they "
                                "are most of the efficiency.",
                        "loss_db": round(loss, 1)})
        else:
            out.append({"lead": "Feed it through a tuner at the base.",
                        "text": f"The {up:.0f} ft radiator is longer than a quarter wave on {band}; a tuner at "
                                "the base matches it, and up to about five-eighths of a wave it fires lower "
                                "than the quarter wave did.",
                        "loss_db": -1.0})
    for w in out:
        w["loss_db"] = min(0.0, w["loss_db"])
    out.sort(key=lambda w: -w["loss_db"])
    return out


def _allowed_modes(band, license_class):
    """The modes of MODES this class may use somewhere on this band."""
    cls = license_class or "Technician"
    have = set()
    for _, _, terms in bandplan.privileges_for(_spaced(band), cls) or []:
        have |= set(bandplan.emissions_in(terms))
    return [(m, label) for m, label, em in MODES if em in have]


def _band_key(name):
    return (name or "").replace(" ", "")


def _spaced(name):
    """"160m" as the band plan writes it, "160 m"."""
    import re
    return re.sub(r"^([0-9.]+)\s*(c?m)$", r"\g<1> \g<2>", name or "")


def _rows(km, snap, emission, watts, night=False):
    return {_band_key(r["band"]): r for r in propagation.path_bands(
        km, fof2=snap.get("fof2"), hmf2=snap.get("hmf2") or propagation.HMF2_DEFAULT,
        elevation=NIGHT_SUN_DEG if night else (snap.get("elevation") or 0.0),
        k_index=snap.get("k_index") or 2.0, muf=None if night else snap.get("muf"),
        watts=watts, emission=emission)["bands"]}


def _verdict(margin):
    if margin is None:
        return "closed"
    if margin >= propagation.SKY_SOLID_DB:
        return "solid"
    if margin >= propagation.SKY_WORKABLE_DB:
        return "workable"
    if margin >= 0:
        return "marginal"
    return "short"


def plan(want_mhz, kind, cut_mhz, height_ft=None, site=None, license_class=None, watts=100.0,
         km=None, reach_said=None, use=None, snap=None):
    """Everything above, for the Lab: None when the antenna is cut for the
    band asked about (the ordinary case), or is a kind this cannot adapt."""
    try:
        want_mhz, cut_mhz = float(want_mhz), float(cut_mhz)
    except (TypeError, ValueError):
        return None
    want_band, cut_band = band_of(want_mhz), band_of(cut_mhz)
    if not want_band or not cut_band or want_band == cut_band:
        return None
    if kind not in WIRES and kind not in VERTICALS:
        return None
    room = A.room_ft(site) if site else None
    found = ways(kind, cut_mhz, want_mhz, height_ft, room)
    if not found:
        return None
    best = found[0]["loss_db"]
    out = {"want": {"mhz": want_mhz, "band": want_band}, "cut": {"mhz": cut_mhz, "band": cut_band},
           "ways": found, "best_loss_db": best}
    if not snap or km is None:
        km = km if km is not None else USE_KM.get(use or "", DEFAULT_KM)
    out["target"] = {"km": round(km), "said": reach_said or None, "use": use}
    if not snap:
        return out
    try:
        modes, bands = [], {}
        allowed_here = _allowed_modes(want_band, license_class)
        for m, label, _em in MODES:
            now = _rows(km, snap, m, watts)
            night = _rows(km, snap, m, watts, night=True)
            if (m, label) in allowed_here:
                r, n = now.get(want_band) or {}, night.get(want_band) or {}
                mn = (r.get("budget") or {}).get("margin_db")
                mt = (n.get("budget") or {}).get("margin_db")
                modes.append({"mode": m, "label": label,
                              "now": _verdict(None if mn is None else mn + best),
                              "now_db": None if mn is None else round(mn + best),
                              "night": _verdict(None if mt is None else mt + best),
                              "night_db": None if mt is None else round(mt + best)})
            bands[m] = now
        out["modes"] = modes
        # Other bands in the privileges where the antenna that is up works as
        # it is - its own band and its harmonics - or nearly, and the path is
        # open now, best first.
        as_is = {cut_band} | {_band_key(h["band"]) for h in A.harmonics(kind, cut_mhz)
                              if kind in A.HARMONIC_SERIES and h.get("band")}
        others = []
        for name in bands.get("ssb", {}):
            if name in (want_band, "11m"):
                continue
            allowed = _allowed_modes(name, license_class)
            if not allowed:
                continue
            here = name in as_is
            cost = 0.0 if here else (ways(kind, cut_mhz, CUT_FOR.get(name, 0) or bands["ssb"][name]["mhz"],
                                          height_ft, room) or [{"loss_db": -30.0}])[0]["loss_db"]
            # Every mode that makes it, not only the one with most margin -
            # which is FT8 every time, and somebody asking about SSB wants
            # to know SSB goes too.
            got = []
            for m, label in allowed:
                row = bands.get(m, {}).get(name) or {}
                mg = (row.get("budget") or {}).get("margin_db")
                if row.get("works") and mg is not None and mg + cost >= 0:
                    got.append({"mode": label, "margin_db": round(mg + cost), "verdict": _verdict(mg + cost)})
            if got:
                others.append({"band": name, "as_is": here, "cost_db": round(cost, 1), "modes": got,
                               "margin_db": max(g["margin_db"] for g in got)})
        others.sort(key=lambda o: (not o["as_is"], -len(o["modes"]), -o["margin_db"]))
        out["bands"] = others[:4]
    except (KeyError, TypeError, ValueError) as exc:
        log.warning("adapt: could not read the path for %s: %s", want_band, exc)
    return out
