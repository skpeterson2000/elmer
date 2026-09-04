"""RF exposure (MPE) station evaluation, per FCC OET Bulletin 65 Supplement B.

Since the 2021 rule change every amateur station must perform an RF exposure
evaluation and be able to show it - 47 CFR 97.13(c), against the limits in
47 CFR 1.1310.  This module does the arithmetic that evaluation needs and
returns every intermediate value, because a compliance record that shows only
its conclusion is not much of a record.

The maths is deliberately the conservative form the bulletin recommends for
amateur use: far-field power density with a ground-reflection factor of 1.6 on
field strength, which is 2.56 on power density.  Where a distance falls inside
the near field the estimate is flagged rather than quietly reported, since the
far-field equation overstates nothing there but does stop being exact.
"""
import math

# --- 47 CFR 1.1310, limits in mW/cm^2, f in MHz ------------------------------
# Controlled/occupational is averaged over 6 minutes, uncontrolled/general
# population over 30 minutes.


def mpe_limit(f_mhz, controlled):
    """Maximum permissible exposure in mW/cm^2 at this frequency."""
    f = float(f_mhz)
    if controlled:
        if f < 0.3:
            return None
        if f < 3.0:
            return 100.0
        if f < 30.0:
            return 900.0 / (f * f)
        if f < 300.0:
            return 1.0
        if f < 1500.0:
            return f / 300.0
        if f <= 100000.0:
            return 5.0
        return None
    if f < 0.3:
        return None
    if f < 1.34:
        return 100.0
    if f < 30.0:
        return 180.0 / (f * f)
    if f < 300.0:
        return 0.2
    if f < 1500.0:
        return f / 1500.0
    if f <= 100000.0:
        return 1.0
    return None


AVERAGING_MINUTES = {True: 6, False: 30}

# Fraction of transmit time the carrier is actually at full power.
MODE_DUTY = {
    "ssb": ("SSB voice, no processing", 0.20),
    "ssb_proc": ("SSB voice, heavy processing", 0.50),
    "am": ("AM voice", 0.30),
    "fm": ("FM voice", 1.00),
    "cw": ("CW", 0.40),
    "rtty": ("RTTY / FSK", 1.00),
    "digital": ("FT8, PSK, other digital", 1.00),
    "carrier": ("Continuous carrier / tune", 1.00),
}

REFLECTION_FIELD = 1.6          # OET-65 ground reflection factor on field
REFLECTION_POWER = REFLECTION_FIELD ** 2      # 2.56 on power density
FT_PER_M = 3.280839895


def dbd_to_dbi(dbd):
    return dbd + 2.15


def power_density(avg_watts, gain_dbi, metres, reflection=True):
    """Far-field power density in mW/cm^2 at a distance."""
    if metres <= 0:
        return float("inf")
    gain = 10 ** (gain_dbi / 10.0)
    factor = REFLECTION_POWER if reflection else 1.0
    # W/m^2 -> mW/cm^2 is a factor of 0.1
    return 0.1 * factor * avg_watts * gain / (4 * math.pi * metres * metres)


def compliance_distance(avg_watts, gain_dbi, limit, reflection=True):
    """The distance at which power density falls to the limit, in metres."""
    if limit is None or limit <= 0 or avg_watts <= 0:
        return None
    gain = 10 ** (gain_dbi / 10.0)
    factor = REFLECTION_POWER if reflection else 1.0
    return math.sqrt(0.1 * factor * avg_watts * gain / (4 * math.pi * limit))


def near_field_boundary(f_mhz, aperture_m=None):
    """Roughly where the far field begins, for flagging estimates.

    Uses 2D^2/lambda when an aperture is known, otherwise lambda/(2*pi), which
    is the usual reactive near-field boundary for a small antenna.
    """
    lam = 299.792458 / float(f_mhz)
    if aperture_m:
        return max(2 * aperture_m * aperture_m / lam, lam / (2 * math.pi))
    return lam / (2 * math.pi)


def evaluate_case(case):
    """Evaluate one band/antenna combination.

    ``case`` carries frequency_mhz, pep_watts, mode, transmit_fraction,
    gain_dbd, and the distances to the controlled and uncontrolled positions in
    feet.
    """
    f = float(case["frequency_mhz"])
    pep = float(case["pep_watts"])
    mode = case.get("mode", "ssb")
    mode_label, mode_duty = MODE_DUTY.get(mode, MODE_DUTY["ssb"])
    tx_fraction = float(case.get("transmit_fraction", 0.5))
    gain_dbd = float(case.get("gain_dbd", 0.0))
    gain_dbi = dbd_to_dbi(gain_dbd)

    duty = mode_duty * tx_fraction
    avg = pep * duty

    rows = []
    for controlled in (False, True):
        limit = mpe_limit(f, controlled)
        distance_ft = float(case.get("distance_controlled_ft" if controlled
                                     else "distance_uncontrolled_ft", 0) or 0)
        metres = distance_ft / FT_PER_M
        density = power_density(avg, gain_dbi, metres) if metres > 0 else None
        safe_m = compliance_distance(avg, gain_dbi, limit)
        boundary = near_field_boundary(f, case.get("aperture_m"))
        rows.append({
            "environment": "Controlled / occupational" if controlled
                           else "Uncontrolled / general population",
            "controlled": controlled,
            "averaging_minutes": AVERAGING_MINUTES[controlled],
            "limit": limit,
            "distance_ft": distance_ft,
            "distance_m": round(metres, 3) if metres else 0.0,
            "density": density,
            "margin_ratio": (density / limit) if (density and limit) else None,
            "compliant": (density is not None and limit is not None
                          and density <= limit),
            "compliance_distance_m": safe_m,
            "compliance_distance_ft": (safe_m * FT_PER_M) if safe_m else None,
            "near_field": bool(metres and metres < boundary),
            "near_field_boundary_ft": boundary * FT_PER_M,
        })

    return {
        "frequency_mhz": f, "band": band_for(f),
        "pep_watts": pep, "mode": mode, "mode_label": mode_label,
        "mode_duty": mode_duty, "transmit_fraction": tx_fraction,
        "duty_cycle": duty, "average_watts": round(avg, 2),
        "gain_dbd": gain_dbd, "gain_dbi": round(gain_dbi, 2),
        "antenna": case.get("antenna", ""),
        "results": rows,
        "compliant": all(r["compliant"] for r in rows),
    }


BANDS = [
    (0.135, 0.138, "2200 m"), (0.472, 0.479, "630 m"), (1.8, 2.0, "160 m"),
    (3.5, 4.0, "80 m"), (5.3, 5.4, "60 m"), (7.0, 7.3, "40 m"),
    (10.1, 10.15, "30 m"), (14.0, 14.35, "20 m"), (18.068, 18.168, "17 m"),
    (21.0, 21.45, "15 m"), (24.89, 24.99, "12 m"), (28.0, 29.7, "10 m"),
    (50.0, 54.0, "6 m"), (144.0, 148.0, "2 m"), (222.0, 225.0, "1.25 m"),
    (420.0, 450.0, "70 cm"), (902.0, 928.0, "33 cm"), (1240.0, 1300.0, "23 cm"),
]


def band_for(f_mhz):
    for lo, hi, name in BANDS:
        if lo <= f_mhz <= hi:
            return name
    return f"{f_mhz:g} MHz"


def evaluate(station, cases):
    """Evaluate a whole station: several bands and antennas at once."""
    evaluated = [evaluate_case(c) for c in cases if c.get("frequency_mhz")]
    return {
        "station": station,
        "cases": evaluated,
        "compliant": all(c["compliant"] for c in evaluated) if evaluated else None,
        "method": {
            "reference": "FCC OET Bulletin 65, Supplement B; limits per 47 CFR 1.1310",
            "requirement": "47 CFR 97.13(c)",
            "reflection_field": REFLECTION_FIELD,
            "reflection_power": REFLECTION_POWER,
            "equation": "S = 0.1 x 2.56 x Pavg x G / (4 pi R^2)",
            "note": "Far-field estimate with ground reflection. Conservative for "
                    "amateur installations; distances inside the near field are "
                    "flagged.",
        },
    }
