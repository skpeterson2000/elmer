"""Transmission lines, and the chart that makes them make sense.

A Smith chart is hard to learn from a book because it is not a picture, it is a
transformation: what teaches it is watching the point move when you change the
line. So this computes the movement - the load impedance, where it lands on the
chart, and the path it walks as you travel along the feedline towards the shack
- and leaves the drawing to the page.

The chart is the reflection coefficient plane. Every impedance normalised to the
line's own Z0 maps to a point inside the unit circle; the centre is a perfect
match, the rim is total reflection. Constant-resistance circles and
constant-reactance arcs are the grid drawn over it. Travelling along a lossless
line rotates you about the centre at constant radius - which is why SWR does not
change along a perfect line - and a full turn is half a wavelength, not a whole
one, which is the fact that surprises everybody.

Loss makes the rotation a spiral inward. That is worth seeing rather than being
told, because it is the mechanism behind the thing that fools people: a long run
of lossy coax shows a flatter SWR at the shack than at the antenna, and the
improvement is your power being turned into heat on the way back.

Line constants are the usual two-term fit, matched loss in dB per 100 ft as
k1*sqrt(f) + k2*f with f in MHz - the first term is conductor loss, the second
dielectric. They are typical figures for the type rather than measurements of
your reel.
"""
import cmath
import math

# name -> Z0 in ohms, velocity factor, k1 (conductor), k2 (dielectric)
LINES = {
    "rg58":    {"label": "RG-58 (thin, common, lossy)", "z0": 50.0, "vf": 0.66,
                "k1": 0.4576, "k2": 0.0034},
    "rg8x":    {"label": "RG-8X (mini-8)", "z0": 50.0, "vf": 0.82,
                "k1": 0.3374, "k2": 0.0018},
    "rg213":   {"label": "RG-213 (full size)", "z0": 50.0, "vf": 0.66,
                "k1": 0.2035, "k2": 0.0006},
    "lmr400":  {"label": "LMR-400 (low loss)", "z0": 50.0, "vf": 0.85,
                "k1": 0.1220, "k2": 0.0002},
    "rg6":     {"label": "RG-6 (75 ohm, TV coax)", "z0": 75.0, "vf": 0.83,
                "k1": 0.2000, "k2": 0.0009},
    "ladder":  {"label": "450 ohm window line", "z0": 450.0, "vf": 0.91,
                "k1": 0.0271, "k2": 0.0002},
}

C_FT = 983.571                     # feet per microsecond


def matched_loss_db(line, mhz, feet):
    """Loss of the line when it is matched, in dB - before any SWR penalty."""
    spec = LINES[line]
    per_100 = spec["k1"] * math.sqrt(mhz) + spec["k2"] * mhz
    return per_100 * feet / 100.0


def reflection(z, z0):
    """The reflection coefficient of an impedance against a line."""
    z = complex(z)
    return (z - z0) / (z + z0) if (z + z0) != 0 else complex(1, 0)


def swr_from(gamma):
    mag = abs(gamma)
    if mag >= 0.999999:
        return float("inf")
    return (1 + mag) / (1 - mag)


def return_loss_db(gamma):
    mag = abs(gamma)
    return float("inf") if mag == 0 else -20 * math.log10(mag)


def mismatch_loss_db(gamma):
    """Power not accepted by the load, in dB."""
    mag2 = abs(gamma) ** 2
    return float("inf") if mag2 >= 1 else -10 * math.log10(1 - mag2)


def wavelength_ft(mhz, vf):
    return C_FT * vf / mhz


def _gamma_per_ft(line, mhz):
    """Propagation constant: nepers and radians per foot."""
    spec = LINES[line]
    db_per_ft = matched_loss_db(line, mhz, 1.0)
    alpha = db_per_ft / 8.685889638          # dB to nepers
    beta = 2 * math.pi / wavelength_ft(mhz, spec["vf"])
    return complex(alpha, beta)


def transform(z_load, line, mhz, feet):
    """The impedance seen `feet` back from a load, through this line.

    The standard lossy-line transform. With no loss it reduces to the rotation
    everybody draws on the chart; with loss it spirals in, which is the part
    that explains why a bad feedline flatters your SWR meter.
    """
    spec = LINES[line]
    z0 = spec["z0"]
    if feet <= 0:
        return complex(z_load)
    t = cmath.tanh(_gamma_per_ft(line, mhz) * feet)
    return z0 * (complex(z_load) + z0 * t) / (z0 + complex(z_load) * t)


def walk(z_load, line, mhz, feet, steps=240):
    """The path from the antenna back to the shack, as chart coordinates.

    Each point is the reflection coefficient at that distance, which is where
    the chart puts it: x to the right, y up, the unit circle as the rim.
    """
    z0 = LINES[line]["z0"]
    out = []
    for n in range(steps + 1):
        at = feet * n / steps
        g = reflection(transform(z_load, line, mhz, at), z0)
        out.append({"ft": round(at, 3), "x": round(g.real, 5), "y": round(g.imag, 5)})
    return out


def analyse(r, x, line, mhz, feet, tx_watts=100.0):
    """Everything the chart needs to say, for one antenna on one feedline."""
    spec = LINES[line]
    z0 = spec["z0"]
    z_load = complex(float(r), float(x))
    g_load = reflection(z_load, z0)
    swr_ant = swr_from(g_load)

    z_in = transform(z_load, line, mhz, feet)
    g_in = reflection(z_in, z0)
    swr_shack = swr_from(g_in)

    matched = matched_loss_db(line, mhz, feet)
    # Total loss on a mismatched line, from the standard SWR-loss relation.
    a = 10 ** (matched / 10.0)
    p = abs(g_load) ** 2
    total = (10 * math.log10((a * a - p) / (a * (1 - p)))
             if a * (1 - p) > 0 and (a * a - p) > 0 else matched)

    lam = wavelength_ft(mhz, spec["vf"])
    return {
        "line": line, "line_label": spec["label"], "z0": z0, "vf": spec["vf"],
        "mhz": mhz, "feet": feet,
        "wavelength_ft": round(lam, 2),
        "electrical_wavelengths": round(feet / lam, 4) if lam else 0,
        "load": {"r": round(z_load.real, 2), "x": round(z_load.imag, 2),
                 "swr": round(swr_ant, 3) if swr_ant != float("inf") else None,
                 "gamma_mag": round(abs(g_load), 4),
                 "gamma_deg": round(math.degrees(cmath.phase(g_load)), 1),
                 "return_loss_db": (round(return_loss_db(g_load), 2)
                                    if abs(g_load) else None),
                 "x": round(g_load.real, 5), "y": round(g_load.imag, 5)},
        "shack": {"r": round(z_in.real, 2), "x": round(z_in.imag, 2),
                  "swr": round(swr_shack, 3) if swr_shack != float("inf") else None,
                  "gamma_mag": round(abs(g_in), 4),
                  "x": round(g_in.real, 5), "y": round(g_in.imag, 5)},
        "loss": {
            "matched_db": round(matched, 3),
            "total_db": round(total, 3),
            "extra_from_swr_db": round(max(0.0, total - matched), 3),
            "power_in": tx_watts,
            "power_at_antenna": round(tx_watts * 10 ** (-total / 10.0), 1),
        },
        "path": walk(z_load, line, mhz, feet),
    }
