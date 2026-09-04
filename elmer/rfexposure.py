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


# --- what the arithmetic will and will not accept ---------------------------
# A compliance record that accepts anything produces nonsense that looks
# authoritative, so impossible inputs are refused outright and merely
# implausible ones are computed but flagged in the record itself.
MIN_FREQ, MAX_FREQ = 0.1, 300000.0
MAX_POWER = 100000.0                  # beyond this is not a radio station
LEGAL_POWER = 1500.0                  # 47 CFR 97.313(a), US amateur PEP limit
MIN_GAIN, MAX_GAIN = -40.0, 40.0      # dBd; outside this is not an antenna
BIG_GAIN = 20.0                       # plausible only for a large stacked array
MIN_DISTANCE_FT = 0.1
CLOSE_FT = 1.0

AMATEUR_RANGES = [
    (0.1357, 0.1378), (0.472, 0.479), (1.8, 2.0), (3.5, 4.0), (5.33, 5.41),
    (7.0, 7.3), (10.1, 10.15), (14.0, 14.35), (18.068, 18.168), (21.0, 21.45),
    (24.89, 24.99), (28.0, 29.7), (50.0, 54.0), (144.0, 148.0), (219.0, 225.0),
    (420.0, 450.0), (902.0, 928.0), (1240.0, 1300.0), (2300.0, 2450.0),
    (3300.0, 3500.0), (5650.0, 5925.0), (10000.0, 10500.0), (24000.0, 24250.0),
]


class InvalidCase(ValueError):
    """An input the evaluation refuses to work with."""


def _number(case, key, default=None):
    value = case.get(key, default)
    if value in (None, ""):
        if default is None:
            raise InvalidCase(f"{key} is required")
        return default
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise InvalidCase(f"{key} must be a number, not {value!r}")
    if value != value or value in (float("inf"), float("-inf")):
        raise InvalidCase(f"{key} must be a real number")
    return value


def validate(case):
    """Check one case. Raises InvalidCase, or returns a list of warnings."""
    warnings = []
    f = _number(case, "frequency_mhz")
    if not MIN_FREQ <= f <= MAX_FREQ:
        raise InvalidCase(f"frequency {f:g} MHz is outside {MIN_FREQ}-{MAX_FREQ:g} MHz")
    if not any(lo <= f <= hi for lo, hi in AMATEUR_RANGES):
        warnings.append(f"{f:g} MHz is not in a US amateur band; the limits still "
                        f"apply but check the frequency")

    pep = _number(case, "pep_watts")
    if pep <= 0:
        raise InvalidCase("transmitter power must be greater than zero")
    if pep > MAX_POWER:
        raise InvalidCase(f"{pep:g} W is not a radio station")
    if pep > LEGAL_POWER:
        warnings.append(f"{pep:g} W PEP exceeds the {LEGAL_POWER:g} W US amateur "
                        f"limit of 47 CFR 97.313")

    gain = _number(case, "gain_dbd", 0.0)
    if not MIN_GAIN <= gain <= MAX_GAIN:
        raise InvalidCase(f"{gain:g} dBd is not an antenna gain; real amateur "
                          f"antennas run about -10 to +20 dBd")
    if gain > BIG_GAIN:
        warnings.append(f"{gain:g} dBd is a very large antenna - plausible only for "
                        f"a big stacked array. Check it is dBd and not dBi")

    fraction = _number(case, "transmit_fraction", 0.5)
    if not 0 <= fraction <= 1:
        raise InvalidCase("transmitting fraction must be between 0 and 1")
    if fraction == 0:
        warnings.append("a transmitting fraction of zero means no exposure at all")

    if case.get("mode") and case["mode"] not in MODE_DUTY:
        raise InvalidCase(f"unknown mode {case['mode']!r}")

    for key, who in (("distance_uncontrolled_ft", "the public"),
                     ("distance_controlled_ft", "you")):
        distance = _number(case, key, 0.0)
        if distance <= 0:
            raise InvalidCase(f"the distance to {who} must be greater than zero")
        if distance < MIN_DISTANCE_FT:
            raise InvalidCase(f"a distance of {distance:g} ft to {who} is inside "
                              f"the antenna")
        if distance < CLOSE_FT:
            warnings.append(f"{distance:g} ft to {who} is close enough to touch the "
                            f"antenna; the far-field estimate does not apply there")

    if mpe_limit(f, False) is None or mpe_limit(f, True) is None:
        raise InvalidCase(f"no MPE limit is defined at {f:g} MHz")
    return warnings


def evaluate_case(case):
    """Evaluate one band/antenna combination.

    ``case`` carries frequency_mhz, pep_watts, mode, transmit_fraction,
    gain_dbd, and the distances to the controlled and uncontrolled positions in
    feet.
    """
    warnings = validate(case)
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
        "warnings": warnings,
        "gain_source": ("modelled" if case.get("gain_source") == "modelled"
                        else "entered"),
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
    """Evaluate a whole station: several bands and antennas at once.

    One unusable row stops the whole evaluation, because a station record with
    a hole in it is worse than none - but the error names the row, so it can be
    found without hunting.
    """
    evaluated = []
    for n, case in enumerate([c for c in cases if c.get("frequency_mhz")], start=1):
        try:
            evaluated.append(evaluate_case(case))
        except InvalidCase as exc:
            where = case.get("antenna") or f"{case.get('frequency_mhz')} MHz"
            raise InvalidCase(f"band {n} ({where}): {exc}") from None
    warnings = [w for c in evaluated for w in c["warnings"]]
    return {
        "station": station,
        "cases": evaluated,
        "warnings": warnings,
        "asserted_gain": any(c["gain_source"] != "modelled" for c in evaluated),
        "compliant": all(c["compliant"] for c in evaluated) if evaluated else None,
        "method": {
            "reference": "FCC OET Bulletin 65, Supplement B; limits per 47 CFR 1.1310",
            "requirement": "47 CFR 97.13(c)",
            "reflection_field": REFLECTION_FIELD,
            "reflection_power": REFLECTION_POWER,
            "equation": "S = 0.1 x 2.56 x Pavg x G / (4 pi R^2)",
            "note": "Far-field estimate with ground reflection, treating the "
                    "antenna as a point source radiating its stated gain toward "
                    "the person. It does not model the antenna's pattern, so it "
                    "is conservative wherever the person is off the main lobe. "
                    "Distances inside the near field are flagged. The gain figure "
                    "is the largest single lever on the result, and where it was "
                    "entered by hand rather than modelled, the record says so.",
        },
    }
